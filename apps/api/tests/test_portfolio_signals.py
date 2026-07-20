from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def _inv(client, h, fid, name, amount="10000000"):
    return client.post(
        f"/funds/{fid}/portfolio", json={"company_name": name, "amount": amount}, headers=h
    ).json()["id"]


def _kpi(client, h, fid, iid, period, as_of, **vals):
    client.post(f"/funds/{fid}/portfolio/{iid}/kpis", headers=h,
                json={"period_label": period, "as_of": as_of, **vals})


def test_risk_signals_fire(client):
    h = auth_headers(client)
    fid = _fund(client, h)

    # Troubled Co: revenue down >20%, runway < 6mo, marked below cost
    tc = _inv(client, h, fid, "Troubled Co")
    _kpi(client, h, fid, tc, "Q1", "2026-03-31", revenue="2000000", cash="30000000", monthly_burn="2000000")
    _kpi(client, h, fid, tc, "Q2", "2026-06-30", revenue="1400000", cash="8000000", monthly_burn="2000000")
    client.put(f"/funds/{fid}/portfolio/{tc}/mark", json={"current_value": "7000000"}, headers=h)

    s = client.get(f"/funds/{fid}/signals", headers=h).json()
    by = {c["company_name"]: c for c in s["companies"]}
    kinds = {sig["kind"]: sig for sig in by["Troubled Co"]["signals"]}
    assert kinds["revenue_decline"]["severity"] == "high"    # 30% drop > 20%
    assert kinds["low_runway"]["severity"] == "high"         # 8m/2m = 4 months
    assert kinds["mark_below_cost"]["severity"] == "warn"    # 10m cost -> 7m mark
    assert s["totals"]["high"] == 2 and s["totals"]["warn"] == 1


def test_follow_on_and_mild_decline(client):
    h = auth_headers(client)
    fid = _fund(client, h)

    # Rocket Co: growing with 15 months runway -> follow-on candidate
    rc = _inv(client, h, fid, "Rocket Co")
    _kpi(client, h, fid, rc, "Q1", "2026-03-31", revenue="1000000", cash="30000000", monthly_burn="2000000")
    _kpi(client, h, fid, rc, "Q2", "2026-06-30", revenue="1500000", cash="30000000", monthly_burn="2000000")

    # Dip Co: 10% decline -> warn (not high)
    dc = _inv(client, h, fid, "Dip Co")
    _kpi(client, h, fid, dc, "Q1", "2026-03-31", revenue="1000000", cash="60000000", monthly_burn="2000000")
    _kpi(client, h, fid, dc, "Q2", "2026-06-30", revenue="900000", cash="60000000", monthly_burn="2000000")

    s = client.get(f"/funds/{fid}/signals", headers=h).json()
    by = {c["company_name"]: c for c in s["companies"]}
    rk = {sig["kind"]: sig for sig in by["Rocket Co"]["signals"]}
    assert rk["follow_on_candidate"]["severity"] == "positive"
    dk = {sig["kind"]: sig for sig in by["Dip Co"]["signals"]}
    assert dk["revenue_decline"]["severity"] == "warn"
    assert s["totals"]["positive"] == 1


def test_reporting_cadence_and_clear_count(client):
    h = auth_headers(client)
    fid = _fund(client, h)

    # Silent Co: last report far in the past -> reporting_silent
    sc = _inv(client, h, fid, "Silent Co")
    _kpi(client, h, fid, sc, "FY25 Q3", "2025-09-30", revenue="1000000")

    # Fresh Co: never reported -> info
    _inv(client, h, fid, "Fresh Co")

    # Healthy Co: recent flat report, no mark issues -> clear (absent from list)
    hc = _inv(client, h, fid, "Healthy Co")
    _kpi(client, h, fid, hc, "Q2", "2026-06-30", revenue="1000000", cash="60000000", monthly_burn="2000000")

    s = client.get(f"/funds/{fid}/signals", headers=h).json()
    by = {c["company_name"]: c for c in s["companies"]}
    assert {x["kind"] for x in by["Silent Co"]["signals"]} == {"reporting_silent"}
    assert {x["kind"] for x in by["Fresh Co"]["signals"]} == {"never_reported"}
    assert "Healthy Co" not in by
    assert s["totals"]["clear"] == 1
    assert s["totals"]["info"] == 1
