import datetime as dt

from app.clock import today_ist
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Perf Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "carry_pct": "0.20", "hurdle_pct": "0"},
        headers=h,
    ).json()["id"]
    return fid


def test_performance_multiples_and_xirr(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h)
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "1.0"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)

    # invest 8M; remaining position marked at 4M after the distribution below
    inv = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "PortCo", "amount": "8000000"},
        headers=h,
    ).json()["id"]
    client.put(
        f"/funds/{fid}/portfolio/{inv}/mark", json={"current_value": "4000000"}, headers=h
    )

    # distribute 12M profit one year out (hurdle 0 -> 10M ROC + 2M split 80/20)
    later = (today_ist() + dt.timedelta(days=365)).isoformat()
    client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "12000000", "kind": "profit", "date": later},
        headers=h,
    )

    p = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert p["paid_in"] == "10000000.00"
    assert p["distributed"] == "11600000.00"   # 12M less 400k carry
    assert p["nav"] == "4000000.00"
    assert p["positions_marked"] == 1
    assert p["dpi"] == "1.16"
    assert p["rvpi"] == "0.40"
    assert p["tvpi"] == "1.56"
    # net -6M today, +11.6M in one year -> ~93.3% money-weighted return
    assert p["xirr_pct"] is not None and 90 < p["xirr_pct"] < 97


def test_performance_empty_fund(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    p = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert p["paid_in"] == "0.00" and p["dpi"] is None and p["xirr_pct"] is None


def test_unmarked_positions_held_at_cost(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "X", "amount": "5000000"}, headers=h
    )
    p = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert p["nav"] == "5000000.00" and p["positions_at_cost"] == 1


def test_management_fee_accrual(client):
    h = auth_headers(client)
    # committed basis (default 2%): 10M commitment for one year -> 200,000
    fid = _fund(client, h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h)
    later = (today_ist() + dt.timedelta(days=365)).isoformat()
    p = client.get(f"/funds/{fid}/performance?as_of={later}", headers=h).json()
    assert p["management_fee_accrued"] == "200000.00"
    assert p["fee_basis"] == "committed"

    # drawn basis: fee accrues only on paid-in capital
    tid = client.post("/tenants", json={"name": "GP2", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Drawn Fund", "type": "fund"}, headers=h
    ).json()["id"]
    fid2 = client.post(
        f"/entities/{eid}/fund",
        json={"sebi_category": "II", "mgmt_fee_pct": "0.02", "fee_basis": "drawn"},
        headers=h,
    ).json()["id"]
    client.post(f"/funds/{fid2}/lps", json={"name": "LP", "commitment": "10000000"}, headers=h)
    call = client.post(f"/funds/{fid2}/capital-calls", json={"pct": "0.5"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid2}/drawdown-notices/{n['id']}/pay", headers=h)
    p = client.get(f"/funds/{fid2}/performance?as_of={later}", headers=h).json()
    assert p["management_fee_accrued"] == "100000.00"  # 2% on 5M drawn for a year


def test_fee_charging_into_capital_accounts(client, monkeypatch):
    import app.services.fund as fundsvc

    h = auth_headers(client)
    fid = _fund(client, h)  # 2% committed basis (default)
    client.post(f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h)
    # a year passes (charging is clamped to "today", so move today itself)
    later_date = today_ist() + dt.timedelta(days=365)
    monkeypatch.setattr(fundsvc, "today_ist", lambda: later_date)
    later = later_date.isoformat()

    r = client.post(f"/funds/{fid}/fees/charge?as_of={later}", headers=h).json()
    assert r["charged"] == "200000.00" and len(r["charges"]) == 1

    # append-only + idempotent: a second run for the same as_of charges nothing
    again = client.post(f"/funds/{fid}/fees/charge?as_of={later}", headers=h).json()
    assert again["charged"] == "0.00" and again["charges"] == []

    acc = client.get(f"/funds/{fid}/capital-accounts", headers=h).json()
    assert acc["accounts"][0]["fees_charged"] == "200000.00"
    assert acc["totals"]["fees_charged"] == "200000.00"
    assert len(client.get(f"/funds/{fid}/fees", headers=h).json()) == 1


def test_units_and_nav_per_unit(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h)
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "1.0"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)
    inv = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "PortCo", "amount": "10000000"}, headers=h
    ).json()["id"]
    client.put(f"/funds/{fid}/portfolio/{inv}/mark", json={"current_value": "15000000"}, headers=h)

    # 10M paid-in at ₹10 par -> 1,000,000 units; NAV 15M -> ₹15/unit
    p = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert p["units_outstanding"] == "1000000.00"
    assert p["nav_per_unit"] == "15.0000"
    acc = client.get(f"/funds/{fid}/capital-accounts", headers=h).json()
    assert acc["accounts"][0]["units"] == "1000000.00"

    # units + fees flow into the LP statement
    lp_id = acc["accounts"][0]["lp_id"]
    doc = client.post(f"/funds/{fid}/lps/{lp_id}/statement", headers=h).json()
    assert "Units held:            1000000.00" in doc["content"]
    assert "NAV per unit: INR 15.0000" in doc["content"]


def test_lp_portal_includes_performance(client):
    gp = auth_headers(client, email="gp@perf.in")
    fid = _fund(client, gp)
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "Anita LP", "email": "anita@lp.in", "commitment": "10000000"},
        headers=gp,
    )
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.5"}, headers=gp).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=gp)

    anita = auth_headers(client, email="anita@lp.in")
    portal = client.get("/portal", headers=anita).json()
    perf = portal["funds"][0]["performance"]
    assert perf["paid_in"] == "5000000.00" and perf["tvpi"] == "0.00"
