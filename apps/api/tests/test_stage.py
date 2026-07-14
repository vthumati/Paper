from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Acme Pvt Ltd", "type": "pvt_ltd", "incorporation_date": "2025-01-01"},
        headers=h,
    ).json()["id"]
    return eid


def test_new_company_starts_at_inception(client):
    h = auth_headers(client)
    eid = _company(client, h)
    g = client.get(f"/entities/{eid}/stage-guide", headers=h).json()
    assert g["stage"] == "inception"
    assert g["suggested_stage"] is None
    # inception hides fundraising/data-room/valuations tabs
    assert "fundraising" not in g["tabs"] and "dataroom" not in g["tabs"]
    assert "captable" in g["tabs"] and "compliance" in g["tabs"]
    # advanced features locked, founder vesting available
    assert g["features"]["founder_vesting"] is True
    assert g["features"]["anti_dilution"] is False
    assert g["features"]["demat"] is False
    # incorporation recorded -> that item is already done
    by_key = {c["key"]: c for c in g["checklist"]}
    assert by_key["incorporated"]["done"] is True
    assert by_key["founder_shares"]["done"] is False
    assert g["progress"]["done"] == 1


def test_checklist_items_flip_when_work_is_done(client):
    h = auth_headers(client)
    eid = _company(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    f = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": f, "quantity": 100000, "price_per_unit": "1", "issue_date": "2025-01-02"},
        headers=h,
    )
    client.post(f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 10000}, headers=h)
    g = client.get(f"/entities/{eid}/stage-guide", headers=h).json()
    by_key = {c["key"]: c for c in g["checklist"]}
    assert by_key["founder_shares"]["done"] is True
    # the ESOP pool item lives on the pre-seed checklist
    g = client.put(f"/entities/{eid}/stage", json={"stage": "preseed"}, headers=h).json()
    by_key = {c["key"]: c for c in g["checklist"]}
    assert by_key["esop_pool"]["done"] is True


def test_stages_can_be_skipped(client):
    h = auth_headers(client)
    eid = _company(client, h)
    # straight from inception to pre-IPO, and back again — no gating
    g = client.put(f"/entities/{eid}/stage", json={"stage": "ipo"}, headers=h).json()
    assert g["stage"] == "ipo" and g["features"]["demat"] is True
    g = client.put(f"/entities/{eid}/stage", json={"stage": "inception"}, headers=h).json()
    assert g["stage"] == "inception"


def test_stage_change_unlocks_tabs_and_features(client):
    h = auth_headers(client)
    eid = _company(client, h)
    g = client.put(f"/entities/{eid}/stage", json={"stage": "series"}, headers=h).json()
    assert g["stage"] == "series"
    assert "fundraising" in g["tabs"] and "contracts" in g["tabs"]
    assert g["features"]["anti_dilution"] is True and g["features"]["waterfall"] is True
    assert g["features"]["demat"] is False  # ipo only
    # invalid stage rejected by schema
    bad = client.put(f"/entities/{eid}/stage", json={"stage": "unicorn"}, headers=h)
    assert bad.status_code == 422


def test_stage_suggested_from_data(client):
    h = auth_headers(client)
    eid = _company(client, h)
    # a SAFE on file suggests pre-seed
    client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Angel", "instrument_type": "safe", "principal": "1000000", "discount_pct": "0.2", "issue_date": "2025-06-01"},
        headers=h,
    )
    g = client.get(f"/entities/{eid}/stage-guide", headers=h).json()
    assert g["suggested_stage"] == "preseed"
    # accepting the suggestion clears it
    g = client.put(f"/entities/{eid}/stage", json={"stage": "preseed"}, headers=h).json()
    assert g["suggested_stage"] is None
    # a priced round suggests seed
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "CCPS", "kind": "ccps"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Seed", "instrument": "ccps", "pre_money": "40000000", "target_amount": "10000000", "price_per_share": "100", "security_class_id": sc},
        headers=h,
    )
    g = client.get(f"/entities/{eid}/stage-guide", headers=h).json()
    assert g["suggested_stage"] == "seed"


def test_stages_do_not_apply_to_funds(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    assert client.get(f"/entities/{eid}/stage-guide", headers=h).status_code == 400
    assert (
        client.put(f"/entities/{eid}/stage", json={"stage": "seed"}, headers=h).status_code == 400
    )
