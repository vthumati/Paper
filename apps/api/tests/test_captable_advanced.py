from tests.conftest import auth_headers


def _setup(client, h):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


def _class(client, h, eid, name, kind="equity", **terms):
    return client.post(
        f"/entities/{eid}/security-classes",
        json={"name": name, "kind": kind, **terms},
        headers=h,
    ).json()["id"]


def _holder(client, h, eid, name, typ="founder"):
    return client.post(
        f"/entities/{eid}/stakeholders", json={"name": name, "type": typ}, headers=h
    ).json()["id"]


def _issue(client, h, eid, sc, sh, qty, price="10"):
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": sh, "quantity": qty, "price_per_unit": price, "issue_date": "2026-01-01"},
        headers=h,
    )


def test_transfer_moves_shares_and_charges_stamp_duty(client):
    h = auth_headers(client)
    eid = _setup(client, h)
    eq = _class(client, h, eid, "Equity")
    a = _holder(client, h, eid, "Founder A")
    b = _holder(client, h, eid, "Buyer B", "investor")
    _issue(client, h, eid, eq, a, 10000, "10")

    t = client.post(
        f"/entities/{eid}/transfers",
        json={"security_class_id": eq, "from_stakeholder_id": a, "to_stakeholder_id": b, "quantity": 3000, "price_per_unit": "50"},
        headers=h,
    )
    assert t.status_code == 201
    # stamp duty = 0.015% of (3000 * 50 = 150000) = 22.50
    assert t.json()["stamp_duty"] == "22.50"

    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    by = {r["stakeholder_name"]: r for r in ct["holders"]}
    assert by["Founder A"]["quantity"] == 7000
    assert by["Buyer B"]["quantity"] == 3000
    assert ct["total_shares"] == 10000  # transfer doesn't change total

    # cannot transfer more than held
    over = client.post(
        f"/entities/{eid}/transfers",
        json={"security_class_id": eq, "from_stakeholder_id": b, "to_stakeholder_id": a, "quantity": 9999, "price_per_unit": "1"},
        headers=h,
    )
    assert over.status_code == 400


def test_conversion_ccps_to_equity(client):
    h = auth_headers(client)
    eid = _setup(client, h)
    ccps = _class(client, h, eid, "Seed CCPS", "ccps", pref_multiple="1")
    eq = _class(client, h, eid, "Equity", "equity")
    inv = _holder(client, h, eid, "Seed Fund", "investor")
    _issue(client, h, eid, ccps, inv, 1000, "100")

    # convert 1000 CCPS -> 1500 equity (1.5x ratio, e.g. anti-dilution)
    r = client.post(
        f"/entities/{eid}/conversions",
        json={"stakeholder_id": inv, "from_class_id": ccps, "to_class_id": eq, "from_quantity": 1000, "ratio": "1.5"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["to_quantity"] == 1500

    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    rows = {r["security_class"]: r for r in ct["holders"]}
    assert "Seed CCPS" not in rows  # fully converted
    assert rows["Equity"]["quantity"] == 1500


def test_buyback_reduces_total(client):
    h = auth_headers(client)
    eid = _setup(client, h)
    eq = _class(client, h, eid, "Equity")
    a = _holder(client, h, eid, "Founder A")
    _issue(client, h, eid, eq, a, 10000, "10")
    client.post(
        f"/entities/{eid}/buybacks",
        json={"security_class_id": eq, "stakeholder_id": a, "quantity": 2000, "price_per_unit": "50"},
        headers=h,
    )
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 8000


def test_liquidation_waterfall_non_participating_preference(client):
    h = auth_headers(client)
    eid = _setup(client, h)
    # founder: 8000 common; investor: 2000 CCPS, 1x non-participating, invested 2,000,000
    common = _class(client, h, eid, "Equity", "equity")
    pref = _class(client, h, eid, "Series A CCPS", "ccps", pref_multiple="1", participating=False, seniority=1)
    founder = _holder(client, h, eid, "Founder", "founder")
    investor = _holder(client, h, eid, "Series A", "investor")
    _issue(client, h, eid, common, founder, 8000, "1")
    _issue(client, h, eid, pref, investor, 2000, "1000")  # invested 2,000,000

    # exit at 3,000,000: investor takes 1x pref (2,000,000) first; remaining 1,000,000
    # to common only (non-participating) -> founder 1,000,000
    w = client.get(f"/entities/{eid}/waterfall?exit_amount=3000000", headers=h).json()
    payout = {p["stakeholder_name"]: p["payout"] for p in w["payouts"]}
    assert payout["Series A"] == "2000000.00"
    assert payout["Founder"] == "1000000.00"
    assert w["distributed"] == "3000000.00"


def test_liquidation_waterfall_participating(client):
    h = auth_headers(client)
    eid = _setup(client, h)
    common = _class(client, h, eid, "Equity", "equity")
    pref = _class(client, h, eid, "Series A CCPS", "ccps", pref_multiple="1", participating=True, seniority=1)
    founder = _holder(client, h, eid, "Founder", "founder")
    investor = _holder(client, h, eid, "Series A", "investor")
    _issue(client, h, eid, common, founder, 8000, "1")
    _issue(client, h, eid, pref, investor, 2000, "1000")  # invested 2,000,000

    # exit 3,000,000: pref 2,000,000 first; remaining 1,000,000 shared pro-rata by ALL shares
    # (participating): founder 8000/10000 -> 800,000 ; investor 200,000 + 2,000,000 pref
    w = client.get(f"/entities/{eid}/waterfall?exit_amount=3000000", headers=h).json()
    payout = {p["stakeholder_name"]: p["payout"] for p in w["payouts"]}
    assert payout["Founder"] == "800000.00"
    assert payout["Series A"] == "2200000.00"


def test_positions_memo_invalidated_by_new_issuance(client):
    """The per-request positions memo must never serve stale numbers: a fresh
    issuance is reflected on the next read (write flush clears the memo)."""
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "Memo", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Memo Co", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    sh = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    iss = lambda q, d: client.post(  # noqa: E731
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": sh, "quantity": q,
              "price_per_unit": "1", "issue_date": d},
        headers=h,
    )
    iss(1000, "2025-01-01")
    assert client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"] == 1000
    iss(500, "2025-02-01")
    assert client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"] == 1500
