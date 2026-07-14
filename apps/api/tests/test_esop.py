from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Equity", "kind": "equity", "par_value": "10"},
        headers=h,
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Employee A", "type": "employee"},
        headers=h,
    ).json()["id"]
    return eid, sc, emp


def _grant(client, h, eid, emp, qty=4800):
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP 2026", "pool_size": 5000}, headers=h
    ).json()["id"]
    grant = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme,
            "stakeholder_id": emp,
            "quantity": qty,
            "exercise_price": "10",
            "grant_date": "2025-01-01",
            "cliff_months": 12,
            "total_months": 48,
        },
        headers=h,
    )
    return scheme, grant


def test_grant_and_pool_limit(client):
    h = auth_headers(client)
    eid, _, emp = _setup(client, h)
    scheme, grant = _grant(client, h, eid, emp, qty=4800)
    assert grant.status_code == 201
    # second grant exceeding remaining pool (5000 - 4800 = 200) -> 400
    over = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme,
            "stakeholder_id": emp,
            "quantity": 300,
            "exercise_price": "10",
            "grant_date": "2025-01-01",
        },
        headers=h,
    )
    assert over.status_code == 400


def test_vesting_schedule(client):
    h = auth_headers(client)
    eid, _, emp = _setup(client, h)
    _, grant = _grant(client, h, eid, emp, qty=4800)
    gid = grant.json()["id"]
    # before cliff (5 months) -> 0
    assert client.get(f"/esop/grants/{gid}?as_of=2025-06-01", headers=h).json()["vested"] == 0
    # at 12 months -> 12/48 * 4800 = 1200
    assert client.get(f"/esop/grants/{gid}?as_of=2026-01-01", headers=h).json()["vested"] == 1200
    # past total (48+ months) -> fully vested
    assert client.get(f"/esop/grants/{gid}?as_of=2029-06-01", headers=h).json()["vested"] == 4800


def test_exercise_flows_into_cap_table(client):
    h = auth_headers(client)
    eid, sc, emp = _setup(client, h)
    _, grant = _grant(client, h, eid, emp, qty=4800)
    gid = grant.json()["id"]

    # at 12 months, 1200 vested; exercise 1000 with FMV 100, strike 10
    ex = client.post(
        f"/esop/grants/{gid}/exercise?as_of=2026-01-01",
        json={"quantity": 1000, "security_class_id": sc, "fmv_per_share": "100"},
        headers=h,
    )
    assert ex.status_code == 201
    # perquisite = (100 - 10) * 1000 = 90000
    assert ex.json()["perquisite_value"] == "90000.00"

    # the grant now shows 1000 exercised, 200 exercisable
    g = client.get(f"/esop/grants/{gid}?as_of=2026-01-01", headers=h).json()
    assert g["exercised"] == 1000 and g["exercisable"] == 200

    # over-exercise beyond exercisable -> 400
    over = client.post(
        f"/esop/grants/{gid}/exercise?as_of=2026-01-01",
        json={"quantity": 500, "security_class_id": sc, "fmv_per_share": "100"},
        headers=h,
    )
    assert over.status_code == 400

    # exercised options now appear as real shares in the cap table
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 1000
    assert ct["holders"][0]["stakeholder_name"] == "Employee A"
    assert ct["holders"][0]["quantity"] == 1000


def test_esop_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid, _, emp = _setup(client, owner)
    _, grant = _grant(client, owner, eid, emp)
    gid = grant.json()["id"]
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/esop/grants/{gid}", headers=outsider).status_code == 403
