from tests.conftest import auth_headers

CONTACT = "founder@portco.in"


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    iid = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "Acme", "amount": "10000000"}, headers=h
    ).json()["id"]
    return fid, iid


def _request(client, h, fid, iid, due="2026-01-01"):
    return client.post(
        f"/funds/{fid}/portfolio/{iid}/kpi-requests",
        json={"period_label": "FY26 Q2", "as_of": "2026-09-30",
              "due_date": due, "contact_email": CONTACT},
        headers=h,
    ).json()


def test_full_request_submit_accept_cycle(client):
    h = auth_headers(client)
    fid, iid = _setup(client, h)
    # contact signs up so the notification lands somewhere
    contact_h = auth_headers(client, email=CONTACT)

    reqs = _request(client, h, fid, iid)
    assert len(reqs) == 1
    r = reqs[0]
    assert r["status"] == "pending" and r["overdue"] is True  # past due date
    assert r["company_name"] == "Acme"

    # contact sees it in their portal (with fund + company context) and got a notification
    portal = client.get("/portal", headers=contact_h).json()
    assert len(portal["kpi_requests"]) == 1
    assert portal["kpi_requests"][0]["company_name"] == "Acme"
    notifs = client.get("/notifications", headers=contact_h).json()
    assert any(n["type"] == "kpi_request" for n in notifs)

    # contact submits values
    sub = client.post(
        f"/portal/kpi-requests/{r['id']}/submit",
        json={"revenue": "1500000", "cash": "24000000", "monthly_burn": "3000000", "headcount": 26},
        headers=contact_h,
    )
    assert sub.status_code == 200 and sub.json()["status"] == "submitted"
    # double submit blocked
    assert client.post(
        f"/portal/kpi-requests/{r['id']}/submit", json={}, headers=contact_h
    ).status_code == 409

    # GP accepts -> a PortfolioKPI period exists and monitoring reflects it
    acc = client.post(f"/funds/{fid}/kpi-requests/{r['id']}/accept", headers=h).json()
    assert acc[0]["status"] == "accepted" and acc[0]["kpi_id"]
    mon = client.get(f"/funds/{fid}/portfolio-monitoring", headers=h).json()
    acme = mon["companies"][0]
    assert acme["latest"]["revenue"] == "1500000.00"
    assert acme["runway_months"] == 8.0
    # accepted request no longer shows in the contact's portal
    assert client.get("/portal", headers=contact_h).json()["kpi_requests"] == []


def test_reopen_for_resubmission(client):
    h = auth_headers(client)
    fid, iid = _setup(client, h)
    contact_h = auth_headers(client, email=CONTACT)
    r = _request(client, h, fid, iid)[0]
    client.post(f"/portal/kpi-requests/{r['id']}/submit",
                json={"revenue": "999"}, headers=contact_h)
    # GP reopens (values look wrong) -> contact can submit again
    re = client.post(f"/funds/{fid}/kpi-requests/{r['id']}/reopen", headers=h).json()
    assert re[0]["status"] == "pending"
    ok = client.post(f"/portal/kpi-requests/{r['id']}/submit",
                     json={"revenue": "1500000"}, headers=contact_h)
    assert ok.status_code == 200
    # accepting a pending (unsubmitted) request is blocked
    r2 = _request(client, h, fid, iid, due=None)[0]
    assert client.post(f"/funds/{fid}/kpi-requests/{r2['id']}/accept", headers=h).status_code == 409


def test_submit_scoped_to_contact_email(client):
    h = auth_headers(client)
    fid, iid = _setup(client, h)
    r = _request(client, h, fid, iid)[0]
    stranger = auth_headers(client, email="stranger2@x.in")
    assert client.post(
        f"/portal/kpi-requests/{r['id']}/submit", json={"revenue": "1"}, headers=stranger
    ).status_code == 404
    # contact_email is remembered on the investment for the next request
    pf = client.get(f"/funds/{fid}/portfolio", headers=h).json()
    assert pf[0]["contact_email"] == CONTACT
