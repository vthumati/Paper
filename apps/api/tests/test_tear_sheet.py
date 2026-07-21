from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def test_tear_sheet_composes_value_kpis_and_signals(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "Troubled Co", "amount": "10000000",
              "instrument": "equity", "ownership_pct": "12.5", "invested_on": "2025-04-01"},
        headers=h,
    ).json()["id"]
    # declining revenue + short runway, marked below cost -> signals fire
    for period, as_of, rev, cash in [
        ("Q1", "2026-03-31", "2000000", "30000000"),
        ("Q2", "2026-06-30", "1400000", "8000000"),
    ]:
        client.post(f"/funds/{fid}/portfolio/{iid}/kpis", headers=h,
                    json={"period_label": period, "as_of": as_of, "revenue": rev,
                          "cash": cash, "monthly_burn": "2000000"})
    client.post(
        f"/funds/{fid}/portfolio/{iid}/valuations",
        json={"as_of": "2026-07-01", "value": "7000000", "methodology": "ipev_market",
              "valuer": "Kroll India", "is_independent": True},
        headers=h,
    )

    r = client.post(f"/funds/{fid}/portfolio/{iid}/tear-sheet", headers=h)
    assert r.status_code == 201
    doc = r.json()
    assert doc["subject_type"] == "tear_sheet"
    assert "Troubled Co" in doc["title"]
    body = doc["content"]
    assert "Troubled Co" in body and "Alpha Fund I" in body
    assert "MOIC 0.70×" in body            # 70L mark on 1Cr cost
    assert "₹70,00,000 (IPEV" in body      # latest valuation, lakh/crore grouping
    assert "[independent]" in body
    # KPI trend is newest-first
    assert body.index("Q2 (2026-06-30)") < body.index("Q1 (2026-03-31)")
    assert "[HIGH] Revenue down 30.0%" in body
    assert "[HIGH] Runway 4.0 months" in body


def test_tear_sheet_healthy_company_without_history(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "Fresh Co", "amount": "5000000"},
        headers=h,
    ).json()["id"]
    # one recent healthy period so no signals fire, no valuation recorded
    client.post(f"/funds/{fid}/portfolio/{iid}/kpis", headers=h,
                json={"period_label": "Q2", "as_of": "2026-06-30", "revenue": "1000000",
                      "cash": "60000000", "monthly_burn": "2000000"})

    body = client.post(f"/funds/{fid}/portfolio/{iid}/tear-sheet", headers=h).json()["content"]
    assert "MOIC 1.00×" in body            # no mark -> fair value = cost
    assert "none recorded" in body
    assert "None — healthy" in body


def test_tear_sheet_unknown_investment_404(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    r = client.post(f"/funds/{fid}/portfolio/nope/tear-sheet", headers=h)
    assert r.status_code == 404
