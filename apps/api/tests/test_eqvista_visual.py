"""Eqvista-parity visual data: dashboard class breakdown + authorized-capital
panel + valuation status card, the narrative equity timeline (FR-C-10), and
the portal vesting projection."""
import datetime

from app.models.esop import Grant
from app.services.esop import add_months, vesting_projection
from tests.conftest import auth_headers


def _company(client, h, name="Viz"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return tid, eid


def _class(client, h, eid, name="Equity", kind="equity"):
    return client.post(
        f"/entities/{eid}/security-classes", json={"name": name, "kind": kind}, headers=h
    ).json()["id"]


def _stakeholder(client, h, eid, name, type_="founder", email=None):
    return client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": name, "type": type_, "email": email},
        headers=h,
    ).json()["id"]


def _issue(client, h, eid, sc, sh, qty, price="10", date="2026-01-01"):
    r = client.post(
        f"/entities/{eid}/issuances",
        json={
            "security_class_id": sc,
            "stakeholder_id": sh,
            "quantity": qty,
            "price_per_unit": price,
            "issue_date": date,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_dashboard_class_breakdown_and_capital(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    eq = _class(client, h, eid, "Equity", "equity")
    ccps = _class(client, h, eid, "Series A CCPS", "ccps")
    f = _stakeholder(client, h, eid, "Founder F")
    inv = _stakeholder(client, h, eid, "Investor I", "investor")
    _issue(client, h, eid, eq, f, 9000)
    _issue(client, h, eid, ccps, inv, 1000, price="100")

    d = client.get(f"/entities/{eid}/dashboard", headers=h).json()
    by_class = d["cap_table"]["by_class"]
    assert [(r["name"], r["quantity"], r["pct"]) for r in by_class] == [
        ("Equity", 9000, 90.0),
        ("Series A CCPS", 1000, 10.0),
    ]
    assert by_class[1]["kind"] == "ccps"
    # no incorporation charter on file -> authorized unknown
    assert d["capital"]["authorized_shares"] is None
    assert d["capital"]["available"] is None
    assert d["capital"]["issued"] == 10000
    assert d["valuation"]["status"] == "missing"


def test_dashboard_authorized_capital_from_incorporation(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "Zed", "type": "company"}, headers=h).json()["id"]
    iid = client.post(
        f"/tenants/{tid}/incorporations",
        json={
            "name_options": ["Zed Labs Pvt Ltd"],
            "state": "Karnataka",
            "registered_office": "1 MG Road, Bengaluru",
            "authorised_capital": "1000000",
            "paid_up_capital": "100000",
            "par_value": "10",
            "founders": [
                {"name": "Aisha", "shares": 6000},
                {"name": "Rohan", "shares": 4000},
            ],
        },
        headers=h,
    ).json()["id"]
    client.post(f"/tenants/{tid}/incorporations/{iid}/prepare", headers=h)
    client.post(f"/tenants/{tid}/incorporations/{iid}/filed", json={"srn": "T1"}, headers=h)
    eid = client.post(
        f"/tenants/{tid}/incorporations/{iid}/registered",
        json={"cin": "U72900KA2026PTC000001", "incorporation_date": "2026-07-01"},
        headers=h,
    ).json()["entity_id"]

    cap = client.get(f"/entities/{eid}/dashboard", headers=h).json()["capital"]
    assert cap["authorized_shares"] == 100000  # 10L authorised / ₹10 par
    assert cap["issued"] == 10000
    assert cap["available"] == 90000


def test_dashboard_valuation_states(client):
    h = auth_headers(client)
    _, eid = _company(client, h, name="Val")
    # an expired report -> "expired", not "missing"
    client.post(
        f"/entities/{eid}/valuations",
        json={
            "method": "fair_value",
            "fmv_per_share": "50",
            "valuation_date": "2024-01-01",
            "valid_until": "2025-01-01",
        },
        headers=h,
    )
    assert client.get(f"/entities/{eid}/dashboard", headers=h).json()["valuation"]["status"] == "expired"

    client.post(
        f"/entities/{eid}/valuations",
        json={
            "method": "rule_11ua",
            "fmv_per_share": "120.5",
            "valuation_date": "2026-07-01",
            "valuer_name": "RV & Co",
        },
        headers=h,
    )
    v = client.get(f"/entities/{eid}/dashboard", headers=h).json()["valuation"]
    assert v["status"] == "active"
    assert v["fmv_per_share"] == "120.5000"
    assert v["method"] == "rule_11ua"
    assert v["valuer_name"] == "RV & Co"


def test_timeline_narrative(client):
    h = auth_headers(client)
    _, eid = _company(client, h, name="Tim")
    eq = _class(client, h, eid)
    f = _stakeholder(client, h, eid, "Priya Founder")
    _issue(client, h, eid, eq, f, 5000, price="10", date="2026-01-01")
    client.post(
        f"/entities/{eid}/instruments",
        json={
            "investor_name": "Angel A",
            "principal": "1500000",
            "valuation_cap": "50000000",
            "issue_date": "2026-03-01",
        },
        headers=h,
    )
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "25", "valuation_date": "2026-05-01"},
        headers=h,
    )

    events = client.get(f"/entities/{eid}/timeline", headers=h).json()["events"]
    assert [e["kind"] for e in events] == ["valuation", "instrument", "issue"]  # newest first
    texts = {e["kind"]: e["text"] for e in events}
    assert texts["issue"] == "Priya Founder received 5,000 Equity shares at ₹10 per share"
    assert texts["instrument"] == "Angel A invested ₹1,500,000 via a SAFE (cap ₹50,000,000)"
    assert texts["valuation"] == "FMV set at ₹25 per share (fair_value)"


