from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    a = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    b = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Investor", "type": "investor"}, headers=h
    ).json()["id"]
    for sh, qty in ((a, 8000), (b, 2000)):
        client.post(
            f"/entities/{eid}/issuances",
            json={"security_class_id": sc, "stakeholder_id": sh, "quantity": qty, "price_per_unit": "10", "issue_date": "2026-01-01"},
            headers=h,
        )
    return eid, sc


def test_stock_split_multiplies_all_holders(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    # 1:10 split -> every share becomes 10
    r = client.post(
        f"/entities/{eid}/corporate-actions",
        json={"security_class_id": sc, "type": "split", "numerator": 10, "denominator": 1},
        headers=h,
    )
    assert r.status_code == 201
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 100000
    by = {r["stakeholder_name"]: r for r in ct["holders"]}
    assert by["Founder"]["quantity"] == 80000
    assert by["Investor"]["quantity"] == 20000
    # ownership unchanged, invested unchanged
    assert by["Founder"]["ownership_pct"] == 80.0
    assert ct["total_invested"] == "100000.00"


def test_bonus_issue_one_for_one(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    # 1:1 bonus -> holdings double
    client.post(
        f"/entities/{eid}/corporate-actions",
        json={"security_class_id": sc, "type": "bonus", "numerator": 1, "denominator": 1},
        headers=h,
    )
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 20000
    by = {r["stakeholder_name"]: r for r in ct["holders"]}
    assert by["Founder"]["quantity"] == 16000


def test_split_then_transfer_consistent(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    a = next(s["id"] for s in client.get(f"/entities/{eid}/stakeholders", headers=h).json() if s["name"] == "Founder")
    b = next(s["id"] for s in client.get(f"/entities/{eid}/stakeholders", headers=h).json() if s["name"] == "Investor")
    # split 1:2 then founder transfers 1000 (post-split) to investor
    client.post(
        f"/entities/{eid}/corporate-actions",
        json={"security_class_id": sc, "type": "split", "numerator": 2, "denominator": 1},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/transfers",
        json={"security_class_id": sc, "from_stakeholder_id": a, "to_stakeholder_id": b, "quantity": 1000, "price_per_unit": "5"},
        headers=h,
    )
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    by = {r["stakeholder_name"]: r for r in ct["holders"]}
    # founder 16000-1000=15000 ; investor 4000+1000=5000
    assert by["Founder"]["quantity"] == 15000
    assert by["Investor"]["quantity"] == 5000
    assert ct["total_shares"] == 20000


def test_corporate_action_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid, sc = _setup(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/corporate-actions",
            json={"security_class_id": sc, "type": "split", "numerator": 2, "denominator": 1},
            headers=outsider,
        ).status_code
        == 403
    )
