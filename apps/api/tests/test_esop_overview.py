"""ESOP overview dashboard (FR-D-1, trica visual gap): pool usage, option
states and the top-grants leaderboard, aggregated read-only."""
from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "Ov", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Ov Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 20000}, headers=h
    ).json()["id"]
    return eid, sc, scheme


def _emp(client, h, eid, name):
    return client.post(
        f"/entities/{eid}/stakeholders", json={"name": name, "type": "employee"}, headers=h
    ).json()["id"]


def _grant(client, h, eid, scheme, emp, qty, date="2024-01-01"):
    return client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": qty,
              "exercise_price": "10", "grant_date": date, "cliff_months": 12, "total_months": 48},
        headers=h,
    ).json()["id"]


def test_esop_overview_pool_and_states(client):
    h = auth_headers(client)
    eid, _sc, scheme = _company(client, h)
    a = _emp(client, h, eid, "Raj")
    b = _emp(client, h, eid, "Asha")
    _grant(client, h, eid, scheme, a, 8000)
    _grant(client, h, eid, scheme, b, 2000)

    ov = client.get(f"/entities/{eid}/esop/overview", headers=h).json()
    assert ov["pool_size"] == 20000
    assert ov["granted"] == 10000
    assert ov["available"] == 10000
    assert ov["used_pct"] == 50.0
    assert ov["grantees"] == 2
    # segments sum to the pool
    seg = ov["pool_segments"]
    assert seg["exercised"] + seg["vested_unexercised"] + seg["unvested"] + seg["available"] == 20000
    # nothing exercised yet; some vested (grants are >1yr old)
    assert ov["exercised"] == 0
    assert ov["vested"] > 0 and ov["unvested"] > 0
    assert ov["exercisable"] == ov["vested"]
    # leaderboard ranks by granted, largest first
    assert [x["name"] for x in ov["leaderboard"]] == ["Raj", "Asha"]
    assert ov["leaderboard"][0]["granted"] == 8000
    assert ov["by_type"] == {"option": 2}


def test_esop_overview_empty(client):
    h = auth_headers(client)
    eid, _sc, _scheme = _company(client, h)
    ov = client.get(f"/entities/{eid}/esop/overview", headers=h).json()
    assert ov["pool_size"] == 20000
    assert ov["granted"] == 0 and ov["available"] == 20000
    assert ov["grantees"] == 0
    assert ov["leaderboard"] == []
