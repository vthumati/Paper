"""RSU / RSA equity instruments (FR-D-2, Mantle gap): grants that share the
vesting model with options but settle and tax differently."""
from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "R", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "R Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Equity", "kind": "equity", "par_value": "10"},
        headers=h,
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Emp R", "type": "employee", "email": "emp@r.in"},
        headers=h,
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "Incentive 2026", "pool_size": 100000}, headers=h
    ).json()["id"]
    return eid, sc, emp, scheme


def test_rsu_grant_and_settle(client):
    h = auth_headers(client)
    eid, sc, emp, scheme = _setup(client, h)
    # RSU grant — strike is forced to 0
    g = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme, "stakeholder_id": emp, "quantity": 4800,
            "grant_type": "rsu", "exercise_price": "99",  # should be ignored
            "grant_date": "2025-01-01", "cliff_months": 12, "total_months": 48,
        },
        headers=h,
    ).json()
    assert g["grant_type"] == "rsu"
    assert g["exercise_price"] == "0.0000"
    gid = g["id"]
    # a valuation to price the perquisite at settlement
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "40", "valuation_date": "2026-01-01"},
        headers=h,
    )
    # at 2026-01-01, 12/48 vested = 1200 settleable
    view = client.get(f"/esop/grants/{gid}?as_of=2026-01-01", headers=h).json()
    assert view["vested"] == 1200
    assert view["exercisable"] == 1200
    # settle 1000 (reuses the exercise endpoint; strike 0 -> perquisite = FMV × qty)
    r = client.post(
        f"/esop/grants/{gid}/exercise?as_of=2026-01-01",
        json={"quantity": 1000, "security_class_id": sc, "fmv_per_share": "40"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    ex = r.json()
    assert ex["exercise_price"] == "0.0000"
    assert ex["perquisite_value"] == "40000.00"  # 1000 × 40, full FMV
    assert ex["net_shares"] == 1000
    # settled shares now sit in the cap table
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert any(row["quantity"] == 1000 for row in ct["holders"])


def test_rsa_issued_upfront(client):
    h = auth_headers(client)
    eid, sc, emp, scheme = _setup(client, h)
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "50", "valuation_date": "2025-01-01"},
        headers=h,
    )
    g = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme, "stakeholder_id": emp, "quantity": 2000,
            "grant_type": "rsa", "exercise_price": "10", "security_class_id": sc,
            "fmv": "50", "grant_date": "2025-01-01", "cliff_months": 12, "total_months": 48,
        },
        headers=h,
    ).json()
    assert g["grant_type"] == "rsa"
    # all 2000 shares issued at grant, sitting in the cap table immediately
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert any(row["quantity"] == 2000 for row in ct["holders"])
    # early on, most are unvested (subject to repurchase); exercisable is n/a
    view = client.get(f"/esop/grants/{g['id']}?as_of=2025-06-01", headers=h).json()
    assert view["vested"] == 0
    assert view["unvested"] == 2000
    assert view["exercisable"] == 0
    # RSA cannot be exercised/settled
    r = client.post(
        f"/esop/grants/{g['id']}/exercise",
        json={"quantity": 100, "security_class_id": sc},
        headers=h,
    )
    assert r.status_code == 400
    assert "issued at grant" in r.json()["detail"]


def test_rsa_requires_security_class(client):
    h = auth_headers(client)
    eid, sc, emp, scheme = _setup(client, h)
    r = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme, "stakeholder_id": emp, "quantity": 100,
            "grant_type": "rsa", "exercise_price": "10",
            "grant_date": "2025-01-01",
        },
        headers=h,
    )
    assert r.status_code == 400
    assert "security class" in r.json()["detail"]


def test_option_grant_unchanged(client):
    h = auth_headers(client)
    eid, sc, emp, scheme = _setup(client, h)
    g = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme, "stakeholder_id": emp, "quantity": 4800,
            "exercise_price": "10", "grant_date": "2025-01-01",
            "cliff_months": 12, "total_months": 48,
        },
        headers=h,
    ).json()
    assert g["grant_type"] == "option"
    assert g["exercise_price"] == "10.0000"
    # nothing issued upfront for options
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 0
