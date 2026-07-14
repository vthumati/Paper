from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    f = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": f, "quantity": 1000000, "price_per_unit": "1", "issue_date": "2025-01-01"},
        headers=h,
    )
    return eid, sc


def test_fully_diluted_combines_options_pool_and_converts(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    # ESOP: pool 200,000; grant 50,000 (unexercised) -> 150,000 unallocated
    emp = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Emp", "type": "employee"}, headers=h
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 200000}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": 50000, "exercise_price": "10", "grant_date": "2025-01-01"},
        headers=h,
    )
    # SAFE 1,000,000 at 20% discount; at assumed price 100 -> 80 -> 12,500 shares
    client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Seed Angel", "instrument_type": "safe", "principal": "1000000", "discount_pct": "0.20", "issue_date": "2025-06-01"},
        headers=h,
    )

    fd = client.get(f"/entities/{eid}/cap-table/fully-diluted?assumed_price=100", headers=h).json()
    assert fd["issued_shares"] == 1000000
    assert fd["option_shares"] == 50000
    assert fd["pool_unallocated"] == 150000
    assert fd["convertible_shares"] == 12500
    assert fd["fully_diluted_shares"] == 1212500
    assert fd["excluded_instruments"] == []

    rows = {r["name"]: r for r in fd["rows"]}
    assert rows["Founder"]["issued"] == 1000000 and rows["Founder"]["pct"] == 82.4742
    assert rows["Emp"]["options"] == 50000
    assert rows["ESOP pool (unallocated)"]["options"] == 150000
    assert rows["Seed Angel"]["converts"] == 12500


def test_fully_diluted_excludes_unpriceable_instruments(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Seed Angel", "instrument_type": "safe", "principal": "1000000", "discount_pct": "0.20", "issue_date": "2025-06-01"},
        headers=h,
    )
    # no assumed price and no valuation on file -> instrument listed, not guessed
    fd = client.get(f"/entities/{eid}/cap-table/fully-diluted", headers=h).json()
    assert fd["assumed_price"] is None
    assert fd["convertible_shares"] == 0
    assert fd["fully_diluted_shares"] == 1000000
    assert fd["excluded_instruments"] == ["Seed Angel"]


def test_fully_diluted_uses_current_fmv_as_fallback(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Seed Angel", "instrument_type": "safe", "principal": "1000000", "discount_pct": "0.20", "issue_date": "2025-06-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "100", "valuation_date": "2025-12-01"},
        headers=h,
    )
    fd = client.get(f"/entities/{eid}/cap-table/fully-diluted", headers=h).json()
    assert fd["assumed_price"] == "100.0000"
    assert fd["convertible_shares"] == 12500
