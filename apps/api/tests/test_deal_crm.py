from tests.conftest import auth_headers


def _deal(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    did = client.post(
        f"/funds/{fid}/deals", json={"company_name": "RocketCo", "sector": "SaaS"}, headers=h
    ).json()["id"]
    return fid, did


def test_contacts_and_activities(client):
    h = auth_headers(client)
    _, did = _deal(client, h)

    crm = client.get(f"/deals/{did}/crm", headers=h).json()
    assert crm == {"strength": 0, "contacts": [], "activities": []}

    crm = client.post(
        f"/deals/{did}/contacts",
        json={"name": "Asha Rao", "role": "Founder", "email": "asha@rocketco.in"},
        headers=h,
    ).json()
    assert len(crm["contacts"]) == 1
    assert crm["contacts"][0]["role"] == "Founder"

    # activities come back newest-first by occurred_on
    client.post(f"/deals/{did}/activities", headers=h,
                json={"kind": "meeting", "body": "Intro call", "occurred_on": "2026-06-01"})
    crm = client.post(f"/deals/{did}/activities", headers=h,
                      json={"kind": "note", "body": "Sent deck", "occurred_on": "2026-07-01"}).json()
    assert [a["body"] for a in crm["activities"]] == ["Sent deck", "Intro call"]
    assert crm["activities"][0]["kind"] == "note"


def test_activity_defaults_date_and_scopes_to_deal(client):
    h = auth_headers(client)
    fid, did = _deal(client, h)
    # no occurred_on -> defaults to today (present, non-null)
    crm = client.post(f"/deals/{did}/activities", json={"body": "Quick note"}, headers=h).json()
    assert crm["activities"][0]["occurred_on"] is not None
    assert crm["activities"][0]["kind"] == "note"  # default kind
    # unknown deal -> 404
    assert client.get("/deals/nope/crm", headers=h).status_code == 404


def test_crm_write_requires_role(client):
    h = auth_headers(client)
    _, did = _deal(client, h)
    viewer = auth_headers(client, email="viewer3@x.in")
    r = client.post(f"/deals/{did}/contacts", json={"name": "X"}, headers=viewer)
    assert r.status_code in (403, 404)
