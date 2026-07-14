from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    founder = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    investor = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Investor", "type": "investor"}, headers=h
    ).json()["id"]
    for sh, qty in ((founder, 8000), (investor, 2000)):
        client.post(
            f"/entities/{eid}/issuances",
            json={"security_class_id": sc, "stakeholder_id": sh, "quantity": qty, "price_per_unit": "10", "issue_date": "2026-01-01"},
            headers=h,
        )
    return eid, sc, founder, investor


def _rights(client, h, eid, sc, num=1, den=2, price="50"):
    return client.post(
        f"/entities/{eid}/rights-issues",
        json={"security_class_id": sc, "ratio_num": num, "ratio_den": den, "price_per_unit": price},
        headers=h,
    ).json()["id"]


def test_entitlements_pro_rata(client):
    h = auth_headers(client)
    eid, sc, founder, investor = _setup(client, h)
    rid = _rights(client, h, eid, sc, 1, 2)  # 1 new per 2 held
    ent = client.get(f"/rights-issues/{rid}/entitlements", headers=h).json()
    by = {e["stakeholder_name"]: e for e in ent["entitlements"]}
    assert by["Founder"]["entitled"] == 4000  # 8000 / 2
    assert by["Investor"]["entitled"] == 1000  # 2000 / 2


def test_subscribe_and_close_issues_shares(client):
    h = auth_headers(client)
    eid, sc, founder, investor = _setup(client, h)
    rid = _rights(client, h, eid, sc, 1, 2, "50")

    # founder takes full 4000; investor takes partial 600
    assert client.post(f"/rights-issues/{rid}/subscriptions", json={"stakeholder_id": founder, "quantity": 4000}, headers=h).status_code == 201
    assert client.post(f"/rights-issues/{rid}/subscriptions", json={"stakeholder_id": investor, "quantity": 600}, headers=h).status_code == 201
    # over-subscription beyond entitlement rejected
    assert client.post(f"/rights-issues/{rid}/subscriptions", json={"stakeholder_id": investor, "quantity": 500}, headers=h).status_code == 400

    res = client.post(f"/rights-issues/{rid}/close", headers=h).json()
    assert res["issued_shares"] == 4600
    # 4000*50 + 600*50 = 230000 (price stored as Numeric(18,4))
    assert res["amount_raised"] == "230000.0000"

    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    by = {r["stakeholder_name"]: r for r in ct["holders"]}
    assert by["Founder"]["quantity"] == 12000  # 8000 + 4000
    assert by["Investor"]["quantity"] == 2600  # 2000 + 600
    assert ct["total_shares"] == 14600


def test_cannot_subscribe_after_close(client):
    h = auth_headers(client)
    eid, sc, founder, investor = _setup(client, h)
    rid = _rights(client, h, eid, sc, 1, 2)
    client.post(f"/rights-issues/{rid}/close", headers=h)
    r = client.post(f"/rights-issues/{rid}/subscriptions", json={"stakeholder_id": founder, "quantity": 100}, headers=h)
    assert r.status_code == 409


def test_rights_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid, sc, _, _ = _setup(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/rights-issues",
            json={"security_class_id": sc, "ratio_num": 1, "ratio_den": 2},
            headers=outsider,
        ).status_code
        == 403
    )
