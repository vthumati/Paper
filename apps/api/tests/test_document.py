from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post(
        "/tenants", json={"name": "Acme", "type": "company"}, headers=h
    ).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"},
        headers=h,
    ).json()["id"]


def test_list_templates(client):
    h = auth_headers(client)
    keys = {t["key"] for t in client.get("/document-templates", headers=h).json()}
    assert {"board_resolution", "share_certificate", "sha", "pas4"} <= keys


def test_generate_document_merges_data(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    doc = client.post(
        f"/entities/{eid}/documents",
        json={
            "template_key": "board_resolution",
            "data": {
                "company": "Acme Pvt Ltd",
                "date": "2026-03-01",
                "resolution_text": "the company shall allot 2000 equity shares.",
                "signatory": "A. Founder",
            },
        },
        headers=h,
    )
    assert doc.status_code == 201
    body = doc.json()
    assert body["status"] == "generated"
    assert body["current_version"] == 1
    assert "Acme Pvt Ltd" in body["content"]
    assert "allot 2000 equity shares" in body["content"]


def test_regenerate_creates_new_version(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    did = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "data": {"company": "Acme", "investor": "Seed Fund"}},
        headers=h,
    ).json()["id"]
    r = client.post(
        f"/documents/{did}/regenerate",
        json={"data": {"company": "Acme", "investor": "Series A Fund", "amount": "5000000"}},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["current_version"] == 2
    assert "Series A Fund" in r.json()["content"]
    versions = client.get(f"/documents/{did}/versions", headers=h).json()
    assert [v["version"] for v in versions] == [1, 2]


def test_signature_flow_marks_document_signed(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    did = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "data": {"company": "Acme"}},
        headers=h,
    ).json()["id"]
    sig = client.post(
        f"/documents/{did}/signatures",
        json={"signatories": [{"name": "A. Founder", "email": "a@acme.in"}]},
        headers=h,
    )
    assert sig.status_code == 201
    assert sig.json()["status"] == "pending"
    sid = sig.json()["id"]

    done = client.post(f"/signatures/{sid}/complete", headers=h)
    assert done.status_code == 200 and done.json()["status"] == "completed"
    # document is now signed and cannot be regenerated
    assert client.get(f"/documents/{did}", headers=h).json()["status"] == "signed"
    assert client.post(
        f"/documents/{did}/regenerate", json={"data": {}}, headers=h
    ).status_code == 409


def test_document_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    did = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "data": {"company": "Acme"}},
        headers=owner,
    ).json()["id"]
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/documents/{did}", headers=outsider).status_code == 403


def test_workflow_generate_document_step_produces_real_document(client):
    """Wiring: completing a GENERATE_DOCUMENT step actually creates a Document
    and threads its id into the run context (HLD §9.2)."""
    h = auth_headers(client)
    eid = _entity(client, h)
    rid = client.post(
        f"/entities/{eid}/workflows",
        json={"definition_key": "priced_round"},
        headers=h,
    ).json()["id"]

    # advance to the generate_documents step
    for _ in range(10):
        run = client.get(f"/workflows/{rid}", headers=h).json()
        active = next(s for s in run["steps"] if s["status"] == "active")
        if active["step_key"] == "generate_documents":
            break
        client.post(
            f"/workflows/{rid}/steps/{active['step_key']}/complete",
            json={"output": {}},
            headers=h,
        )
    else:
        raise AssertionError("never reached generate_documents")

    res = client.post(
        f"/workflows/{rid}/steps/generate_documents/complete",
        json={
            "output": {
                "template_key": "sha",
                "data": {"company": "Acme Pvt Ltd", "investor": "Seed Fund"},
            }
        },
        headers=h,
    ).json()
    doc_id = res["context"]["document_id"]
    doc = client.get(f"/documents/{doc_id}", headers=h).json()
    assert doc["entity_id"] == eid
    assert doc["subject_type"] == "workflow_run" and doc["subject_id"] == rid
    assert "Seed Fund" in doc["content"]
