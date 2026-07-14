from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_dashboard_aggregates_across_modules(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    # seed a bit of state across modules
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    sh = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": sh, "quantity": 10000, "price_per_unit": "10", "issue_date": "2026-01-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/compliance/generate", json={"financial_year_end": "2026-03-31"}, headers=h
    )
    client.post(
        f"/entities/{eid}/documents", json={"template_key": "sha", "data": {"company": "Acme"}}, headers=h
    )

    d = client.get(f"/entities/{eid}/dashboard", headers=h).json()
    assert d["entity"]["name"] == "Acme Pvt Ltd"
    assert d["cap_table"]["total_shares"] == 10000
    assert d["cap_table"]["holders"] == 1
    assert d["compliance"]["total"] == 5
    assert d["documents"] >= 1
    assert "fund" not in d  # not a fund entity


def test_dashboard_includes_fund_block_for_funds(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    client.post(f"/funds/{fid}/lps", json={"name": "LP A", "commitment": "5000000"}, headers=h)

    d = client.get(f"/entities/{eid}/dashboard", headers=h).json()
    assert d["fund"]["committed"] == "5000000.00"
    assert d["fund"]["lps"] == 1


def test_file_cabinet_search(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "title": "Series A SHA", "data": {"company": "Acme"}},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "board_resolution", "title": "Board Resolution Q1", "data": {}},
        headers=h,
    )
    allf = client.get(f"/entities/{eid}/files", headers=h).json()
    assert len(allf) == 2
    hits = client.get(f"/entities/{eid}/files?q=resolution", headers=h).json()
    assert len(hits) == 1 and "Resolution" in hits[0]["title"]


def test_tax_records_vault(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    rec = client.post(
        f"/entities/{eid}/tax-records",
        json={"type": "gst", "period_label": "Q1 FY2026", "reference": "GSTR-3B", "amount": "125000"},
        headers=h,
    )
    assert rec.status_code == 201 and rec.json()["type"] == "gst"
    recs = client.get(f"/entities/{eid}/tax-records", headers=h).json()
    assert len(recs) == 1 and recs[0]["reference"] == "GSTR-3B"


def test_workspace_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/entities/{eid}/dashboard", headers=outsider).status_code == 403
