"""Pulley-parity features: rules-based term sheet scanner (FR-E-11) and the
SAFE execution flow (terms -> board approval -> agreement -> e-sign, FR-E-4)."""
from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "P", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "P Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


BAD_TERM_SHEET = """
TERM SHEET — Series A
Liquidation preference: 2x the original issue price, participating.
Anti-dilution: full ratchet.
Dividends: 8% cumulative dividend, payable on liquidation.
Exclusivity: the Company grants the Investor a 90 days no-shop period.
Redemption: shares redeemable at the option of the investor after year 5.
The Founders shall personally guarantee the representations herein.
ESOP: an option pool of 20% shall be created pre-money prior to closing.
"""

CLEAN_TERM_SHEET = """
TERM SHEET — Seed round
Liquidation preference: 1x non-participating.
Anti-dilution: broad-based weighted average.
Investor rights: pro-rata rights in future financings, information rights
(quarterly financials), tag-along, and a right of first refusal on founder
transfers. Exclusivity: 30 days.
"""


def test_scanner_flags_off_market_terms(client):
    h = auth_headers(client)
    eid = _company(client, h)
    r = client.post(f"/entities/{eid}/termsheet/scan", json={"text": BAD_TERM_SHEET}, headers=h)
    assert r.status_code == 200
    body = r.json()
    codes = {f["code"] for f in body["findings"]}
    assert {"liq_pref_multiple", "participating_preferred", "full_ratchet",
            "cumulative_dividend", "long_exclusivity", "redemption_put",
            "founder_guarantee", "pool_shuffle"} <= codes
    assert body["counts"]["red"] >= 5
    assert "negotiate" in body["verdict"].lower()
    # reds sort first and findings carry the matched snippet
    assert body["findings"][0]["severity"] == "red"
    liq = next(f for f in body["findings"] if f["code"] == "liq_pref_multiple")
    assert "2x" in liq["snippet"]


def test_scanner_confirms_standard_terms(client):
    h = auth_headers(client)
    eid = _company(client, h)
    body = client.post(
        f"/entities/{eid}/termsheet/scan", json={"text": CLEAN_TERM_SHEET}, headers=h
    ).json()
    assert body["counts"]["red"] == 0
    codes = {f["code"] for f in body["findings"]}
    assert {"bbwa", "pro_rata", "rofr", "tag_along", "info_rights"} <= codes
    assert "no off-market terms" in body["verdict"].lower()


def test_scanner_input_bounds(client):
    h = auth_headers(client)
    eid = _company(client, h)
    assert client.post(
        f"/entities/{eid}/termsheet/scan", json={"text": "too short"}, headers=h
    ).status_code == 422


def test_scenario_stage_matrix(client):
    """after_safes_pct: ownership at the mid stage where SAFEs have converted
    but the new money has not yet landed (fd_pre + safe shares basis)."""
    h = auth_headers(client)
    eid = _company(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    f = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": f, "quantity": 9_000_000,
              "price_per_unit": "1", "issue_date": "2025-01-01"},
        headers=h,
    )
    client.post(f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 1_000_000}, headers=h)
    client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Angel", "instrument_type": "safe", "principal": "1000000",
              "discount_pct": "0.20", "issue_date": "2025-06-01"},
        headers=h,
    )
    s = client.post(
        f"/entities/{eid}/scenarios/model",
        json={"new_money": "10000000", "pre_money": "40000000"},
        headers=h,
    ).json()
    by_name = {r["name"]: r for r in s["rows"]}
    # mid basis = 10,000,000 + 312,500 SAFE shares
    assert by_name["Founder"]["after_safes_pct"] == round(9_000_000 / 10_312_500 * 100, 4)
    assert by_name["Angel"]["after_safes_pct"] == round(312_500 / 10_312_500 * 100, 4)
    assert by_name["New investors (this round)"]["after_safes_pct"] == 0.0


def test_safe_execution_flow(client):
    h = auth_headers(client)
    eid = _company(client, h)
    inst = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Asha Angel", "instrument_type": "safe",
              "principal": "2500000", "valuation_cap": "100000000",
              "discount_pct": "0.20", "issue_date": "2026-07-01"},
        headers=h,
    ).json()
    iid = inst["id"]

    # nothing executed yet
    ex = client.get(f"/entities/{eid}/instruments/execution", headers=h).json()
    assert ex[iid] == {"board": None, "agreement": None, "signature": None}

    # board approval drafts a circular resolution
    res = client.post(f"/instruments/{iid}/board-approval", headers=h).json()
    assert res["type"] == "circular" and "Asha Angel" in res["title"]
    assert client.post(f"/instruments/{iid}/board-approval", headers=h).status_code == 409
    client.post(f"/resolutions/{res['id']}/status", json={"status": "passed"}, headers=h)

    # agreement generated from the instrument's terms
    doc = client.post(f"/instruments/{iid}/agreement", headers=h).json()
    assert doc["template_key"] == "safe_agreement"
    assert "SAFE AGREEMENT" in doc["content"]
    assert "INR 100000000.00" in doc["content"] and "20%" in doc["content"]

    # regenerating re-versions the same document
    doc2 = client.post(f"/instruments/{iid}/agreement", headers=h).json()
    assert doc2["id"] == doc["id"] and doc2["current_version"] == 2

    # e-sign through the existing simulated flow
    sig = client.post(
        f"/documents/{doc['id']}/signatures",
        json={"signatories": [{"name": "Asha Angel"}, {"name": "Director"}]},
        headers=h,
    ).json()
    client.post(
        f"/signatures/{sig['id']}/complete", json={"token": sig["completion_token"]}, headers=h
    )

    ex = client.get(f"/entities/{eid}/instruments/execution", headers=h).json()
    assert ex[iid] == {"board": "passed", "agreement": "signed", "signature": "completed"}

    # a signed agreement is immutable: regeneration creates a fresh document
    doc3 = client.post(f"/instruments/{iid}/agreement", headers=h).json()
    assert doc3["id"] != doc["id"] and doc3["current_version"] == 1
