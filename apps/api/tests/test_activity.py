from tests.conftest import auth_headers


def test_audit_log_records_mutations(client):
    h = auth_headers(client)
    # a few mutating actions
    client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h)

    entries = client.get("/audit-log", headers=h).json()
    # the POST /tenants should be recorded against this user
    assert any(e["method"] == "POST" and e["path"] == "/tenants" for e in entries)
    # GET requests are not audited
    assert all(e["method"] != "GET" for e in entries)


def test_audit_log_is_per_user(client):
    a = auth_headers(client, email="a@x.in")
    client.post("/tenants", json={"name": "A Co", "type": "company"}, headers=a)
    b = auth_headers(client, email="b@x.in")
    # b has not created anything -> empty (signup/login are b's only mutations, by b)
    b_entries = client.get("/audit-log", headers=b).json()
    assert all(e["path"] != "/tenants" or e["method"] != "POST" for e in b_entries) or True
    # a sees their own tenant creation
    a_entries = client.get("/audit-log", headers=a).json()
    assert any(e["path"] == "/tenants" for e in a_entries)
    # b must not see a's tenant-creation entry
    assert not any(e["path"] == "/tenants" and e["method"] == "POST" for e in b_entries)


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_compliance_generation_creates_notification(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    assert client.get("/notifications", headers=h).json() == []

    client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    )
    notes = client.get("/notifications", headers=h).json()
    assert len(notes) == 1
    assert notes[0]["type"] == "compliance" and "generated" in notes[0]["title"].lower()
    assert notes[0]["read"] is False


def test_round_close_foreign_creates_fc_gpr_notification(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Eq", "kind": "ccps"}, headers=h
    ).json()["id"]
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Seed", "price_per_share": "100", "security_class_id": sc},
        headers=h,
    ).json()["id"]
    c = client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Overseas VC", "amount": "1000000", "is_foreign": True},
        headers=h,
    ).json()["id"]
    client.post(f"/rounds/{rid}/commitments/{c}/status", json={"status": "funded"}, headers=h)
    client.post(f"/rounds/{rid}/close", headers=h)

    notes = client.get("/notifications?unread_only=true", headers=h).json()
    assert any(n["type"] == "compliance" and "FC-GPR" in n["title"] for n in notes)


def test_mark_notifications_read(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/compliance/generate",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    )
    nid = client.get("/notifications", headers=h).json()[0]["id"]
    assert client.post(f"/notifications/{nid}/read", headers=h).json()["read"] is True
    assert client.get("/notifications?unread_only=true", headers=h).json() == []
