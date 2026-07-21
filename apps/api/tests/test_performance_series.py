from app.clock import today_ist
from tests.conftest import auth_headers


def _fund_with_lp(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    client.post(
        f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "20000000"}, headers=h
    )
    return fid


def test_series_tracks_flows_and_marks(client):
    h = auth_headers(client)
    fid = _fund_with_lp(client, h)

    # 50% call paid today -> paid-in 1Cr; invest 80L (backdated invested_on)
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.5"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)
    iid = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "Acme", "amount": "8000000", "invested_on": "2026-05-01"},
        headers=h,
    ).json()["id"]
    # a valuation doubling the mark and a 20L distribution, both dated after today
    client.post(
        f"/funds/{fid}/portfolio/{iid}/valuations",
        json={"as_of": "2027-01-15", "value": "16000000", "methodology": "ipev_market"},
        headers=h,
    )
    client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "2000000", "kind": "return_of_capital", "date": "2027-02-01"},
        headers=h,
    )

    s = client.get(f"/funds/{fid}/performance-series", headers=h).json()
    assert [p["date"] for p in s] == sorted(p["date"] for p in s)
    by = {p["date"]: p for p in s}
    # dates before the first paid drawdown are skipped (TVPI undefined)
    assert "2026-05-01" not in by
    # first point = the drawdown payment day: held at cost
    today = today_ist().isoformat()
    assert s[0]["date"] == today
    assert by[today]["nav"] == "8000000.00"
    assert by[today]["tvpi"] == "0.80" and by[today]["dpi"] == "0.00"
    # valuation date: mark doubles -> NAV 1.6Cr, TVPI 1.60
    assert by["2027-01-15"]["nav"] == "16000000.00"
    assert by["2027-01-15"]["tvpi"] == "1.60"
    # after the distribution: DPI 0.20, TVPI 1.80
    assert by["2027-02-01"]["dpi"] == "0.20"
    assert by["2027-02-01"]["tvpi"] == "1.80"


def test_series_empty_before_first_drawdown(client):
    h = auth_headers(client)
    fid = _fund_with_lp(client, h)
    assert client.get(f"/funds/{fid}/performance-series", headers=h).json() == []
