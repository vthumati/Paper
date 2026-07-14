from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    # existing 1,000,000 founder shares so the cap price has a share base
    f = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": f, "quantity": 1000000, "price_per_unit": "1", "issue_date": "2025-01-01"},
        headers=h,
    )
    return eid, sc


def test_safe_converts_at_discount(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    # SAFE 1,000,000 with 20% discount, no cap
    sid = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Seed Angel", "instrument_type": "safe", "principal": "1000000", "discount_pct": "0.20", "issue_date": "2025-06-01"},
        headers=h,
    ).json()["id"]
    # round price 100 -> discount price 80 -> shares = 1,000,000/80 = 12,500
    prev = client.get(f"/instruments/{sid}/conversion-preview?round_price_per_share=100", headers=h).json()
    assert prev["conversion_price"] == "80.0000" and prev["shares"] == 12500

    res = client.post(
        f"/instruments/{sid}/convert",
        json={"round_price_per_share": "100", "security_class_id": sc},
        headers=h,
    ).json()
    assert res["converted_shares"] == 12500
    # appears in cap table; instrument marked converted
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert any(r["stakeholder_name"] == "Seed Angel" and r["quantity"] == 12500 for r in ct["holders"])
    assert client.get(f"/entities/{eid}/instruments", headers=h).json()[0]["status"] == "converted"


def test_safe_cap_beats_discount(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    # cap 50,000,000 over 1,000,000 shares -> cap price 50; discount 20% of round 100 -> 80; min = 50
    sid = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Cap Angel", "instrument_type": "safe", "principal": "5000000", "valuation_cap": "50000000", "discount_pct": "0.20", "issue_date": "2025-06-01"},
        headers=h,
    ).json()["id"]
    prev = client.get(f"/instruments/{sid}/conversion-preview?round_price_per_share=100", headers=h).json()
    assert prev["conversion_price"] == "50.0000"  # cap price wins
    assert prev["shares"] == 100000  # 5,000,000 / 50


def test_convert_is_idempotent_guarded(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    sid = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "X", "instrument_type": "safe", "principal": "100000", "discount_pct": "0.10", "issue_date": "2025-06-01"},
        headers=h,
    ).json()["id"]
    client.post(f"/instruments/{sid}/convert", json={"round_price_per_share": "100", "security_class_id": sc}, headers=h)
    again = client.post(f"/instruments/{sid}/convert", json={"round_price_per_share": "100", "security_class_id": sc}, headers=h)
    assert again.status_code == 409


def test_demat_record(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    r = client.post(
        f"/entities/{eid}/demat",
        json={"security_class_id": sc, "isin": "INE000A01010", "depository": "NSDL", "status": "dematerialised"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["isin"] == "INE000A01010"
    assert len(client.get(f"/entities/{eid}/demat", headers=h).json()) == 1


def test_cap_table_csv_export(client):
    h = auth_headers(client)
    eid, sc = _setup(client, h)
    resp = client.get(f"/entities/{eid}/cap-table.csv", headers=h)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "Stakeholder" in resp.text and "Founder" in resp.text
