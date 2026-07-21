"""Scheduled KPI requests (on-read materialisation) and the no-login
token-link submission flow (Visible-style frictionless founder experience)."""
import datetime

from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def _inv(client, h, fid, name="Acme"):
    return client.post(
        f"/funds/{fid}/portfolio", json={"company_name": name, "amount": "10000000"}, headers=h
    ).json()["id"]


def _expected_quarter(today):
    qstart_month = ((today.month - 1) // 3) * 3 + 1
    end = datetime.date(today.year, qstart_month, 1) - datetime.timedelta(days=1)
    fy = end.year + 1 if end.month >= 4 else end.year
    qn = (end.month - 1) // 3 if end.month >= 4 else 4
    return f"FY{fy % 100} Q{qn}", end


def test_schedule_materialises_last_completed_quarter(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid)

    s = client.put(
        f"/funds/{fid}/portfolio/{iid}/kpi-schedule",
        json={"cadence": "quarterly", "contact_email": "cfo@acme.in"},
        headers=h,
    )
    assert s.status_code == 200 and s.json()["cadence"] == "quarterly"

    label, end = _expected_quarter(datetime.date.today())
    reqs = client.get(f"/funds/{fid}/kpi-requests", headers=h).json()
    assert len(reqs) == 1
    assert reqs[0]["period_label"] == label
    assert reqs[0]["as_of"] == end.isoformat()
    assert reqs[0]["contact_email"] == "cfo@acme.in"
    assert reqs[0]["token"]  # no-login link token minted

    # idempotent: a second read creates nothing new
    assert len(client.get(f"/funds/{fid}/kpi-requests", headers=h).json()) == 1

    # deleting the schedule stops materialisation
    client.delete(f"/funds/{fid}/portfolio/{iid}/kpi-schedule", headers=h)
    assert client.get(f"/funds/{fid}/kpi-schedules", headers=h).json() == []


def test_schedule_requires_contact(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid)
    r = client.put(
        f"/funds/{fid}/portfolio/{iid}/kpi-schedule", json={"cadence": "monthly"}, headers=h
    )
    assert r.status_code == 400  # no reporting contact on the company yet


def test_no_login_token_submission(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid)
    client.post(
        f"/funds/{fid}/portfolio/{iid}/kpi-requests",
        json={"period_label": "FY27 Q1", "as_of": "2026-06-30", "contact_email": "cfo@acme.in"},
        headers=h,
    )
    token = client.get(f"/funds/{fid}/kpi-requests", headers=h).json()[0]["token"]

    # public info page — no auth header at all
    info = client.get(f"/public/kpi-requests/{token}")
    assert info.status_code == 200
    assert info.json()["company_name"] == "Acme" and info.json()["status"] == "pending"
    assert client.get("/public/kpi-requests/not-a-token").status_code == 404

    # public submit, then 409 on resubmit
    sub = client.post(
        f"/public/kpi-requests/{token}/submit",
        json={"revenue": "1500000", "cash": "20000000", "monthly_burn": "1000000", "headcount": 12},
    )
    assert sub.status_code == 200 and sub.json()["status"] == "submitted"
    assert client.post(f"/public/kpi-requests/{token}/submit", json={}).status_code == 409

    # the GP sees the submitted values and accepts them into a KPI period
    reqs = client.get(f"/funds/{fid}/kpi-requests", headers=h).json()
    assert reqs[0]["status"] == "submitted" and reqs[0]["revenue"] == "1500000.00"
    rid = reqs[0]["id"]
    acc = client.post(f"/funds/{fid}/kpi-requests/{rid}/accept", headers=h)
    assert acc.json()[0]["status"] == "accepted"
