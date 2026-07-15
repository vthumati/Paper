"""Self-serve indicative valuation (FR-L-2, Eqvista gap 6): scorecard / VC
method / DCF, custom weighting, per-share on the fully-diluted count,
smartfill from financial snapshots, and the workpaper document."""
from decimal import Decimal

from app.services.startup_valuation import _dcf, _scorecard, _vc_method
from tests.conftest import auth_headers


def _company(client, h, name="Val"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return tid, eid


def _seed_shares(client, h, eid, qty=1_000_000):
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    sh = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={
            "security_class_id": sc,
            "stakeholder_id": sh,
            "quantity": qty,
            "price_per_unit": "10",
            "issue_date": "2026-01-01",
        },
        headers=h,
    )


# --- pure method unit tests ---
def test_scorecard_at_and_off_benchmark():
    # all factors exactly at benchmark (100) -> equals the base valuation
    at = _scorecard({"base_valuation": "40000000", "scores": {}})
    assert at == Decimal("40000000.00")
    # lift only the team factor (30% weight) to 150 -> +15% overall
    lifted = _scorecard({"base_valuation": "40000000", "scores": {"team": "150"}})
    assert lifted == Decimal("46000000.00")


def test_vc_method_pre_money():
    vc = _vc_method({"exit_value": "500000000", "target_multiple": "10", "planned_raise": "20000000"})
    assert vc["post_money"] == Decimal("50000000.00")
    assert vc["pre_money"] == Decimal("30000000.00")


def test_dcf_positive():
    # 2 years of ₹10 net cash, 20% discount, no terminal growth
    v = _dcf(
        {
            "projections": [
                {"revenue": "10", "expenses": "0"},
                {"revenue": "10", "expenses": "0"},
            ],
            "discount_rate_pct": "20",
            "terminal_growth_pct": "0",
        }
    )
    # 10/1.2 + 10/1.44 + terminal (10/0.2 = 50 discounted at yr2) = 8.33+6.94+34.72
    assert v == Decimal("50.00")


# --- API tests ---
def test_estimate_blend_and_per_share(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    _seed_shares(client, h, eid, qty=1_000_000)
    body = {
        "label": "Seed pitch",
        "weights": {"scorecard": "1", "vc_method": "1"},
        "scorecard": {"base_valuation": "40000000", "scores": {}},
        "vc_method": {"exit_value": "500000000", "target_multiple": "10", "planned_raise": "20000000"},
    }
    r = client.post(f"/entities/{eid}/valuation-estimates", json=body, headers=h)
    assert r.status_code == 201, r.text
    res = r.json()["results"]
    # blended = (40,000,000 + 30,000,000) / 2 = 35,000,000
    assert res["blended_value"] == "35000000.00"
    assert res["methods"] == {"scorecard": "40000000.00", "vc_method": "30000000.00"}
    # equal normalised weights
    assert res["weights"] == {"scorecard": "0.5000", "vc_method": "0.5000"}
    # per share on 1,000,000 FD shares
    assert res["per_share"] == "35.0000"
    assert "registered valuer" in res["disclaimer"]
    # persisted and listable
    lst = client.get(f"/entities/{eid}/valuation-estimates", headers=h).json()
    assert len(lst) == 1 and lst[0]["label"] == "Seed pitch"


def test_estimate_weighted_method_needs_inputs(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    _seed_shares(client, h, eid)
    # weight on dcf but no dcf block -> 400
    body = {
        "label": "bad",
        "weights": {"scorecard": "1", "dcf": "1"},
        "scorecard": {"base_valuation": "10000000", "scores": {}},
    }
    r = client.post(f"/entities/{eid}/valuation-estimates", json=body, headers=h)
    assert r.status_code == 400
    assert "dcf" in r.json()["detail"]


def test_estimate_preview_not_saved(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    _seed_shares(client, h, eid)
    body = {
        "label": "preview",
        "save": False,
        "weights": {"scorecard": "1"},
        "scorecard": {"base_valuation": "10000000", "scores": {}},
    }
    r = client.post(f"/entities/{eid}/valuation-estimates", json=body, headers=h)
    assert r.status_code == 201
    assert client.get(f"/entities/{eid}/valuation-estimates", headers=h).json() == []


def test_smartfill_from_snapshots(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    # add 3 months of financials
    for m in (1, 2, 3):
        client.post(
            f"/entities/{eid}/finance/snapshots",
            json={
                "period": f"2026-0{m}-01",
                "cash_balance": "10000000",
                "monthly_burn": "500000",
                "revenue": "200000",
            },
            headers=h,
        )
    r = client.get(f"/entities/{eid}/valuation-estimates/smartfill?growth_pct=25&years=3", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["months_of_data"] == 3
    assert body["base_annual_revenue"] == "2400000.00"  # 200k * 12
    # expenses = (burn + revenue) * 12 = 700k*12
    assert body["base_annual_expenses"] == "8400000.00"
    assert len(body["projections"]) == 3
    # revenue grows 25% year 1
    assert body["projections"][0]["revenue"] == "3000000.00"


def test_smartfill_no_snapshots_400(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    assert client.get(f"/entities/{eid}/valuation-estimates/smartfill", headers=h).status_code == 400


def test_estimate_report_document(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    _seed_shares(client, h, eid)
    est_id = client.post(
        f"/entities/{eid}/valuation-estimates",
        json={
            "label": "Board pack",
            "weights": {"scorecard": "1"},
            "scorecard": {"base_valuation": "50000000", "scores": {}},
        },
        headers=h,
    ).json()["id"]
    r = client.post(f"/entities/{eid}/valuation-estimates/{est_id}/report", headers=h)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["type"] == "valuation_estimate"
    assert "Board pack" in doc["title"]


def test_estimate_report_cross_entity_guard(client):
    h = auth_headers(client)
    _, eid = _company(client, h, name="A")
    _, other = _company(client, h, name="B")
    _seed_shares(client, h, eid)
    est_id = client.post(
        f"/entities/{eid}/valuation-estimates",
        json={
            "label": "x",
            "weights": {"scorecard": "1"},
            "scorecard": {"base_valuation": "10000000", "scores": {}},
        },
        headers=h,
    ).json()["id"]
    # reference entity A's estimate under entity B -> 400
    r = client.post(f"/entities/{other}/valuation-estimates/{est_id}/report", headers=h)
    assert r.status_code == 400
