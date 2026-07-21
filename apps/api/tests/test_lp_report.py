from tests.conftest import auth_headers


def test_report_preview_and_portal_view(client):
    """The web-native report view: GP preview JSON + LP-scoped portal route."""
    gp = auth_headers(client, email="gp@fund.in")
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=gp).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=gp
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=gp).json()["id"]
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "LP One", "email": "lp1@invest.in", "commitment": "10000000"},
        headers=gp,
    )
    client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "Acme", "amount": "2000000", "invested_on": "2025-01-15"},
        headers=gp,
    )

    # GP preview defaults to the last completed quarter
    prev = client.get(f"/funds/{fid}/lp-report/preview", headers=gp)
    assert prev.status_code == 200
    data = prev.json()
    assert data["fund_name"] == "Alpha Fund I"
    assert data["period_label"].startswith("FY")
    assert data["snapshot"]["committed"] == "10000000.00"
    assert len(data["holdings"]) == 1
    assert data["holdings"][0]["holding_years"] is not None

    # the LP sees the same view through their portal; a stranger 404s
    lp = auth_headers(client, email="lp1@invest.in")
    mine = client.get(f"/portal/funds/{fid}/lp-report", headers=lp)
    assert mine.status_code == 200 and mine.json()["fund_name"] == "Alpha Fund I"
    stranger = auth_headers(client, email="nobody@nowhere.in")
    assert client.get(f"/portal/funds/{fid}/lp-report", headers=stranger).status_code == 404

LP_EMAIL = "lp-report@x.in"


def _fund_with_lp(client, h, commitment="20000000"):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "Report LP", "email": LP_EMAIL, "commitment": commitment},
        headers=h,
    )
    return fid


def test_lp_report_composes_and_surfaces_in_portal(client):
    h = auth_headers(client)
    fid = _fund_with_lp(client, h)

    # quarter activity: a paid 50% call and a return-of-capital distribution
    call = client.post(
        f"/funds/{fid}/capital-calls",
        json={"pct": "0.5", "purpose": "Deal 1", "due_date": "2026-05-15"},
        headers=h,
    ).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)
    client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "2000000", "kind": "return_of_capital", "date": "2026-06-10"},
        headers=h,
    )
    # a holding marked up
    iid = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "Acme", "amount": "5000000"},
        headers=h,
    ).json()["id"]
    client.put(f"/funds/{fid}/portfolio/{iid}/mark", json={"current_value": "9000000"}, headers=h)

    r = client.post(
        f"/funds/{fid}/lp-report",
        json={"period_label": "FY27 Q1", "period_start": "2026-04-01", "period_end": "2026-06-30"},
        headers=h,
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["subject_type"] == "lp_report"
    body = doc["content"]
    assert "Alpha Fund I" in body and "FY27 Q1" in body
    assert "Committed ₹2,00,00,000" in body and "Drawn ₹1,00,00,000" in body
    assert "Capital call #1 (2026-05-15): ₹1,00,00,000 — Deal 1" in body
    assert "Distribution #1 (2026-06-10): ₹20,00,000 gross" in body
    assert "Acme: cost ₹50,00,000 · fair value ₹90,00,000 · MOIC 1.80×" in body
    assert "0 of 1 holdings valued" in body

    # the report surfaces in the LP's portal statements automatically
    lp_h = auth_headers(client, email=LP_EMAIL)
    p = client.get("/portal", headers=lp_h).json()
    titles = [s["title"] for s in p["funds"][0]["statements"]]
    assert "LP Report — FY27 Q1" in titles


def test_lp_report_quiet_period(client):
    h = auth_headers(client)
    fid = _fund_with_lp(client, h)
    body = client.post(
        f"/funds/{fid}/lp-report",
        json={"period_label": "FY27 Q2", "period_start": "2026-07-01", "period_end": "2026-09-30"},
        headers=h,
    ).json()["content"]
    assert "No capital calls or distributions this period." in body
    assert "No portfolio holdings." in body


def test_lp_report_rejects_inverted_period(client):
    h = auth_headers(client)
    fid = _fund_with_lp(client, h)
    r = client.post(
        f"/funds/{fid}/lp-report",
        json={"period_label": "Bad", "period_start": "2026-06-30", "period_end": "2026-04-01"},
        headers=h,
    )
    assert r.status_code == 400
