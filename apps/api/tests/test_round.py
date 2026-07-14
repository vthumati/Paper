from tests.conftest import auth_headers


def _entity_with_class(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Seed CCPS", "kind": "ccps"},
        headers=h,
    ).json()["id"]
    return eid, sc


def _round(client, h, eid, sc):
    return client.post(
        f"/entities/{eid}/rounds",
        json={
            "name": "Seed",
            "instrument": "ccps",
            "pre_money": "40000000",
            "target_amount": "10000000",
            "price_per_share": "100",
            "security_class_id": sc,
        },
        headers=h,
    ).json()["id"]


def test_round_summary_models_dilution(client):
    h = auth_headers(client)
    eid, sc = _entity_with_class(client, h)
    # seed an existing founder holding so dilution is meaningful
    f = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": f, "quantity": 900000, "price_per_unit": "1", "issue_date": "2026-01-01"},
        headers=h,
    )
    rid = _round(client, h, eid, sc)
    client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Seed Fund", "amount": "10000000"},
        headers=h,
    )
    s = client.get(f"/rounds/{rid}/summary", headers=h).json()
    assert s["committed"] == "10000000.00"
    assert s["post_money"] == "50000000.00"
    # 10,000,000 / 100 = 100,000 new shares; existing 900,000 -> 10% to new investors
    assert s["new_shares"] == 100000
    assert s["implied_new_ownership_pct"] == 10.0


def test_term_sheet_generation(client):
    h = auth_headers(client)
    eid, sc = _entity_with_class(client, h)
    rid = _round(client, h, eid, sc)
    ts = client.post(f"/rounds/{rid}/term-sheet", headers=h)
    assert ts.status_code == 201
    assert "TERM SHEET" in ts.json()["content"] and "Seed" in ts.json()["content"]


def test_close_issues_only_funded_and_flags_fema(client):
    h = auth_headers(client)
    eid, sc = _entity_with_class(client, h)
    rid = _round(client, h, eid, sc)
    # two commitments: one funded foreign, one only soft
    c1 = client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Overseas VC", "amount": "10000000", "is_foreign": True},
        headers=h,
    ).json()["id"]
    client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Maybe Angel", "amount": "500000"},
        headers=h,
    )
    client.post(f"/rounds/{rid}/commitments/{c1}/status", json={"status": "funded"}, headers=h)

    res = client.post(f"/rounds/{rid}/close", headers=h).json()
    assert res["issued"] == 1
    assert res["foreign_investors"] is True
    assert res["fc_gpr_obligation_id"]

    # round is closed; closing again -> 409
    assert client.post(f"/rounds/{rid}/close", headers=h).status_code == 409

    # cap table reflects the funded foreign investor only (100,000 shares)
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 100000
    assert ct["holders"][0]["stakeholder_name"] == "Overseas VC"

    # an FC-GPR FEMA obligation was created
    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "FC-GPR" and o["category"] == "FEMA" for o in obs)


def test_round_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid, sc = _entity_with_class(client, owner)
    rid = _round(client, owner, eid, sc)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/rounds/{rid}/commitments", headers=outsider).status_code == 403
