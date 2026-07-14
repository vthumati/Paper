from tests.conftest import auth_headers


def _entity(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_create_and_current_valuation(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "rule_11ua", "fmv_per_share": "100", "valuation_date": "2026-01-01"},
        headers=h,
    )
    # a later valuation supersedes the earlier one
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "150", "valuation_date": "2026-04-01"},
        headers=h,
    )
    cur = client.get(f"/entities/{eid}/valuations/current?as_of=2026-06-01", headers=h).json()
    assert cur["fmv_per_share"] == "150.0000"
    # as of a date before the later valuation -> earlier one applies
    cur2 = client.get(f"/entities/{eid}/valuations/current?as_of=2026-02-01", headers=h).json()
    assert cur2["fmv_per_share"] == "100.0000"


def test_expired_valuation_not_current(client):
    h = auth_headers(client)
    eid = _entity(client, h)
    client.post(
        f"/entities/{eid}/valuations",
        json={
            "method": "rule_11ua",
            "fmv_per_share": "100",
            "valuation_date": "2025-01-01",
            "valid_until": "2025-12-31",
        },
        headers=h,
    )
    cur = client.get(f"/entities/{eid}/valuations/current?as_of=2026-06-01", headers=h).json()
    assert cur["fmv_per_share"] is None


def test_esop_exercise_uses_current_valuation(client):
    """Loop-closer: exercising without an explicit FMV pulls the entity's
    current valuation to price the perquisite."""
    h = auth_headers(client)
    eid = _entity(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Equity", "kind": "equity"},
        headers=h,
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Emp", "type": "employee"}, headers=h
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 10000}, headers=h
    ).json()["id"]
    gid = client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme,
            "stakeholder_id": emp,
            "quantity": 4800,
            "exercise_price": "10",
            "grant_date": "2025-01-01",
        },
        headers=h,
    ).json()["id"]
    # current valuation = 250
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "250", "valuation_date": "2025-12-01"},
        headers=h,
    )
    # exercise WITHOUT fmv -> uses 250; perquisite = (250-10)*1000 = 240000
    ex = client.post(
        f"/esop/grants/{gid}/exercise?as_of=2026-01-01",
        json={"quantity": 1000, "security_class_id": sc},
        headers=h,
    ).json()
    assert ex["fmv_per_share"] == "250.0000"
    assert ex["perquisite_value"] == "240000.00"


def test_valuation_access_control(client):
    owner = auth_headers(client, email="owner@acme.in")
    eid = _entity(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert (
        client.post(
            f"/entities/{eid}/valuations",
            json={"method": "fema", "fmv_per_share": "1", "valuation_date": "2026-01-01"},
            headers=outsider,
        ).status_code
        == 403
    )
