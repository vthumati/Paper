from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def _counterparty(client, h, eid, kind="customer"):
    return client.post(
        f"/entities/{eid}/counterparties",
        json={"name": "BigCo", "kind": kind, "contact_email": "ap@bigco.in"},
        headers=h,
    ).json()["id"]


def test_counterparty_and_contract(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    cp = _counterparty(client, h, eid)
    c = client.post(
        f"/entities/{eid}/contracts",
        json={"counterparty_id": cp, "title": "MSA 2026", "type": "msa", "value": "1200000"},
        headers=h,
    )
    assert c.status_code == 201
    body = c.json()
    assert body["counterparty_name"] == "BigCo" and body["counterparty_kind"] == "customer"
    # unknown counterparty rejected
    bad = client.post(
        f"/entities/{eid}/contracts", json={"counterparty_id": "nope", "title": "X"}, headers=h
    )
    assert bad.status_code == 400


def test_renewal_tracking(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    cp = _counterparty(client, h, eid)
    cid = client.post(
        f"/entities/{eid}/contracts",
        json={"counterparty_id": cp, "title": "MSA", "renewal_date": "2026-09-30"},
        headers=h,
    ).json()["id"]
    # make it active so it shows up in renewals
    client.post(f"/contracts/{cid}/status", json={"status": "active"}, headers=h)

    # as of well before renewal, within 30 days -> not due
    none_due = client.get(
        f"/entities/{eid}/contracts/renewals?within_days=30&as_of=2026-06-01", headers=h
    ).json()
    assert none_due == []

    # within 60 days of 2026-09-30 from 2026-08-15 -> due
    due = client.get(
        f"/entities/{eid}/contracts/renewals?within_days=60&as_of=2026-08-15", headers=h
    ).json()
    assert len(due) == 1 and due[0]["title"] == "MSA"

    # past renewal date while active -> overdue flag in the listing
    listed = client.get(f"/entities/{eid}/contracts?as_of=2026-12-01", headers=h).json()
    assert listed[0]["renewal_overdue"] is True
    assert listed[0]["days_to_renewal"] < 0


def test_contract_document_generation(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    cp = _counterparty(client, h, eid, kind="vendor")
    cid = client.post(
        f"/entities/{eid}/contracts",
        json={"counterparty_id": cp, "title": "Hosting MSA", "value": "500000"},
        headers=h,
    ).json()["id"]
    doc = client.post(f"/contracts/{cid}/document", json={"template_key": "msa"}, headers=h)
    assert doc.status_code == 201
    assert "MASTER SERVICES AGREEMENT" in doc.json()["content"]
    assert "BigCo" in doc.json()["content"]
    # contract now links the document
    listed = client.get(f"/entities/{eid}/contracts", headers=h).json()
    assert listed[0]["document_id"] == doc.json()["id"]


def test_clm_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/counterparties",
            json={"name": "X", "kind": "vendor"},
            headers=outsider,
        ).status_code
        == 403
    )
