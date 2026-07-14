from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


# --- finance / runway ---
def test_runway_computation(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/finance/snapshots",
        json={"period": "2026-04-01", "cash_balance": "12000000", "monthly_burn": "2000000", "revenue": "500000"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/finance/snapshots",
        json={"period": "2026-05-01", "cash_balance": "10000000", "monthly_burn": "2000000"},
        headers=h,
    )
    r = client.get(f"/entities/{eid}/finance/runway", headers=h).json()
    assert r["latest_cash"] == "10000000.00"
    assert r["avg_monthly_burn"] == "2000000.00"
    assert r["runway_months"] == 5.0  # 10,000,000 / 2,000,000


def test_snapshot_upsert_by_period(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/finance/snapshots",
        json={"period": "2026-04-01", "cash_balance": "5000000", "monthly_burn": "1000000"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/finance/snapshots",
        json={"period": "2026-04-01", "cash_balance": "4000000", "monthly_burn": "1000000"},
        headers=h,
    )
    r = client.get(f"/entities/{eid}/finance/runway", headers=h).json()
    assert len(r["snapshots"]) == 1 and r["latest_cash"] == "4000000.00"


# --- statutory registers ---
def test_sbo_and_charges_and_registrations(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    sbo = client.post(
        f"/entities/{eid}/sbo",
        json={"name": "Asha Rao", "pan": "ABCDE1234F", "percentage": "27.5", "nature": "indirect"},
        headers=h,
    )
    assert sbo.status_code == 201
    assert len(client.get(f"/entities/{eid}/sbo", headers=h).json()) == 1

    ch = client.post(
        f"/entities/{eid}/charges",
        json={"holder": "HDFC Bank", "amount": "5000000", "charge_type": "hypothecation", "created_on": "2026-02-01"},
        headers=h,
    )
    cid = ch.json()["id"]
    assert ch.json()["satisfied"] is False
    sat = client.post(f"/charges/{cid}/satisfy", headers=h)
    assert sat.status_code == 200 and sat.json()["satisfied"] is True

    reg = client.post(
        f"/entities/{eid}/registrations",
        json={"kind": "gst", "state": "Karnataka", "number": "29ABCDE1234F1Z5"},
        headers=h,
    )
    assert reg.status_code == 201 and reg.json()["kind"] == "gst"


def test_incorporation_templates_available(client):
    h = auth_headers(client)
    keys = {t["key"] for t in client.get("/document-templates", headers=h).json()}
    assert {"spice_plus", "emoa", "eaoa"} <= keys


# --- alerts / reminders ---
def test_alerts_surface_overdue_compliance(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/compliance/generate", json={"financial_year_end": "2026-03-31"}, headers=h
    )
    # FY2026 obligations are due in 2026; as of "today" some are overdue/upcoming
    alerts = client.get("/alerts?within_days=3650", headers=h).json()
    assert any(a["kind"] == "compliance" for a in alerts)

    swept = client.post("/alerts/sweep?within_days=3650", headers=h).json()
    assert swept["notifications_created"] >= 1
    notes = client.get("/notifications", headers=h).json()
    assert any(n["type"] == "reminder" for n in notes)


def test_gaps_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/finance/snapshots",
            json={"period": "2026-04-01", "cash_balance": "1", "monthly_burn": "1"},
            headers=outsider,
        ).status_code
        == 403
    )
    # alerts are per-user; an unrelated user sees none for this entity
    assert client.get("/alerts", headers=outsider).json() == []
