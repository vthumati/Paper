"""Portfolio segments (sector cohorts in benchmarks) and the plan-vs-actual
variance report on the fund forecast (Visible-style portfolio intelligence)."""
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def _inv(client, h, fid, name, sector=None, amount="10000000"):
    return client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": name, "sector": sector, "amount": amount, "invested_on": "2026-01-15"},
        headers=h,
    ).json()["id"]


def test_segment_medians_in_benchmarks(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    for name, sector, rev in [
        ("FinCo", "fintech", "1000000"),
        ("PayCo", "fintech", "3000000"),
        ("ShopCo", "commerce", "8000000"),
    ]:
        iid = _inv(client, h, fid, name, sector)
        client.post(
            f"/funds/{fid}/portfolio/{iid}/kpis",
            json={"period_label": "Q1", "as_of": "2026-03-31", "revenue": rev},
            headers=h,
        )

    b = client.get(f"/funds/{fid}/benchmarks", headers=h).json()
    segs = {s["segment"]: s for s in b["segments"]}
    assert set(segs) == {"fintech", "commerce"}
    assert segs["fintech"]["companies"] == 2
    assert segs["fintech"]["medians"]["revenue"] == 2000000.0
    assert segs["commerce"]["medians"]["revenue"] == 8000000.0
    # overall median unchanged by segmentation
    assert b["medians"]["revenue"] == 3000000.0


def test_single_segment_hides_comparison(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid, "OnlyCo")  # untagged
    client.post(
        f"/funds/{fid}/portfolio/{iid}/kpis",
        json={"period_label": "Q1", "as_of": "2026-03-31", "revenue": "1000000"},
        headers=h,
    )
    b = client.get(f"/funds/{fid}/benchmarks", headers=h).json()
    assert b["segments"] == []  # nothing to compare against


def test_variance_report_rows(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    # plan: 100 Cr fund, 4-year period, 2.5 Cr cheques, 3x gross
    client.put(
        f"/funds/{fid}/plan",
        json={
            "fund_size": "1000000000",
            "investment_period_years": 4,
            "avg_initial_cheque": "25000000",
            "avg_entry_valuation": "250000000",
            "projected_gross_moic": "3",
        },
        headers=h,
    )
    _inv(client, h, fid, "Acme", "saas", amount="30000000")

    plan = client.get(f"/funds/{fid}/plan", headers=h).json()
    rows = {r["metric"]: r for r in plan["variance"]}
    assert rows["Average initial cheque"]["planned"] == "25000000.00"
    assert rows["Average initial cheque"]["actual"] == "30000000.00"
    assert rows["Average initial cheque"]["variance_pct"] == 20.0
    assert rows["Portfolio companies"]["actual"] == 1
    # unmarked position -> MOIC actual held at cost = 1.00
    assert rows["Gross MOIC"]["planned"] == "3.00" and rows["Gross MOIC"]["actual"] == "1.00"
    assert rows["Capital deployed to date"]["planned"] is not None
    # nothing paid in yet -> TVPI actual unknown
    assert rows["Net TVPI"]["actual"] is None and rows["Net TVPI"]["variance_pct"] is None
