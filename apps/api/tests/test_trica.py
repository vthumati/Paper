"""trica-parity: Ind AS 102 ESOP expense (FR-D-6), periodic investor report
(FR-K-4), and the ESOP-adoption document pack (FR-D-1)."""
from app.services.sbp import black_scholes_call
from tests.conftest import auth_headers


def _company(client, h, name="Tr"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


def _grant(client, h, eid, gtype="option", qty=4800, strike="10", email="emp@tr.in"):
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Emp", "type": "employee", "email": email}, headers=h
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP 2026", "pool_size": 100000}, headers=h
    ).json()["id"]
    body = {"scheme_id": scheme, "stakeholder_id": emp, "quantity": qty, "grant_type": gtype,
            "exercise_price": strike, "grant_date": "2024-04-01", "cliff_months": 12, "total_months": 48}
    if gtype == "rsa":
        body["security_class_id"] = sc
    gid = client.post(f"/entities/{eid}/esop/grants", json=body, headers=h).json()["id"]
    return sc, scheme, gid


# --- Black-Scholes unit ---
def test_black_scholes_matches_reference():
    # spot 100, strike 100, 1y, vol 20%, rate 5%, no dividend -> ~10.45 (classic)
    v = black_scholes_call(100, 100, 1, 0.2, 0.05, 0)
    assert abs(v - 10.4506) < 0.01
    # deep in the money, no time value floors at intrinsic-ish
    assert black_scholes_call(100, 10, 0.0001, 0.2, 0.05) >= 89


# --- expense report (Ind AS 102) ---
def test_esop_expense_rsu_full_fmv(client):
    h = auth_headers(client)
    eid = _company(client, h)
    _sc, _scheme, _gid = _grant(client, h, eid, gtype="rsu", qty=1000, email="rsu@tr.in")
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "50", "valuation_date": "2024-04-01"},
        headers=h,
    )
    rep = client.get(f"/entities/{eid}/esop/expense", headers=h).json()
    # RSU grant-date fair value = full FMV × qty = 50 × 1000 = 50,000
    assert rep["totals"]["total_fair_value"] == "50000.00"
    g = rep["grants"][0]
    assert g["fair_value_per_unit"] == "50.00" and g["grant_type"] == "rsu"
    # straight-line over 48 months; the expense is spread across financial years
    assert len(rep["by_financial_year"]) >= 4
    fy_sum = sum(float(r["expense"]) for r in rep["by_financial_year"])
    assert abs(fy_sum - 50000.0) < 1.0  # FY buckets reconcile to total
    # some expense recognised by now (grant is >1yr old), some still future
    assert float(rep["totals"]["recognized_to_date"]) > 0
    assert float(rep["totals"]["unrecognized"]) > 0


def test_esop_expense_report_document(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Ex")
    _grant(client, h, eid, gtype="option", strike="10", email="opt@ex.in")
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "40", "valuation_date": "2024-04-01"},
        headers=h,
    )
    r = client.post(
        f"/entities/{eid}/esop/expense-report",
        json={"volatility": "0.6", "risk_free": "0.07", "expected_life": "5"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["type"] == "esop_expense"
    assert "Ind AS 102" in doc["content"]
    assert "Black-Scholes" in doc["content"]


def test_esop_expense_unpriced_when_no_fmv(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Np")
    _grant(client, h, eid, gtype="option", email="np@np.in")  # no valuation at all
    rep = client.get(f"/entities/{eid}/esop/expense", headers=h).json()
    assert rep["unpriced_grants"] == 1
    assert rep["totals"]["total_fair_value"] == "0"


# --- investor report ---
def test_investor_report_metrics_and_doc(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Ir")
    sc, _scheme, _gid = _grant(client, h, eid, email="ir@ir.in")
    fnd = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": fnd, "quantity": 1000000, "price_per_unit": "10", "issue_date": "2024-01-01"},
        headers=h,
    )
    m = client.get(f"/entities/{eid}/investor-report/preview", headers=h).json()
    assert m["shares_issued"] == 1000000
    assert m["stakeholders"] >= 1
    assert "options_granted" in m

    r = client.post(
        f"/entities/{eid}/investor-reports",
        json={"period_label": "Q1 FY26", "highlights": "Closed a marquee customer; runway extended."},
        headers=h,
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["type"] == "investor_report"
    assert "Q1 FY26" in doc["content"]
    assert "marquee customer" in doc["content"]
    assert "Shares issued" in doc["content"]


# --- ESOP scheme adoption pack ---
def test_esop_scheme_pack(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Pk")
    _sc, scheme, _gid = _grant(client, h, eid, email="pk@pk.in")
    r = client.post(f"/entities/{eid}/esop/schemes/{scheme}/pack", headers=h)
    assert r.status_code == 200, r.text
    docs = r.json()
    types = {d["type"] for d in docs}
    assert types == {"board_resolution", "esop_egm_notice", "esop_policy"}
    egm = next(d for d in docs if d["type"] == "esop_egm_notice")
    assert "Section 62(1)(b)" in egm["content"]
    assert "SPECIAL RESOLUTION" in egm["content"]
    policy = next(d for d in docs if d["type"] == "esop_policy")
    assert "ESOP 2026" in policy["content"]


def test_scheme_pack_bad_scheme_404(client):
    h = auth_headers(client)
    eid = _company(client, h, name="Bad")
    assert client.post(f"/entities/{eid}/esop/schemes/nope/pack", headers=h).status_code == 404
