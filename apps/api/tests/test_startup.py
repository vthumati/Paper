import datetime

from tests.conftest import auth_headers


def _entity(client, h, etype="pvt_ltd", incorporated="2024-01-01"):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Acme Pvt Ltd", "type": etype, "incorporation_date": incorporated},
        headers=h,
    ).json()["id"]


def test_eligibility_recent_pvt_ltd_is_eligible(client):
    h = auth_headers(client)
    eid = _entity(client, h, "pvt_ltd", "2024-01-01")
    e = client.get(f"/entities/{eid}/startup/eligibility", headers=h).json()
    assert e["eligible"] is True


def test_eligibility_old_company_not_eligible(client):
    h = auth_headers(client)
    eid = _entity(client, h, "pvt_ltd", "2010-01-01")
    e = client.get(f"/entities/{eid}/startup/eligibility", headers=h).json()
    assert e["eligible"] is False
    assert any("10-year" in r or "exceeds" in r for r in e["reasons"])


def test_eligibility_wrong_type_not_eligible(client):
    h = auth_headers(client)
    eid = _entity(client, h, "opc", "2024-01-01")
    e = client.get(f"/entities/{eid}/startup/eligibility", headers=h).json()
    assert e["eligible"] is False


def test_recognition_and_benefit_gating(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    # benefit before recognition -> 400
    assert (
        client.post(
            f"/entities/{eid}/startup/benefits", json={"type": "section_80iac"}, headers=h
        ).status_code
        == 400
    )
    # apply then record recognition (upsert)
    client.put(f"/entities/{eid}/startup/recognition", json={"status": "applied"}, headers=h)
    rec = client.put(
        f"/entities/{eid}/startup/recognition",
        json={"status": "recognised", "dpiit_number": "DIPP12345", "recognised_on": "2026-03-01"},
        headers=h,
    )
    assert rec.status_code == 200 and rec.json()["status"] == "recognised"
    assert rec.json()["dpiit_number"] == "DIPP12345"

    # now benefits can be applied for
    b = client.post(
        f"/entities/{eid}/startup/benefits", json={"type": "angel_tax_56_2_viib"}, headers=h
    )
    assert b.status_code == 201 and b.json()["status"] == "applied"
    bid = b.json()["id"]
    upd = client.post(
        f"/startup-benefits/{bid}/status", json={"status": "approved", "reference": "CBDT-77"}, headers=h
    )
    assert upd.status_code == 200 and upd.json()["status"] == "approved"
    assert len(client.get(f"/entities/{eid}/startup/benefits", headers=h).json()) == 1


def test_startup_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.put(
            f"/entities/{eid}/startup/recognition", json={"status": "applied"}, headers=outsider
        ).status_code
        == 403
    )