def test_vesting_projection_unit():
    g = Grant(
        quantity=4800,
        grant_date=datetime.date(2025, 1, 1),
        cliff_months=12,
        total_months=48,
    )
    # before the cliff: the first future event is the cliff chunk itself
    p = vesting_projection(g, datetime.date(2025, 6, 1))
    assert p["full_vest_date"] == datetime.date(2029, 1, 1)
    assert p["next_vests"][0] == {"date": datetime.date(2026, 1, 1), "quantity": 1200}
    # mid-schedule: monthly 100-option tranches
    p = vesting_projection(g, datetime.date(2026, 6, 15))
    assert p["next_vests"] == [
        {"date": datetime.date(2026, 7, 1), "quantity": 100},
        {"date": datetime.date(2026, 8, 1), "quantity": 100},
        {"date": datetime.date(2026, 9, 1), "quantity": 100},
    ]
    # fully vested: nothing upcoming
    assert vesting_projection(g, datetime.date(2029, 2, 1))["next_vests"] == []
    assert add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)


def test_portal_grant_vesting_projection(client):
    h = auth_headers(client)
    _, eid = _company(client, h, name="Port")
    emp_email = "emp@port.in"
    emp = _stakeholder(client, h, eid, "Emp E", "employee", email=emp_email)
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 5000}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/esop/grants",
        json={
            "scheme_id": scheme,
            "stakeholder_id": emp,
            "quantity": 4800,
            "exercise_price": "10",
            "grant_date": "2025-01-01",
            "cliff_months": 12,
            "total_months": 48,
        },
        headers=h,
    )
    he = auth_headers(client, email=emp_email)
    g = client.get("/portal", headers=he).json()["equity_grants"][0]
    assert g["full_vest_date"] == "2029-01-01"
    assert 0.0 <= g["vesting_pct"] <= 100.0
    assert 0 < len(g["next_vests"]) <= 3
    assert all(ev["quantity"] > 0 for ev in g["next_vests"])
    dates = [ev["date"] for ev in g["next_vests"]]
    assert dates == sorted(dates)
