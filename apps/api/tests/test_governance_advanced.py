from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_director_register_and_resignation(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    d = client.post(
        f"/entities/{eid}/directors",
        json={"name": "A. Rao", "din": "01234567", "designation": "managing_director", "appointed_on": "2026-01-01"},
        headers=h,
    )
    assert d.status_code == 201 and d.json()["status"] == "active"
    did = d.json()["id"]
    assert len(client.get(f"/entities/{eid}/directors", headers=h).json()) == 1

    r = client.post(f"/directors/{did}/resign", json={"resigned_on": "2026-06-30"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "resigned"
    assert r.json()["resigned_on"] == "2026-06-30"


def test_director_indemnification_document(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    did = client.post(
        f"/entities/{eid}/directors",
        json={"name": "A. Rao", "designation": "director", "appointed_on": "2026-01-01"},
        headers=h,
    ).json()["id"]
    doc = client.post(f"/directors/{did}/indemnification", headers=h)
    assert doc.status_code == 201
    assert "INDEMNIFICATION" in doc.json()["content"] and "A. Rao" in doc.json()["content"]


def test_meeting_agenda_and_notice(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    mid = client.post(
        f"/entities/{eid}/meetings",
        json={"type": "board", "title": "Q1 Board", "date": "2026-04-15", "quorum": 2, "location": "HQ"},
        headers=h,
    ).json()["id"]
    client.post(f"/meetings/{mid}/agenda", json={"title": "Approve financials", "order_index": 1}, headers=h)
    m = client.post(f"/meetings/{mid}/agenda", json={"title": "Approve ESOP top-up", "order_index": 2}, headers=h)
    assert len(m.json()["agenda_items"]) == 2

    notice = client.post(f"/meetings/{mid}/notice", headers=h)
    assert notice.status_code == 201
    content = notice.json()["content"]
    assert "NOTICE OF BOARD MEETING" in content
    assert "Approve financials" in content and "Approve ESOP top-up" in content
    # the notice document is linked to the meeting
    assert client.get(f"/meetings/{mid}", headers=h).json()["notice_document_id"] == notice.json()["id"]


def test_governance_advanced_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/directors",
            json={"name": "X", "designation": "director", "appointed_on": "2026-01-01"},
            headers=outsider,
        ).status_code
        == 403
    )
