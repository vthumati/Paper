from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_pipeline_crud_and_summary(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/investor-pipeline",
        json={"name": "Sequoia", "stage": "diligence", "check_size": "50000000"},
        headers=h,
    )
    p2 = client.post(
        f"/entities/{eid}/investor-pipeline",
        json={"name": "Accel", "stage": "contacted", "check_size": "30000000"},
        headers=h,
    ).json()["id"]
    assert len(client.get(f"/entities/{eid}/investor-pipeline", headers=h).json()) == 2

    # move Accel to passed
    client.post(f"/pipeline/{p2}/stage", json={"stage": "passed"}, headers=h)
    s = client.get(f"/entities/{eid}/investor-pipeline/summary", headers=h).json()
    assert s["total"] == 2
    # only Sequoia (diligence) counts as open value
    assert s["open_value"] == "50000000.00"
    assert s["by_stage"]["passed"]["count"] == 1


def test_convert_prospect_to_round_commitment(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "CCPS", "kind": "ccps"}, headers=h
    ).json()["id"]
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Series A", "price_per_share": "500", "security_class_id": sc},
        headers=h,
    ).json()["id"]
    pid = client.post(
        f"/entities/{eid}/investor-pipeline",
        json={"name": "Sequoia", "stage": "term_sheet", "check_size": "50000000", "round_id": rid},
        headers=h,
    ).json()["id"]

    res = client.post(f"/pipeline/{pid}/convert", headers=h).json()
    assert res["round_id"] == rid and res["commitment_id"]

    # the round now has a signed commitment from the converted prospect
    commits = client.get(f"/rounds/{rid}/commitments", headers=h).json()
    assert len(commits) == 1
    assert commits[0]["investor_name"] == "Sequoia" and commits[0]["status"] == "signed"
    assert commits[0]["amount"] == "50000000.00"
    # prospect is now committed and re-conversion blocked
    assert client.post(f"/pipeline/{pid}/convert", headers=h).status_code == 409


def test_convert_requires_round_and_check_size(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    pid = client.post(
        f"/entities/{eid}/investor-pipeline", json={"name": "NoRound"}, headers=h
    ).json()["id"]
    assert client.post(f"/pipeline/{pid}/convert", headers=h).status_code == 400


def test_crm_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/investor-pipeline", json={"name": "X"}, headers=outsider
        ).status_code
        == 403
    )
