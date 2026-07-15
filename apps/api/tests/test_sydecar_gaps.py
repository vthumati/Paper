"""Sydecar-parity features (FR-S-3/FR-S-4): SPV deal terms provisioning the
fund profile, and the syndicate subscription flow (invite -> portal commit ->
funded) with co-investor portal visibility."""
from tests.conftest import auth_headers


def _spv(client, h, *, portco=False):
    tid = client.post("/tenants", json={"name": "Syndicate House", "type": "fund"}, headers=h).json()["id"]
    body = {"sponsor": "Lead GP", "target_company": "Target Pvt Ltd"}
    if portco:
        pid = client.post(
            f"/tenants/{tid}/entities", json={"name": "Target Pvt Ltd", "type": "pvt_ltd"}, headers=h
        ).json()["id"]
        body["portco_entity_id"] = pid
    spv_entity = client.post(
        f"/tenants/{tid}/entities", json={"name": "Deal SPV I", "type": "spv"}, headers=h
    ).json()["id"]
    sid = client.post(f"/entities/{spv_entity}/spv", json=body, headers=h).json()["id"]
    return spv_entity, sid


def test_spv_terms_provision_fund_profile(client):
    h = auth_headers(client)
    spv_entity, sid = _spv(client, h)

    r = client.post(
        f"/spvs/{sid}/terms", json={"carry_pct": "0.20", "min_ticket": "500000"}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["carry_pct"] == "0.2000"
    assert r.json()["min_ticket"] == "500000.00"

    # a fund profile now exists on the SPV entity: carry mirrored, no hurdle/fee
    f = client.get(f"/entities/{spv_entity}/fund", headers=h).json()
    assert f["carry_pct"] == "0.2000"
    assert f["hurdle_pct"] == "0.0000"
    assert f["mgmt_fee_pct"] == "0.0000"

    # revising terms updates the existing profile instead of duplicating it
    client.post(f"/spvs/{sid}/terms", json={"carry_pct": "0.15", "min_ticket": "0"}, headers=h)
    f = client.get(f"/entities/{spv_entity}/fund", headers=h).json()
    assert f["carry_pct"] == "0.1500"


def test_spv_terms_validation(client):
    h = auth_headers(client)
    _, sid = _spv(client, h)
    r = client.post(f"/spvs/{sid}/terms", json={"carry_pct": "1.5", "min_ticket": "0"}, headers=h)
    assert r.status_code == 422


def test_syndicate_flow_invite_commit_fund(client):
    lead = auth_headers(client, email="lead@syndicate.in")
    _, sid = _spv(client, lead)
    client.post(f"/spvs/{sid}/terms", json={"carry_pct": "0.20", "min_ticket": "500000"}, headers=lead)

    # invite a backer by email (no commitment yet -> invited)
    ci = client.post(
        f"/spvs/{sid}/co-investors",
        json={"name": "Angel A", "email": "backer@angels.in"},
        headers=lead,
    ).json()
    assert ci["status"] == "invited"

    # the backer sees the deal in their portal
    backer = auth_headers(client, email="backer@angels.in")
    p = client.get("/portal", headers=backer).json()
    assert p["summary"]["spvs"] == 1
    deal = p["spvs"][0]
    assert deal["target_company"] == "Target Pvt Ltd"
    assert deal["status"] == "invited"
    assert deal["min_ticket"] == "500000.00"
    assert deal["carry_pct"] == "0.2000"

    # below the minimum ticket -> rejected
    r = client.post(
        "/portal/spv-commitments",
        json={"co_investor_id": ci["id"], "amount": "100000"},
        headers=backer,
    )
    assert r.status_code == 400 and "Minimum ticket" in r.json()["detail"]

    # a stranger cannot commit on this invitation
    stranger = auth_headers(client, email="stranger@evil.in")
    r = client.post(
        "/portal/spv-commitments",
        json={"co_investor_id": ci["id"], "amount": "750000"},
        headers=stranger,
    )
    assert r.status_code == 404

    # a valid commitment moves the backer to committed
    r = client.post(
        "/portal/spv-commitments",
        json={"co_investor_id": ci["id"], "amount": "750000"},
        headers=backer,
    )
    assert r.status_code == 200
    assert r.json() == {"id": ci["id"], "status": "committed", "commitment": "750000.00"}

    # the lead sees it and marks the money received -> funded
    listed = client.get(f"/spvs/{sid}/co-investors", headers=lead).json()
    assert listed[0]["status"] == "committed" and listed[0]["commitment"] == "750000.00"
    funded = client.post(f"/spvs/{sid}/co-investors/{ci['id']}/contribute", headers=lead).json()
    assert funded["status"] == "funded" and funded["contributed"] == "750000.00"

    s = client.get(f"/spvs/{sid}/summary", headers=lead).json()
    assert s["by_status"] == {"invited": 0, "committed": 0, "funded": 1}

    # funded commitments can no longer be revised from the portal
    r = client.post(
        "/portal/spv-commitments",
        json={"co_investor_id": ci["id"], "amount": "900000"},
        headers=backer,
    )
    assert r.status_code == 409

    # the backer's portal reflects the funded position
    p = client.get("/portal", headers=backer).json()
    assert p["spvs"][0]["status"] == "funded"
    assert p["summary"]["total_committed"] == "750000.00"
    assert p["summary"]["total_invested"] == "750000.00"


def test_direct_add_with_commitment_is_committed(client):
    h = auth_headers(client)
    _, sid = _spv(client, h)
    ci = client.post(
        f"/spvs/{sid}/co-investors", json={"name": "Angel B", "commitment": "2000000"}, headers=h
    ).json()
    assert ci["status"] == "committed"
