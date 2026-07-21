from app.clock import today_ist
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    return eid, fid


def test_relationship_strength_from_attributed_activities(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    did = client.post(
        f"/funds/{fid}/deals",
        json={"company_name": "Acme", "amount": "10000000", "source": "IIT network"},
        headers=h,
    ).json()["id"]
    cid = client.post(
        f"/deals/{did}/contacts", json={"name": "Asha Rao", "role": "Founder"}, headers=h
    ).json()["contacts"][0]["id"]

    today = today_ist().isoformat()
    # two recent touches attributed to Asha, one unattributed note
    client.post(f"/deals/{did}/activities", headers=h,
                json={"kind": "meeting", "body": "Pitch", "occurred_on": today, "contact_id": cid})
    client.post(f"/deals/{did}/activities", headers=h,
                json={"kind": "call", "body": "Follow-up", "occurred_on": today, "contact_id": cid})
    crm = client.post(f"/deals/{did}/activities", headers=h,
                      json={"kind": "note", "body": "Internal note", "occurred_on": today}).json()

    # contact: 2 touches today -> freq 30 + recency 40 = 70; deal: 3 touches -> 45 + 40 = 85
    assert crm["contacts"][0]["strength"] == 70
    assert crm["strength"] == 85
    assert crm["activities"][0]["contact_id"] is None  # newest-first; the note

    # attributing to a contact from another deal is rejected
    r = client.post(f"/deals/{did}/activities", headers=h,
                    json={"kind": "note", "body": "x", "contact_id": "nope"})
    assert r.status_code == 404


def test_followup_flag_and_tasks_hub(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    did = client.post(
        f"/funds/{fid}/deals", json={"company_name": "BrickMart"}, headers=h
    ).json()["id"]

    d = client.put(f"/deals/{did}/followup", json={"on": "2026-01-01"}, headers=h).json()
    assert d["next_followup_on"] == "2026-01-01"

    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    mine = [t for t in tasks if t["kind"] == "deal_followup"]
    assert len(mine) == 1 and "BrickMart" in mine[0]["title"] and mine[0]["severity"] == "red"

    # clearing the date clears the task
    client.put(f"/deals/{did}/followup", json={"on": None}, headers=h)
    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    assert not [t for t in tasks if t["kind"] == "deal_followup"]


def test_deal_source_persists(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    client.post(f"/funds/{fid}/deals",
                json={"company_name": "GreenGrid", "source": "Accel referral"}, headers=h)
    deals = client.get(f"/funds/{fid}/deals", headers=h).json()
    assert deals[0]["source"] == "Accel referral"
    assert deals[0]["next_followup_on"] is None
