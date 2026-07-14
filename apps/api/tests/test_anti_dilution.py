from tests.conftest import auth_headers


def _setup(client, h, method="broad_based"):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    common = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    ccps = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Seed CCPS", "kind": "ccps", "pref_multiple": "1",
              "anti_dilution": method, "orig_issue_price": "100"},
        headers=h,
    ).json()["id"]
    founder = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Seed Investor", "type": "investor"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": common, "stakeholder_id": founder, "quantity": 900000, "price_per_unit": "1", "issue_date": "2024-01-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": ccps, "stakeholder_id": inv, "quantity": 100000, "price_per_unit": "100", "issue_date": "2024-06-01"},
        headers=h,
    )
    return eid, ccps


def test_broad_based_weighted_average(client):
    h = auth_headers(client)
    eid, ccps = _setup(client, h)
    # A = 1,000,000 FD pre; B = (50 x 250,000)/100 = 125,000; C = 250,000
    # CP2 = 100 x 1,125,000 / 1,250,000 = 90 exactly; ratio 100/90
    r = client.get(
        f"/entities/{eid}/security-classes/{ccps}/anti-dilution?new_price=50&new_shares=250000",
        headers=h,
    ).json()
    assert r["method"] == "broad_based"
    assert r["adjusted_price"] == "90.0000"
    assert r["conversion_ratio"] == "1.111111"
    assert r["holders"] == [
        {"stakeholder_id": r["holders"][0]["stakeholder_id"], "stakeholder_name": "Seed Investor",
         "held": 100000, "additional_shares": 11111}
    ]


def test_full_ratchet(client):
    h = auth_headers(client)
    eid, ccps = _setup(client, h, method="full_ratchet")
    r = client.get(
        f"/entities/{eid}/security-classes/{ccps}/anti-dilution?new_price=50&new_shares=250000",
        headers=h,
    ).json()
    assert r["adjusted_price"] == "50.0000"
    assert r["conversion_ratio"] == "2.000000"
    assert r["holders"][0]["additional_shares"] == 100000


def test_up_round_makes_no_adjustment(client):
    h = auth_headers(client)
    eid, ccps = _setup(client, h)
    r = client.get(
        f"/entities/{eid}/security-classes/{ccps}/anti-dilution?new_price=120&new_shares=100000",
        headers=h,
    ).json()
    assert r["adjusted_price"] == "100.0000"
    assert r["conversion_ratio"] == "1.000000"
    assert r["holders"][0]["additional_shares"] == 0


def test_unprotected_class_rejected(client):
    h = auth_headers(client)
    eid, ccps = _setup(client, h, method="none")
    r = client.get(
        f"/entities/{eid}/security-classes/{ccps}/anti-dilution?new_price=50&new_shares=250000",
        headers=h,
    )
    assert r.status_code == 400
