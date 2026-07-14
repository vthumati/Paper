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


def _drive(client, run_id, h, foreign):
    """Complete steps until the run is no longer running; set foreign_investor
    flag on the first collect step. Guarded against infinite loops."""
    for _ in range(20):
        run = client.get(f"/workflows/{run_id}", headers=h).json()
        if run["status"] != "running":
            return run
        active = next(s for s in run["steps"] if s["status"] == "active")
        out = (
            {"foreign_investor": foreign}
            if active["step_key"] == "collect_round_terms"
            else {}
        )
        r = client.post(
            f"/workflows/{run_id}/steps/{active['step_key']}/complete",
            json={"output": out},
            headers=h,
        )
        assert r.status_code == 200, r.text
    raise AssertionError("workflow did not terminate")


def test_list_definitions(client):
    h = auth_headers(client)
    keys = {d["key"] for d in client.get("/workflow-definitions", headers=h).json()}
    assert {"priced_round", "incorporate_pvt_ltd"} <= keys


def test_start_sets_first_step_active(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    run = client.post(
        f"/entities/{eid}/workflows",
        json={"definition_key": "priced_round", "context": {}},
        headers=h,
    ).json()
    assert run["status"] == "running"
    active = [s for s in run["steps"] if s["status"] == "active"]
    assert len(active) == 1 and active[0]["step_key"] == "collect_round_terms"
    # all other steps pending
    assert all(s["status"] == "pending" for s in run["steps"] if s["step_key"] != "collect_round_terms")


def test_branch_skips_fc_gpr_for_domestic_round(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    rid = client.post(
        f"/entities/{eid}/workflows",
        json={"definition_key": "priced_round"},
        headers=h,
    ).json()["id"]
    run = _drive(client, rid, h, foreign=False)
    assert run["status"] == "completed"
    by_key = {s["step_key"]: s["status"] for s in run["steps"]}
    assert by_key["fc_gpr"] == "skipped"
    assert by_key["publish_portal"] == "complete"


def test_branch_includes_fc_gpr_for_foreign_round(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    rid = client.post(
        f"/entities/{eid}/workflows",
        json={"definition_key": "priced_round"},
        headers=h,
    ).json()["id"]
    run = _drive(client, rid, h, foreign=True)
    assert run["status"] == "completed"
    by_key = {s["step_key"]: s["status"] for s in run["steps"]}
    assert by_key["fc_gpr"] == "complete"
    assert run["context"]["foreign_investor"] is True


def test_completing_wrong_step_conflicts(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    rid = client.post(
        f"/entities/{eid}/workflows",
        json={"definition_key": "priced_round"},
        headers=h,
    ).json()["id"]
    # 'esign' is not the active step yet (collect_round_terms is)
    r = client.post(
        f"/workflows/{rid}/steps/esign/complete", json={"output": {}}, headers=h
    )
    assert r.status_code == 409


def test_unknown_definition_404(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    r = client.post(
        f"/entities/{eid}/workflows", json={"definition_key": "nope"}, headers=h
    )
    assert r.status_code == 404


def test_workflow_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    rid = client.post(
        f"/entities/{eid}/workflows",
        json={"definition_key": "priced_round"},
        headers=owner,
    ).json()["id"]

    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/workflows/{rid}", headers=outsider).status_code == 403
    assert (
        client.post(
            f"/workflows/{rid}/steps/collect_round_terms/complete",
            json={"output": {}},
            headers=outsider,
        ).status_code
        == 403
    )
