"""Ledgy-parity employee equity views: per-grant value summary + vesting
schedule (FR-D-2 / FR-K) driving the grant detail view and equity hero card."""
import datetime

from app.models.esop import Grant
from app.services.esop import grant_schedule, grant_unit_value
from tests.conftest import auth_headers


def _company(client, h, name="Led"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


def _grant(client, h, eid, emp_email="emp@led.in", qty=4800, gtype="option", strike="10"):
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Emp L", "type": "employee", "email": emp_email},
        headers=h,
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=h
    ).json()["id"]
    body = {
        "scheme_id": scheme, "stakeholder_id": emp, "quantity": qty, "grant_type": gtype,
        "exercise_price": strike, "grant_date": "2025-01-01", "cliff_months": 12, "total_months": 48,
    }
    if gtype == "rsa":
        body["security_class_id"] = sc
    gid = client.post(f"/entities/{eid}/esop/grants", json=body, headers=h).json()["id"]
    return sc, emp, gid


# --- unit fns ---
def test_grant_unit_value():
    opt = Grant(grant_type="option", exercise_price=30)
    assert grant_unit_value(opt, 100) == 70  # intrinsic FMV - strike
    assert grant_unit_value(opt, 20) == 0  # underwater -> floored
    rsu = Grant(grant_type="rsu", exercise_price=0)
    assert grant_unit_value(rsu, 100) == 100  # full FMV
    assert grant_unit_value(opt, None) is None


def test_grant_schedule_events():
    g = Grant(grant_type="option", grant_date=datetime.date(2025, 1, 1), cliff_months=12, total_months=48, quantity=4800)
    sched = grant_schedule(g, datetime.date(2026, 1, 1))
    # cliff event at month 12 vests 12/48 = 1200 at once
    first = sched[0]
    assert first["date"] == "2026-01-01" and first["units"] == 1200 and first["cumulative"] == 1200
    assert first["past"] is True
    # then monthly 100-unit events, all future relative to as_of
    assert sched[1]["units"] == 100 and sched[1]["past"] is False
    # last event reaches the full grant
    assert sched[-1]["cumulative"] == 4800
    # every event is exactly one of past/future, dates ascending
    dates = [e["date"] for e in sched]
    assert dates == sorted(dates)


# --- portal grant detail (option) ---
def test_portal_grant_detail_option(client):
    h = auth_headers(client)
    eid = _company(client, h)
    _sc, _emp, gid = _grant(client, h, eid, qty=4800, gtype="option", strike="10")
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "50", "valuation_date": "2026-01-01"},
        headers=h,
    )
    emp = auth_headers(client, email="emp@led.in")
    d = client.get(f"/portal/grants/{gid}/detail", headers=emp).json()
    # at 2026-07-16, ~18 months vested of 48 -> 1800 vested, none exercised
    assert d["vested"] == 1800
    assert d["exercised"] == 0
    # unit value = intrinsic 50 - 10 = 40; today's value = vested(unexercised) 1800 × 40
    assert d["unit_value"] == "40.00"
    assert d["today_value"] == "72000.00"
    assert d["max_potential_value"] == "192000.00"  # 4800 × 40
    assert d["segments"] == {"exercised": 0, "vested": 1800, "unvested": 3000}
    # timeline schedule present with a Today split
    assert len(d["schedule"]) > 0
    assert any(e["past"] for e in d["schedule"]) and any(not e["past"] for e in d["schedule"])


def test_portal_grant_detail_rsa_segments(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Rz")
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "50", "valuation_date": "2025-01-01"},
        headers=h,
    )
    _sc, _emp, gid = _grant(client, h, eid, emp_email="rsa@led.in", qty=2000, gtype="rsa", strike="0")
    emp = auth_headers(client, email="rsa@led.in")
    d = client.get(f"/portal/grants/{gid}/detail", headers=emp).json()
    # RSA: shares issued upfront; the bar splits vested (unlocked) vs unvested
    assert d["segments"]["exercised"] == 0
    assert d["segments"]["vested"] + d["segments"]["unvested"] == 2000
    # full FMV per unit (no strike)
    assert d["unit_value"] == "50.00"


def test_grant_detail_not_yours_404(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Priv")
    _sc, _emp, gid = _grant(client, h, eid, emp_email="owner@led.in")
    other = auth_headers(client, email="stranger@led.in")
    assert client.get(f"/portal/grants/{gid}/detail", headers=other).status_code == 404


def test_portal_grant_carries_value_fields(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Hero")
    _grant(client, h, eid, emp_email="hero@led.in", qty=4800)
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "50", "valuation_date": "2026-01-01"},
        headers=h,
    )
    portal = client.get("/portal", headers=auth_headers(client, email="hero@led.in")).json()
    g = portal["equity_grants"][0]
    assert g["grant_type"] == "option"
    assert g["today_value"] is not None
    assert g["max_potential_value"] == "192000.00"
    assert set(g["segments"]) == {"exercised", "vested", "unvested"}
