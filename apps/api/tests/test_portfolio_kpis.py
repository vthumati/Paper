from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h
    ).json()["id"]
    return fid


def _investment(client, h, fid, name="Acme", amount="10000000"):
    return client.post(
        f"/funds/{fid}/portfolio", json={"company_name": name, "amount": amount}, headers=h
    ).json()["id"]


def test_add_and_list_kpis(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _investment(client, h, fid)
    r = client.post(
        f"/funds/{fid}/portfolio/{iid}/kpis",
        json={"period_label": "FY26 Q1", "as_of": "2026-06-30", "revenue": "1000000",
              "cash": "30000000", "monthly_burn": "2500000", "headcount": 20},
        headers=h,
    )
    assert r.status_code == 201
    hist = r.json()
    assert len(hist) == 1
    # runway = 30,000,000 / 2,500,000 = 12 months
    assert hist[0]["runway_months"] == 12.0


def test_monitoring_growth_runway_and_rollup(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    acme = _investment(client, h, fid, "Acme")
    beta = _investment(client, h, fid, "Beta", "5000000")

    client.post(f"/funds/{fid}/portfolio/{acme}/kpis", headers=h, json={
        "period_label": "Q1", "as_of": "2026-06-30", "revenue": "1000000",
        "cash": "30000000", "monthly_burn": "2500000", "headcount": 20})
    client.post(f"/funds/{fid}/portfolio/{acme}/kpis", headers=h, json={
        "period_label": "Q2", "as_of": "2026-09-30", "revenue": "1500000",
        "cash": "24000000", "monthly_burn": "3000000", "headcount": 26})
    # Beta: 6,000,000 / 1,500,000 = 4 months -> low runway
    client.post(f"/funds/{fid}/portfolio/{beta}/kpis", headers=h, json={
        "period_label": "Q2", "as_of": "2026-09-30", "revenue": "200000",
        "cash": "6000000", "monthly_burn": "1500000", "headcount": 8})

    mon = client.get(f"/funds/{fid}/portfolio-monitoring", headers=h).json()
    by = {c["company_name"]: c for c in mon["companies"]}

    # Acme: latest picked by as_of, 50% growth, 8-month runway, not flagged
    assert by["Acme"]["latest"]["period_label"] == "Q2"
    assert by["Acme"]["revenue_growth_pct"] == 50.0
    assert by["Acme"]["runway_months"] == 8.0
    assert by["Acme"]["low_runway"] is False
    assert len(by["Acme"]["revenue_series"]) == 2

    # Beta: low runway flagged, no growth (single period)
    assert by["Beta"]["runway_months"] == 4.0
    assert by["Beta"]["low_runway"] is True
    assert by["Beta"]["revenue_growth_pct"] is None

    t = mon["totals"]
    assert t["companies"] == 2 and t["reporting"] == 2
    assert t["latest_revenue"] == "1700000.00"   # 1.5m + 0.2m
    assert t["cash"] == "30000000.00"            # 24m + 6m
    assert t["low_runway"] == 1


def test_kpi_write_requires_role_and_scopes_to_fund(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _investment(client, h, fid)
    # unknown investment id -> 404
    r = client.post(f"/funds/{fid}/portfolio/nope/kpis", headers=h,
                    json={"period_label": "Q1", "as_of": "2026-06-30"})
    assert r.status_code == 404
    # viewer (different user, no membership) cannot write
    viewer = auth_headers(client, email="viewer2@x.in")
    r2 = client.post(f"/funds/{fid}/portfolio/{iid}/kpis", headers=viewer,
                     json={"period_label": "Q1", "as_of": "2026-06-30"})
    assert r2.status_code in (403, 404)
