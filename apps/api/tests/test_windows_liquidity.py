"""Exercise windows (FR-D-4) gating exercise, and the company liquidity /
buyback tender flow (FR-C-8)."""
from tests.conftest import auth_headers


def _company(client, h, name="Wl"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


def _shares(client, h, eid, email, qty=10000):
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    sh = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Holder", "type": "employee", "email": email},
        headers=h,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": sh, "quantity": qty,
              "price_per_unit": "10", "issue_date": "2025-01-01"},
        headers=h,
    )
    return sc, sh


def _grant(client, h, eid, sh, qty=4800):
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=h
    ).json()["id"]
    return client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": sh, "quantity": qty,
              "exercise_price": "10", "grant_date": "2024-01-01", "cliff_months": 12, "total_months": 48},
        headers=h,
    ).json()["id"]


# --- exercise windows ---
def test_exercise_gated_by_window(client):
    h = auth_headers(client, email="admin@wl.in")
    eid = _company(client, h)
    _sc, sh = _shares(client, h, eid, "emp@wl.in")
    gid = _grant(client, h, eid, sh)
    emp = auth_headers(client, email="emp@wl.in")

    # no windows defined -> exercise requests allowed (opt-in, back-compat)
    assert client.post("/portal/exercise-requests", json={"grant_id": gid, "quantity": 10}, headers=emp).status_code == 201

    # define a CLOSED (past) window -> now gated, no open window -> blocked
    client.post(
        f"/entities/{eid}/exercise-windows",
        json={"name": "FY25 Q1", "opens_on": "2024-01-01", "closes_on": "2024-03-31"},
        headers=h,
    )
    r = client.post("/portal/exercise-requests", json={"grant_id": gid, "quantity": 10}, headers=emp)
    assert r.status_code == 400
    assert "open exercise window" in r.json()["detail"]

    # add an open window (spanning today) -> allowed again
    client.post(
        f"/entities/{eid}/exercise-windows",
        json={"name": "Always", "opens_on": "2020-01-01", "closes_on": "2035-01-01"},
        headers=h,
    )
    assert client.post("/portal/exercise-requests", json={"grant_id": gid, "quantity": 10}, headers=emp).status_code == 201

    windows = client.get(f"/entities/{eid}/exercise-windows", headers=h).json()
    states = {w["name"]: w["state"] for w in windows}
    assert states["FY25 Q1"] == "closed" and states["Always"] == "open"


def test_exercise_window_bad_dates(client):
    h = auth_headers(client, email="a2@wl.in")
    eid = _company(client, h)
    r = client.post(
        f"/entities/{eid}/exercise-windows",
        json={"name": "X", "opens_on": "2026-06-01", "closes_on": "2026-01-01"},
        headers=h,
    )
    assert r.status_code == 400


# --- liquidity / buyback tender ---
def test_liquidity_buyback_flow(client):
    h = auth_headers(client, email="admin@buy.in")
    eid = _company(client, h)
    sc, sh = _shares(client, h, eid, "seller@buy.in", qty=10000)

    ev = client.post(
        f"/entities/{eid}/liquidity-events",
        json={"name": "2026 Buyback", "kind": "buyback", "price_per_share": "50",
              "opens_on": "2020-01-01", "closes_on": "2035-01-01"},
        headers=h,
    ).json()
    assert ev["status"] == "open"

    # holder tenders 3,000 shares
    seller = auth_headers(client, email="seller@buy.in")
    t = client.post(
        "/portal/tenders",
        json={"event_id": ev["id"], "security_class_id": sc, "quantity": 3000},
        headers=seller,
    )
    assert t.status_code == 201, t.text

    # can't tender more than held (10,000 held, 3,000 already tendered)
    over = client.post(
        "/portal/tenders",
        json={"event_id": ev["id"], "security_class_id": sc, "quantity": 8000},
        headers=seller,
    )
    assert over.status_code == 400

    # the tender shows in the portal's open liquidity events
    portal = client.get("/portal", headers=seller).json()
    le = portal["liquidity_events"][0]
    assert le["my_tendered"] == 3000 and le["price_per_share"] == "50.0000"
    assert any(hld["quantity"] == 10000 for hld in le["holdings"])

    # admin settles -> buyback of 3,000 at ₹50 = ₹150,000
    res = client.post(f"/entities/{eid}/liquidity-events/{ev['id']}/settle", headers=h).json()
    assert res["tenders_settled"] == 1
    assert res["shares_bought_back"] == 3000
    assert res["total_paid"] == "150000.00"

    # cap table now shows 7,000 held (10,000 - 3,000 bought back)
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 7000
    # event settled; re-settle is a conflict
    assert client.post(f"/entities/{eid}/liquidity-events/{ev['id']}/settle", headers=h).status_code == 409


def test_tender_requires_shares(client):
    h = auth_headers(client, email="admin@buy2.in")
    eid = _company(client, h)
    sc, _sh = _shares(client, h, eid, "hasshares@buy2.in")
    ev = client.post(
        f"/entities/{eid}/liquidity-events",
        json={"name": "B", "price_per_share": "10", "opens_on": "2020-01-01", "closes_on": "2035-01-01"},
        headers=h,
    ).json()
    # a stranger with no stakeholder record in the entity can't tender
    stranger = auth_headers(client, email="nobody@buy2.in")
    r = client.post(
        "/portal/tenders",
        json={"event_id": ev["id"], "security_class_id": sc, "quantity": 1},
        headers=stranger,
    )
    assert r.status_code == 403
