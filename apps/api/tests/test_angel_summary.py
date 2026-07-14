from tests.conftest import auth_headers


def test_angel_portfolio_value_and_moic(client):
    founder = auth_headers(client, email="founder@x.in")
    tid = client.post("/tenants", json={"name": "X", "type": "company"}, headers=founder).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "X Pvt Ltd", "type": "pvt_ltd"}, headers=founder
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "CCPS", "kind": "ccps"}, headers=founder
    ).json()["id"]
    angel = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Angel A", "type": "investor", "email": "angel@a.in"},
        headers=founder,
    ).json()["id"]
    # invested 1,000,000 for 10,000 shares @ 100
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": angel, "quantity": 10000,
              "price_per_unit": "100", "issue_date": "2025-01-01"},
        headers=founder,
    )
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "angel@a.in", "stakeholder_id": angel},
        headers=founder,
    )
    # company later valued at FMV 250/share -> position worth 2,500,000
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "250", "valuation_date": "2026-01-01"},
        headers=founder,
    )

    portal = client.get("/portal", headers=auth_headers(client, email="angel@a.in")).json()
    assert portal["summary"]["total_invested"] == "1000000.00"
    assert portal["summary"]["portfolio_value"] == "2500000.00"
    assert portal["summary"]["moic"] == "2.50"
    assert portal["companies"][0]["current_value"] == "2500000.00"


def test_holdings_without_valuation_held_at_cost(client):
    founder = auth_headers(client, email="founder@y.in")
    tid = client.post("/tenants", json={"name": "Y", "type": "company"}, headers=founder).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Y Pvt Ltd", "type": "pvt_ltd"}, headers=founder
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=founder
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Inv", "type": "investor", "email": "inv@y.in"},
        headers=founder,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": inv, "quantity": 5000,
              "price_per_unit": "100", "issue_date": "2025-01-01"},
        headers=founder,
    )
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "inv@y.in", "stakeholder_id": inv},
        headers=founder,
    )
    portal = client.get("/portal", headers=auth_headers(client, email="inv@y.in")).json()
    assert portal["summary"]["portfolio_value"] == "500000.00"  # cost basis
    assert portal["summary"]["moic"] == "1.00"
