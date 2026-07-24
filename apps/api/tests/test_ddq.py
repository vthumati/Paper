"""DDQ answer bank (Visible-style due-diligence support): Q&A CRUD with
presets, and the generated DDQ responses document."""
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def test_ddq_crud_and_presets(client):
    h = auth_headers(client)
    fid = _fund(client, h)

    ls = client.get(f"/funds/{fid}/ddq", headers=h).json()
    assert ls["entries"] == [] and len(ls["presets"]) == 12
    # presets carry an SEC/SEBI regulator tag
    assert any(p["regulator"] == "sec" for p in ls["presets"])

    # add a preset question, then answer it
    e = client.post(f"/funds/{fid}/ddq", json=ls["presets"][0], headers=h).json()
    assert e["category"] == "Firm" and e["answered"] is False
    # same question again -> 409
    assert client.post(f"/funds/{fid}/ddq", json=ls["presets"][0], headers=h).status_code == 409

    upd = client.put(
        f"/funds/{fid}/ddq/{e['id']}",
        json={"answer": "Founded 2020; 100% partner-owned; team of 8 across Mumbai and Bengaluru."},
        headers=h,
    ).json()
    assert upd["answered"] is True

    # own question in a custom category
    client.post(
        f"/funds/{fid}/ddq",
        json={"category": "Tax", "question": "How are LP distributions taxed?", "answer": "Pass-through under s.115UB."},
        headers=h,
    )
    entries = client.get(f"/funds/{fid}/ddq", headers=h).json()["entries"]
    assert [x["category"] for x in entries] == ["Firm", "Tax"]

    # delete
    assert client.delete(f"/funds/{fid}/ddq/{e['id']}", headers=h).status_code == 204
    assert client.delete(f"/funds/{fid}/ddq/{e['id']}", headers=h).status_code == 404


def test_ddq_document_renders_sections(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.post(
        f"/funds/{fid}/ddq",
        json={"category": "Fund", "question": "What are the fund's key terms?", "answer": "₹100 Cr, 2% fee, 20% carry, 8% hurdle, 10-year life."},
        headers=h,
    )
    client.post(
        f"/funds/{fid}/ddq",
        json={"category": "ESG", "question": "Describe the ESG policy."},
        headers=h,
    )
    doc = client.post(f"/funds/{fid}/ddq/report", headers=h).json()
    body = doc["content"]
    assert "DUE DILIGENCE QUESTIONNAIRE" in body and "Alpha Fund I" in body
    assert "FUND" in body and "What are the fund's key terms?" in body
    assert "20% carry" in body
    assert "(response pending)" in body  # the unanswered ESG question


def test_ddq_entry_scoped_to_fund(client):
    h = auth_headers(client)
    fid_a = _fund(client, h)
    e = client.post(
        f"/funds/{fid_a}/ddq", json={"question": "Only in fund A?"}, headers=h
    ).json()

    h2 = auth_headers(client, email="other@gp.in")
    fid_b = _fund(client, h2)
    assert (
        client.put(f"/funds/{fid_b}/ddq/{e['id']}", json={"answer": "hijack"}, headers=h2).status_code
        == 404
    )
