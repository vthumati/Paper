from tests.conftest import auth_headers


def test_employee_sees_own_grants_in_portal(client):
    founder = auth_headers(client, email="founder@acme.in")
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=founder).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=founder
    ).json()["id"]
    # employee stakeholder with an email matching a future login
    emp = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Asha", "type": "employee", "email": "asha@acme.in"},
        headers=founder,
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=founder
    ).json()["id"]
    client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": 4800, "exercise_price": "10", "grant_date": "2025-01-01"},
        headers=founder,
    )
    # a current valuation so unrealized gain is computed
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "100", "valuation_date": "2025-12-01"},
        headers=founder,
    )

    # the employee logs in (matched by email) and sees their grant in the portal
    emp_user = auth_headers(client, email="asha@acme.in")
    portal = client.get("/portal", headers=emp_user).json()
    assert len(portal["equity_grants"]) == 1
    g = portal["equity_grants"][0]
    assert g["entity_name"] == "Acme Pvt Ltd"
    assert g["granted"] == 4800
    assert g["vested"] > 0  # past the 1-year cliff as of today (2026+)
    assert g["current_fmv"] == "100.0000"
    # unrealized gain = exercisable * (100 - 10)
    assert g["unrealized_gain"] == f"{g['exercisable'] * 90:.2f}"
    assert portal["summary"]["options_vested"] == g["vested"]


def test_non_employee_has_no_grants(client):
    founder = auth_headers(client, email="founder@acme.in")
    stranger = auth_headers(client, email="stranger@nowhere.in")
    assert client.get("/portal", headers=stranger).json()["equity_grants"] == []
