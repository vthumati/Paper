from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


def test_family_friends_safe_and_portal(client):
    founder = auth_headers(client, email="founder@acme.in")
    eid = _company(client, founder)
    r = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Sunita Sharma", "investor_email": "sunita@family.in",
              "investor_kind": "friend_family", "instrument_type": "safe",
              "principal": "500000", "discount_pct": "0.15", "issue_date": "2026-05-01"},
        headers=founder,
    )
    assert r.status_code == 201 and r.json()["investor_kind"] == "friend_family"

    # the F&F investor sees their SAFE in the portal, with no explicit grant
    sunita = auth_headers(client, email="sunita@family.in")
    portal = client.get("/portal", headers=sunita).json()
    assert portal["summary"]["companies"] == 1
    co = portal["companies"][0]
    assert co["entity_name"] == "Acme Pvt Ltd"
    assert co["instruments"][0]["investor_kind"] == "friend_family"
    assert co["instruments"][0]["principal"] == "500000.00"
    assert portal["summary"]["total_invested"] == "500000.00"


def test_commitment_carries_investor_kind(client):
    h = auth_headers(client)
    eid = _company(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Pre-seed", "instrument": "equity", "pre_money": "20000000",
              "target_amount": "2000000", "price_per_share": "20", "security_class_id": sc},
        headers=h,
    ).json()["id"]
    c = client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Uncle Prakash", "investor_kind": "friend_family", "amount": "300000"},
        headers=h,
    ).json()
    assert c["investor_kind"] == "friend_family"


def test_sec42_offeree_limit(client, monkeypatch):
    from app.services import placement

    monkeypatch.setattr(placement, "MAX_OFFEREES_PER_FY", 3)
    h = auth_headers(client)
    eid = _company(client, h)
    for i in range(3):
        r = client.post(
            f"/entities/{eid}/instruments",
            json={"investor_name": f"Friend {i}", "investor_kind": "friend_family",
                  "instrument_type": "safe", "principal": "100000", "discount_pct": "0.1",
                  "issue_date": "2026-05-01"},
            headers=h,
        )
        assert r.status_code == 201
    # a 4th distinct offeree in the same FY is rejected
    blocked = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Friend 99", "investor_kind": "friend_family",
              "instrument_type": "safe", "principal": "100000", "discount_pct": "0.1",
              "issue_date": "2026-06-01"},
        headers=h,
    )
    assert blocked.status_code == 400 and "Sec 42" in blocked.json()["detail"]
    # a repeat cheque from an existing offeree is fine
    again = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Friend 0", "investor_kind": "friend_family",
              "instrument_type": "safe", "principal": "50000", "discount_pct": "0.1",
              "issue_date": "2026-06-01"},
        headers=h,
    )
    assert again.status_code == 201
