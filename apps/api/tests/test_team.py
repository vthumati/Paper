from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_add_and_list_team(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    m = client.post(
        f"/entities/{eid}/team",
        json={"name": "Asha Rao", "email": "asha@acme.in", "title": "Engineer"},
        headers=h,
    )
    assert m.status_code == 201 and m.json()["status"] == "active"
    assert len(client.get(f"/entities/{eid}/team", headers=h).json()) == 1


def test_onboard_creates_stakeholder_and_documents(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    mid = client.post(
        f"/entities/{eid}/team",
        json={"name": "Asha Rao", "title": "Engineer"},
        headers=h,
    ).json()["id"]

    res = client.post(f"/team/{mid}/onboard", headers=h).json()
    assert len(res["documents"]) == 3
    assert res["stakeholder_id"]

    # the member is now linked to a cap-table stakeholder (ESOP-eligible)
    member = client.get(f"/entities/{eid}/team", headers=h).json()[0]
    assert member["stakeholder_id"] == res["stakeholder_id"]
    sh = client.get(f"/entities/{eid}/stakeholders", headers=h).json()
    assert any(s["id"] == res["stakeholder_id"] and s["type"] == "employee" for s in sh)

    # the 3 HR docs are in the file cabinet
    files = client.get(f"/entities/{eid}/files", headers=h).json()
    titles = " ".join(f["title"] for f in files)
    assert "Offer Letter" in titles and "IP Assignment" in titles and "Non-Disclosure" in titles

    # and the employee can immediately receive an ESOP grant
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 10000}, headers=h
    ).json()["id"]
    grant = client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": res["stakeholder_id"], "quantity": 1000, "exercise_price": "10", "grant_date": "2026-01-01"},
        headers=h,
    )
    assert grant.status_code == 201


def test_generate_single_hr_document(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    mid = client.post(
        f"/entities/{eid}/team", json={"name": "Asha Rao", "title": "Engineer"}, headers=h
    ).json()["id"]
    doc = client.post(f"/team/{mid}/documents", json={"template_key": "offer_letter"}, headers=h)
    assert doc.status_code == 201
    assert "OFFER LETTER" in doc.json()["content"] and "Asha Rao" in doc.json()["content"]
    # non-HR template rejected
    bad = client.post(f"/team/{mid}/documents", json={"template_key": "sha"}, headers=h)
    assert bad.status_code == 400


def test_status_update(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    mid = client.post(f"/entities/{eid}/team", json={"name": "X"}, headers=h).json()["id"]
    r = client.post(f"/team/{mid}/status", json={"status": "exited", "left_on": "2026-06-30"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "exited" and r.json()["left_on"] == "2026-06-30"


def test_team_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.post(f"/entities/{eid}/team", json={"name": "X"}, headers=outsider).status_code == 403
