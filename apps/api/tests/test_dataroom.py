from tests.conftest import auth_headers


def _entity_with_doc(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    did = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "data": {"company": "Acme"}},
        headers=h,
    ).json()["id"]
    return eid, did


def test_data_room_flow(client):
    h = auth_headers(client)
    eid, did = _entity_with_doc(client, h)

    room = client.post(
        f"/entities/{eid}/data-rooms", json={"name": "Series A diligence"}, headers=h
    )
    assert room.status_code == 201
    rid = room.json()["id"]

    # add the document as an item
    r = client.post(f"/data-rooms/{rid}/items", json={"document_id": did}, headers=h)
    assert r.status_code == 201
    body = r.json()
    assert len(body["items"]) == 1
    item_id = body["items"][0]["id"]
    assert body["items"][0]["document_title"]

    # grant access
    r = client.post(
        f"/data-rooms/{rid}/grants", json={"email": "investor@vc.in"}, headers=h
    )
    assert len(r.json()["grants"]) == 1

    # view the item -> logs engagement and returns content
    v = client.post(f"/data-rooms/{rid}/items/{item_id}/view", headers=h)
    assert v.status_code == 200 and "Acme" in v.json()["content"]
    client.post(f"/data-rooms/{rid}/items/{item_id}/view", headers=h)  # second view

    eng = client.get(f"/data-rooms/{rid}/engagement", headers=h).json()
    assert eng and eng[0]["views"] == 2
    # engagement now carries the "who accessed, when" signal
    row = eng[0]
    assert row["document_name"]  # resolved title, not a raw id
    assert row["first_viewed"] and row["last_viewed"]
    assert row["last_viewed"] >= row["first_viewed"]


def test_data_room_rejects_foreign_document(client):
    h = auth_headers(client)
    eid, _ = _entity_with_doc(client, h)
    rid = client.post(
        f"/entities/{eid}/data-rooms", json={"name": "DR"}, headers=h
    ).json()["id"]
    r = client.post(f"/data-rooms/{rid}/items", json={"document_id": "nope"}, headers=h)
    assert r.status_code == 400


def test_data_room_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid, _ = _entity_with_doc(client, owner)
    rid = client.post(
        f"/entities/{eid}/data-rooms", json={"name": "DR"}, headers=owner
    ).json()["id"]
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/data-rooms/{rid}", headers=outsider).status_code == 403
