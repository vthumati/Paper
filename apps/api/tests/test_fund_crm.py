from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "X Fund", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "carry_pct": "0.20"}, headers=h
    ).json()["id"]
    return eid, fid


def test_ddq_workflow_and_regulator_tag(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    # presets now carry an SEC/SEBI regulator tag
    listing = client.get(f"/funds/{fid}/ddq", headers=h).json()
    regs = {p["regulator"] for p in listing["presets"]}
    assert "sec" in regs and "sebi" in regs

    e = client.post(
        f"/funds/{fid}/ddq",
        json={"question": "Form ADV registration?", "category": "Governance & compliance",
              "regulator": "sec", "assignee": "Asha"},
        headers=h,
    ).json()
    assert e["status"] == "draft" and e["regulator"] == "sec" and e["assignee"] == "Asha"

    # collaborative workflow: answer, assign reviewer, move to approved
    upd = client.put(
        f"/funds/{fid}/ddq/{e['id']}",
        json={"answer": "Registered ERA.", "status": "approved", "reviewer": "Ravi"},
        headers=h,
    ).json()
    assert upd["status"] == "approved" and upd["reviewer"] == "Ravi" and upd["answered"] is True


def test_multi_currency_fx_translation(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)  # fund currency defaults to INR
    # a USD-denominated holding: cost $100,000, marked at $150,000
    inv = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "US NewCo", "amount": "100000", "currency": "USD"},
        headers=h,
    ).json()
    assert inv["currency"] == "USD"
    client.put(
        f"/funds/{fid}/portfolio/{inv['id']}/mark", json={"current_value": "150000"}, headers=h
    )
    # before any FX rate: SOI totals equal the raw USD number (no rate → unchanged)
    soi0 = client.get(f"/funds/{fid}/soi", headers=h).json()
    assert soi0["totals"]["current_value"] == "150000.00"

    # set USD→INR = 83; the holding now translates into the fund currency
    client.post(f"/funds/{fid}/fx-rates", json={"currency": "USD", "as_of": "2025-01-01", "rate": "83"}, headers=h)
    soi = client.get(f"/funds/{fid}/soi", headers=h).json()
    hold = soi["holdings"][0]
    assert hold["currency"] == "USD" and hold["native_value"] == "150000.00"
    assert hold["current_value"] == "12450000.00"  # 150,000 × 83
    assert soi["totals"]["cost"] == "8300000.00"    # 100,000 × 83
    # NAV in fund performance is translated too
    perf = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert perf["nav"] == "12450000.00"


def test_metric_alert_pct_change_trigger(client):
    """A period-over-period % change trigger: alert when monthly burn rises
    more than 20% vs the prior period."""
    h = auth_headers(client)
    _, fid = _fund(client, h)
    inv = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "BurnCo", "amount": "1000000"}, headers=h
    ).json()
    # two reported periods: burn 100k → 130k (+30%)
    client.post(f"/funds/{fid}/portfolio/{inv['id']}/kpis",
        json={"period_label": "Q1", "as_of": "2026-01-31", "monthly_burn": "100000", "cash": "600000"}, headers=h)
    client.post(f"/funds/{fid}/portfolio/{inv['id']}/kpis",
        json={"period_label": "Q2", "as_of": "2026-04-30", "monthly_burn": "130000", "cash": "400000"}, headers=h)

    # rule: monthly burn increases (pct_change) by more than 20%
    rule = client.post(f"/funds/{fid}/alert-rules",
        json={"metric": "monthly_burn", "comparator": "gt", "threshold": "20",
              "severity": "high", "basis": "pct_change"}, headers=h).json()
    assert rule["basis"] == "pct_change"

    sig = client.get(f"/funds/{fid}/signals", headers=h).json()
    company = next(c for c in sig["companies"] if c["company_name"] == "BurnCo")
    alerts = [s for s in company["signals"] if s["kind"] == "metric_alert"]
    assert any("up 30.0%" in s["message"] for s in alerts)

    # a >50% threshold would NOT fire (30% change is below it)
    client.post(f"/funds/{fid}/alert-rules",
        json={"metric": "monthly_burn", "comparator": "gt", "threshold": "50", "basis": "pct_change"}, headers=h)
    sig2 = client.get(f"/funds/{fid}/signals", headers=h).json()
    company2 = next(c for c in sig2["companies"] if c["company_name"] == "BurnCo")
    fired = [s for s in company2["signals"] if s["kind"] == "metric_alert"]
    assert len(fired) == 1  # only the >20% rule fired


def test_single_currency_fund_unaffected_by_fx(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    inv = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "INR Co", "amount": "5000000"}, headers=h
    ).json()
    assert inv["currency"] == "INR"  # defaulted to the fund currency
    soi = client.get(f"/funds/{fid}/soi", headers=h).json()
    assert soi["totals"]["cost"] == "5000000.00"
    perf = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert perf["nav"] == "5000000.00"
