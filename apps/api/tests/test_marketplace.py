from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_provider_directory_and_filter(client):
    h = auth_headers(client)
    client.post(
        "/service-providers",
        json={"name": "CS Rao & Co", "category": "cs", "firm": "Rao & Co"},
        headers=h,
    )
    client.post(
        "/service-providers",
        json={"name": "ABC Merchant Bankers", "category": "valuer"},
        headers=h,
    )
    allp = client.get("/service-providers", headers=h).json()
    assert len(allp) == 2
    valuers = client.get("/service-providers?category=valuer", headers=h).json()
    assert len(valuers) == 1 and valuers[0]["category"] == "valuer"


def test_engagement_lifecycle(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    pid = client.post(
        "/service-providers", json={"name": "CS Rao & Co", "category": "cs"}, headers=h
    ).json()["id"]

    eng = client.post(
        f"/entities/{eid}/engagements",
        json={"provider_id": pid, "scope": "FY2026 annual ROC filings"},
        headers=h,
    )
    assert eng.status_code == 201
    body = eng.json()
    assert body["provider_name"] == "CS Rao & Co"
    assert body["provider_category"] == "cs"
    assert body["status"] == "requested"
    eng_id = body["id"]

    upd = client.post(
        f"/engagements/{eng_id}/status", json={"status": "in_progress"}, headers=h
    )
    assert upd.status_code == 200 and upd.json()["status"] == "in_progress"

    listed = client.get(f"/entities/{eid}/engagements", headers=h).json()
    assert len(listed) == 1 and listed[0]["status"] == "in_progress"


def test_engagement_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    pid = client.post(
        "/service-providers", json={"name": "CS X", "category": "cs"}, headers=owner
    ).json()["id"]
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/engagements", json={"provider_id": pid}, headers=outsider
        ).status_code
        == 403
    )


def test_data_room_engagement_still_works(client):
    """Regression: marketplace EngagementOut must not shadow the data-room one."""
    h = auth_headers(client)
    eid = _entity(client, h)
    did = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "data": {"company": "Acme"}},
        headers=h,
    ).json()["id"]
    rid = client.post(f"/entities/{eid}/data-rooms", json={"name": "DR"}, headers=h).json()["id"]
    item = client.post(f"/data-rooms/{rid}/items", json={"document_id": did}, headers=h).json()[
        "items"
    ][0]["id"]
    client.post(f"/data-rooms/{rid}/items/{item}/view", headers=h)
    eng = client.get(f"/data-rooms/{rid}/engagement", headers=h).json()
    assert eng and eng[0]["views"] == 1 and "actor" in eng[0]
