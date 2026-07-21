from app.clock import today_ist
from app.services import tasks as tasks_svc
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    return eid, fid


def _prospect(client, h, fid, name="SIDBI"):
    s = client.post(
        f"/funds/{fid}/prospects",
        json={"name": name, "kind": "institutional", "target_commitment": "50000000"},
        headers=h,
    ).json()
    return s["prospects"][0]["id"]


def test_prospect_activity_timeline_and_strength(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    pid = _prospect(client, h, fid)

    today = today_ist().isoformat()
    client.post(f"/funds/{fid}/prospects/{pid}/activities", headers=h,
                json={"kind": "meeting", "body": "Intro meeting", "occurred_on": today})
    crm = client.post(f"/funds/{fid}/prospects/{pid}/activities", headers=h,
                      json={"kind": "email", "body": "Sent deck", "occurred_on": today}).json()
    # 2 touches today -> freq 30 + recency 40
    assert crm["strength"] == 70
    assert [a["kind"] for a in crm["activities"]] == ["email", "meeting"]

    crm2 = client.get(f"/funds/{fid}/prospects/{pid}/crm", headers=h).json()
    assert crm2["strength"] == 70 and len(crm2["activities"]) == 2
    # unknown prospect -> 404
    assert client.get(f"/funds/{fid}/prospects/nope/crm", headers=h).status_code == 404


def test_prospect_followup_surfaces_in_tasks(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    pid = _prospect(client, h, fid, "Accel FoF")

    s = client.put(f"/funds/{fid}/prospects/{pid}/followup", json={"on": "2026-01-01"}, headers=h).json()
    assert s["prospects"][0]["next_followup_on"] == "2026-01-01"

    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    mine = [t for t in tasks if t["kind"] == "lp_followup"]
    assert len(mine) == 1 and "Accel FoF" in mine[0]["title"] and mine[0]["severity"] == "red"

    # converting the prospect ends the chase — the task disappears
    client.post(f"/funds/{fid}/prospects/{pid}/convert", json={"commitment": "50000000"}, headers=h)
    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    assert not [t for t in tasks if t["kind"] == "lp_followup"]


def test_stale_deal_task(client, monkeypatch):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    did = client.post(f"/funds/{fid}/deals", json={"company_name": "SlowCo"}, headers=h).json()["id"]

    # fresh deal is not stale at the real threshold
    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    assert not [t for t in tasks if t["kind"] == "deal_stale"]

    # shrink the threshold so today's deal counts as parked too long
    monkeypatch.setattr(tasks_svc, "STALE_DEAL_DAYS", -1)
    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    stale = [t for t in tasks if t["kind"] == "deal_stale"]
    assert len(stale) == 1 and "SlowCo" in stale[0]["title"] and stale[0]["severity"] == "amber"

    # passed deals are never stale
    client.post(f"/deals/{did}/stage", json={"stage": "passed"}, headers=h)
    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()["tasks"]
    assert not [t for t in tasks if t["kind"] == "deal_stale"]
