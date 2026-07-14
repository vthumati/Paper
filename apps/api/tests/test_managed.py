from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_subscription_unique_per_entity(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    r = client.post(
        f"/entities/{eid}/admin-subscription", json={"tier": "growth"}, headers=h
    )
    assert r.status_code == 201 and r.json()["tier"] == "growth"
    dup = client.post(
        f"/entities/{eid}/admin-subscription", json={"tier": "basic"}, headers=h
    )
    assert dup.status_code == 409


def test_touchpoints_and_audits(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    sid = client.post(
        f"/entities/{eid}/admin-subscription", json={"tier": "scale"}, headers=h
    ).json()["id"]

    tp = client.post(
        f"/admin-subscriptions/{sid}/touchpoints",
        json={"date": "2026-06-30", "attendee": "Paralegal", "summary": "Q1 review"},
        headers=h,
    )
    assert tp.status_code == 201

    audit = client.post(
        f"/admin-subscriptions/{sid}/audits",
        json={"type": "corporate_audit", "period_label": "FY2026"},
        headers=h,
    )
    assert audit.status_code == 201 and audit.json()["status"] == "scheduled"
    aid = audit.json()["id"]

    done = client.post(
        f"/admin-subscriptions/{sid}/audits/{aid}/status",
        json={"status": "completed", "findings": "All registers up to date."},
        headers=h,
    )
    assert done.status_code == 200 and done.json()["status"] == "completed"

    # subscription view nests touchpoints + audits
    sub = client.get(f"/entities/{eid}/admin-subscription", headers=h).json()
    assert len(sub["touchpoints"]) == 1
    assert len(sub["audits"]) == 1 and sub["audits"][0]["findings"] == "All registers up to date."


def test_managed_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/admin-subscription", json={"tier": "basic"}, headers=outsider
        ).status_code
        == 403
    )
