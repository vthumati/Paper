"""Full teardown of an entity / workspace, with the type-to-confirm guard."""
from tests.conftest import auth_headers


def _entity_with_data(client, h, tid, name="Acme Pvt Ltd"):
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": name, "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    sh = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": sh, "quantity": 100000,
              "price_per_unit": "1", "issue_date": "2025-01-02"},
        headers=h,
    )
    # an ESOP grant — indirectly owned (hangs off the scheme + stakeholder), the
    # case a naive "delete where entity_id=…" would miss
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 10000}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": sh, "quantity": 1000,
              "exercise_price": "1", "grant_date": "2025-02-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/compliance/generate", json={"financial_year_end": "2026-03-31"}, headers=h
    )
    return eid


def test_entity_teardown_preview_and_cascade(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    doomed = _entity_with_data(client, h, tid, "Doomed Co")
    keep = _entity_with_data(client, h, tid, "Keeper Co")

    # preview counts the associated records (incl. the indirectly-owned grant)
    pv = client.get(f"/entities/{doomed}/teardown-preview", headers=h).json()
    assert pv["name"] == "Doomed Co"
    assert pv["breakdown"].get("ESOP grants") == 1
    assert pv["associated_records"] >= 5

    # wrong confirmation name is refused, nothing deleted
    bad = client.post(f"/entities/{doomed}/teardown", json={"confirm_name": "wrong"}, headers=h)
    assert bad.status_code == 400
    assert client.get(f"/entities/{doomed}", headers=h).status_code == 200

    # exact name tears the whole subtree down
    ok = client.post(f"/entities/{doomed}/teardown", json={"confirm_name": "Doomed Co"}, headers=h)
    assert ok.status_code == 200 and ok.json()["deleted_rows"] >= 6
    assert client.get(f"/entities/{doomed}", headers=h).status_code == 404
    # every owned surface is gone
    assert client.get(f"/entities/{doomed}/cap-table", headers=h).status_code in (403, 404)

    # the sibling entity is completely untouched
    assert client.get(f"/entities/{keep}", headers=h).status_code == 200
    ct = client.get(f"/entities/{keep}/cap-table", headers=h).json()
    assert ct["total_shares"] == 100000


def test_workspace_teardown_removes_everything(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "TearCo", "type": "company"}, headers=h).json()["id"]
    _entity_with_data(client, h, tid, "E1")
    _entity_with_data(client, h, tid, "E2")
    # a second workspace that must survive
    other = client.post("/tenants", json={"name": "Survivor", "type": "company"}, headers=h).json()["id"]
    _entity_with_data(client, h, other, "S1")

    pv = client.get(f"/tenants/{tid}/teardown-preview", headers=h).json()
    assert pv["breakdown"].get("Entity") == 2  # both entities counted

    # confirm-name guard
    assert client.post(f"/tenants/{tid}/teardown", json={"confirm_name": "nope"}, headers=h).status_code == 400

    ok = client.post(f"/tenants/{tid}/teardown", json={"confirm_name": "TearCo"}, headers=h)
    assert ok.status_code == 200
    assert client.get(f"/tenants/{tid}", headers=h).status_code == 404
    assert tid not in [t["id"] for t in client.get("/tenants", headers=h).json()]

    # the survivor workspace and its data remain
    survivors = [t["id"] for t in client.get("/tenants", headers=h).json()]
    assert other in survivors
    assert len(client.get(f"/tenants/{other}/entities", headers=h).json()) == 1


def test_teardown_owner_only(client):
    owner = auth_headers(client, email="owner@tear.in")
    tid = client.post("/tenants", json={"name": "Private", "type": "company"}, headers=owner).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Priv Co", "type": "pvt_ltd"}, headers=owner
    ).json()["id"]
    outsider = auth_headers(client, email="stranger@tear.in")
    assert client.get(f"/entities/{eid}/teardown-preview", headers=outsider).status_code == 403
    assert client.post(
        f"/entities/{eid}/teardown", json={"confirm_name": "Priv Co"}, headers=outsider
    ).status_code == 403
    assert client.post(
        f"/tenants/{tid}/teardown", json={"confirm_name": "Private"}, headers=outsider
    ).status_code == 403
