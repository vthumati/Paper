from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_meeting_with_minutes_and_resolution(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    mtg = client.post(
        f"/entities/{eid}/meetings",
        json={"type": "board", "title": "Board Meeting Q1", "date": "2026-04-15", "quorum": 2},
        headers=h,
    )
    assert mtg.status_code == 201
    mid = mtg.json()["id"]

    res = client.post(
        f"/entities/{eid}/resolutions",
        json={
            "meeting_id": mid,
            "type": "board",
            "title": "Approve seed allotment",
            "text": "RESOLVED THAT the company allot 100,000 CCPS to Seed Fund.",
        },
        headers=h,
    )
    assert res.status_code == 201
    rid = res.json()["id"]

    # record minutes -> meeting held, resolution nested in meeting view
    client.post(
        f"/meetings/{mid}/minutes",
        json={"minutes": "Quorum present; resolution discussed.", "status": "held"},
        headers=h,
    )
    m = client.get(f"/meetings/{mid}", headers=h).json()
    assert m["status"] == "held"
    assert len(m["resolutions"]) == 1 and m["resolutions"][0]["id"] == rid


def test_resolution_pass_and_generate_document(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    rid = client.post(
        f"/entities/{eid}/resolutions",
        json={"type": "special", "title": "Amend AoA", "text": "RESOLVED THAT the AoA be amended."},
        headers=h,
    ).json()["id"]

    passed = client.post(f"/resolutions/{rid}/status", json={"status": "passed"}, headers=h)
    assert passed.status_code == 200
    assert passed.json()["status"] == "passed" and passed.json()["passed_date"]

    doc = client.post(f"/resolutions/{rid}/document", headers=h)
    assert doc.status_code == 201
    assert "BOARD RESOLUTION" in doc.json()["content"]
    assert "AoA be amended" in doc.json()["content"]
    # the document is linked back to the resolution
    listed = client.get(f"/entities/{eid}/resolutions", headers=h).json()
    assert listed[0]["document_id"] == doc.json()["id"]


def test_governance_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/meetings",
            json={"type": "board", "title": "X", "date": "2026-01-01"},
            headers=outsider,
        ).status_code
        == 403
    )
