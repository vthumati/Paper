from tests.conftest import auth_headers


def _company_with_investor(client, founder):
    tid = client.post("/tenants", json={"name": "C", "type": "company"}, headers=founder).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "C Pvt Ltd", "type": "pvt_ltd"}, headers=founder
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=founder
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Angel A", "type": "investor", "email": "angel@c.in"},
        headers=founder,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": inv, "quantity": 10000,
              "price_per_unit": "100", "issue_date": "2025-01-01"},
        headers=founder,
    )
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "angel@c.in", "stakeholder_id": inv},
        headers=founder,
    )
    return eid, sc, inv


def test_investor_consent_flow(client):
    founder = auth_headers(client, email="founder@c.in")
    eid, sc, inv = _company_with_investor(client, founder)
    rid = client.post(
        f"/entities/{eid}/resolutions",
        json={"type": "special", "title": "Approve ESOP top-up",
              "text": "RESOLVED THAT the pool be increased."},
        headers=founder,
    ).json()["id"]

    r = client.post(f"/resolutions/{rid}/consents", headers=founder).json()
    assert r == {"requested": 1, "total": 1}
    # idempotent: re-requesting adds nothing
    assert client.post(f"/resolutions/{rid}/consents", headers=founder).json()["requested"] == 0

    # investor sees the pending consent and approves it
    angel = auth_headers(client, email="angel@c.in")
    portal = client.get("/portal", headers=angel).json()
    consent = portal["companies"][0]["consents"][0]
    assert consent["status"] == "pending" and consent["title"] == "Approve ESOP top-up"
    r = client.post(f"/portal/consents/{consent['id']}", json={"approve": True}, headers=angel).json()
    assert r["status"] == "approved"
    # double-decide guarded; someone else's consent is invisible
    assert client.post(f"/portal/consents/{consent['id']}", json={"approve": False}, headers=angel).status_code == 409
    outsider = auth_headers(client, email="other@x.in")
    assert client.post(f"/portal/consents/{consent['id']}", json={"approve": True}, headers=outsider).status_code == 404

    tally = client.get(f"/resolutions/{rid}/consents", headers=founder).json()["tally"]
    assert tally == {"approved": 1, "rejected": 0, "pending": 0}


def test_secondary_sale_rofr(client):
    founder = auth_headers(client, email="founder@s.in")
    eid, sc, seller = _company_with_investor(client, founder)
    buyer = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Buyer B", "type": "investor"}, headers=founder
    ).json()["id"]

    # investor requests a sale from the portal
    angel = auth_headers(client, email="angel@c.in")
    req = client.post(
        "/portal/secondary-requests",
        json={"entity_id": eid, "security_class_id": sc, "quantity": 4000, "price_per_unit": "150"},
        headers=angel,
    )
    assert req.status_code == 201
    rid = req.json()["id"]
    # can't ask for more than held
    too_many = client.post(
        "/portal/secondary-requests",
        json={"entity_id": eid, "security_class_id": sc, "quantity": 99999, "price_per_unit": "150"},
        headers=angel,
    )
    assert too_many.status_code == 400

    # the company exercises ROFR: assigns the buyer and executes the transfer
    r = client.post(
        f"/secondary-requests/{rid}/decide",
        json={"approve": True, "buyer_stakeholder_id": buyer},
        headers=founder,
    ).json()
    assert r["status"] == "executed" and r["transfer_id"]

    ct = client.get(f"/entities/{eid}/cap-table", headers=founder).json()
    by_name = {h["stakeholder_name"]: h["quantity"] for h in ct["holders"]}
    assert by_name["Angel A"] == 6000 and by_name["Buyer B"] == 4000
    # seller's portal shows the executed request
    portal = client.get("/portal", headers=angel).json()
    assert portal["companies"][0]["sale_requests"][0]["status"] == "executed"


def test_secondary_reject(client):
    founder = auth_headers(client, email="founder@r.in")
    eid, sc, seller = _company_with_investor(client, founder)
    angel = auth_headers(client, email="angel@c.in")
    rid = client.post(
        "/portal/secondary-requests",
        json={"entity_id": eid, "security_class_id": sc, "quantity": 1000, "price_per_unit": "120"},
        headers=angel,
    ).json()["id"]
    r = client.post(
        f"/secondary-requests/{rid}/decide", json={"approve": False}, headers=founder
    ).json()
    assert r["status"] == "rejected"
    # approving without a buyer is a 400 on a fresh request
    rid2 = client.post(
        "/portal/secondary-requests",
        json={"entity_id": eid, "security_class_id": sc, "quantity": 1000, "price_per_unit": "120"},
        headers=angel,
    ).json()["id"]
    assert (
        client.post(f"/secondary-requests/{rid2}/decide", json={"approve": True}, headers=founder).status_code
        == 400
    )
