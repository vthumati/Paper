import datetime as dt

from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "S", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "S Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return eid


def test_scenario_model_pro_forma(client):
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

    # FD pre = 9M issued + 1M pool = 10M → price = 40M / 10M = 4
    # SAFE at 3.2 → 312,500 · new = 10M / 4 = 2.5M · FD post = 12,812,500
    s = client.post(
        f"/entities/{eid}/scenarios/model",
        json={"new_money": "10000000", "pre_money": "40000000"},
        headers=h,
    ).json()
    assert s["price_per_share"] == "4.0000"
    assert s["new_shares"] == 2_500_000
    assert s["safe_shares_converted"] == 312_500
    assert s["fd_pre"] == 10_000_000 and s["fd_post"] == 12_812_500
    by_name = {r["name"]: r for r in s["rows"]}
    assert by_name["Founder"]["before_pct"] == 90.0
    assert by_name["Founder"]["after_pct"] == 70.2439
    assert by_name["New investors (this round)"]["after"] == 2_500_000
    assert by_name["Angel"]["after"] == 312_500
    # nothing was written to the ledger
    assert client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"] == 9_000_000

    # explicit price + pool top-up variant
    s2 = client.post(
        f"/entities/{eid}/scenarios/model",
        json={"new_money": "10000000", "price_per_share": "5", "pool_top_up": 500000},
        headers=h,
    ).json()
    assert s2["fd_pre"] == 10_500_000
    assert s2["pre_money"] == "52500000.00"
    # both pre_money and price missing → 400
    assert client.post(
        f"/entities/{eid}/scenarios/model", json={"new_money": "1"}, headers=h
    ).status_code == 400


def test_scenario_pool_shuffle(client):
    """Same round, pool timed pre vs post: pre-money comes out of the founder,
    post-money dilutes everyone (new investors included)."""
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
    round_ = {"new_money": "4500000", "pre_money": "9000000", "pool_top_up": 1_000_000}

    pre = client.post(f"/entities/{eid}/scenarios/model", json={**round_, "pool_timing": "pre"}, headers=h).json()
    post = client.post(f"/entities/{eid}/scenarios/model", json={**round_, "pool_timing": "post"}, headers=h).json()

    # pre-money pool sits in the price denominator → cheaper shares, bigger round
    assert pre["price_per_share"] == "0.9000" and pre["fd_pre"] == 10_000_000
    assert pre["new_shares"] == 5_000_000 and pre["fd_post"] == 15_000_000
    # post-money pool is created after the round → higher price, pool in fd_post
    assert post["price_per_share"] == "1.0000" and post["fd_pre"] == 9_000_000
    assert post["new_shares"] == 4_500_000 and post["fd_post"] == 14_500_000

    pre_by = {r["name"]: r for r in pre["rows"]}
    post_by = {r["name"]: r for r in post["rows"]}
    new = "New investors (this round)"
    # the new investor is protected pre-money, diluted by the pool post-money
    assert pre_by[new]["after_pct"] == 33.3333
    assert post_by[new]["after_pct"] == 31.0345
    # mirror image for the founder: worse pre-money, better post-money
    assert pre_by["Founder"]["after_pct"] == 60.0
    assert post_by["Founder"]["after_pct"] == 62.069
    assert pre["pool_timing"] == "pre" and post["pool_timing"] == "post"


def _vested_grant(client, h, eid, *, email, qty=48000, strike="10", fmv="50", days=800):
    """A company with one employee holding a partly-vested option grant + FMV."""
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Meera", "type": "employee", "email": email},
        headers=h,
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=h
    ).json()["id"]
    grant_date = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    gid = client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": qty,
              "exercise_price": strike, "grant_date": grant_date},
        headers=h,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": fmv, "valuation_date": "2026-01-01"},
        headers=h,
    )
    return sc, gid


def test_esop_tax_letter_and_certificate(client):
    """Perquisite/TDS calculator, grant-letter PDF download, and the share
    certificate auto-generated when the board approves an exercise."""
    founder = auth_headers(client, email="hr@x.in")
    eid = _company(client, founder)
    sc, gid = _vested_grant(client, founder, eid, email="meera@x.in")

    # grant letter (admin) — award terms + vesting schedule
    letter = client.post(f"/esop/grants/{gid}/letter", headers=founder).json()
    assert "GRANT LETTER" in letter["content"] and "48,000" in letter["content"]

    meera = auth_headers(client, email="meera@x.in")
    # the employee can download their own grant letter; a stranger cannot
    ok = client.get(f"/portal/documents/{letter['id']}/pdf", headers=meera)
    assert ok.status_code == 200 and ok.headers["content-type"] == "application/pdf"
    other = auth_headers(client, email="stranger@x.in")
    assert client.get(f"/portal/documents/{letter['id']}/pdf", headers=other).status_code == 404

    # tax estimate for exercising 10,000: perquisite (50−10)×10,000 = 400,000;
    # TDS = 30% + 4% cess = 124,800; cash cost = strike × qty = 100,000
    est = client.get(f"/portal/grants/{gid}/tax-estimate?quantity=10000", headers=meera).json()
    assert est["perquisite"] == "400000.00" and est["exercise_cost"] == "100000.00"
    assert est["income_tax"] == "120000.00" and est["cess"] == "4800.00"
    assert est["tds"] == "124800.00" and est["gain_after_tax"] == "275200.00"

    # request → board approval issues shares, returns the TDS, mints a certificate
    rid = client.post(
        "/portal/exercise-requests", json={"grant_id": gid, "quantity": 10000}, headers=meera
    ).json()["id"]
    res = client.post(
        f"/exercise-requests/{rid}/decide",
        json={"approve": True, "security_class_id": sc},
        headers=founder,
    ).json()
    assert res["perquisite_value"] == "400000.00" and res["tds"] == "124800.00"

    # both documents now hang off the grant, and the certificate is downloadable
    detail = client.get(f"/portal/grants/{gid}/detail", headers=meera).json()
    assert sorted(d["kind"] for d in detail["documents"]) == ["certificate", "grant_letter"]
    cert = next(d for d in detail["documents"] if d["kind"] == "certificate")
    assert client.get(f"/portal/documents/{cert['id']}/pdf", headers=meera).status_code == 200
    # the tax block rides along on the grant detail too
    assert detail["tax"]["tds"] is not None


def test_esop_forfeiture_true_up(client):
    """Offboarding freezes vesting and lapses the unvested balance as an
    auditable forfeiture event (returned to the pool, shown in the timeline)."""
    founder = auth_headers(client, email="hr3@x.in")
    eid = _company(client, founder)
    m = client.post(
        f"/entities/{eid}/team", json={"name": "Dev", "email": "dev@x.in"}, headers=founder
    ).json()["id"]
    sh_id = client.post(f"/team/{m}/onboard", headers=founder).json()["stakeholder_id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=founder
    ).json()["id"]
    grant_date = (dt.date.today() - dt.timedelta(days=800)).isoformat()
    client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": sh_id, "quantity": 48000,
              "exercise_price": "10", "grant_date": grant_date},
        headers=founder,
    )

    client.post(f"/team/{m}/offboard", json={}, headers=founder)

    forf = client.get(f"/entities/{eid}/esop/forfeitures", headers=founder).json()
    assert len(forf) == 1
    f0 = forf[0]
    assert f0["stakeholder"] == "Dev" and f0["reason"] == "offboarding"
    assert f0["lapsed_quantity"] > 0 and f0["vested_retained"] > 0
    assert f0["lapsed_quantity"] + f0["vested_retained"] == 48000
    # the grant is frozen at the vested amount; the lapse returns to the pool
    g = client.get(f"/entities/{eid}/esop/grants", headers=founder).json()[0]
    assert g["quantity"] == f0["vested_retained"]
    ov = client.get(f"/entities/{eid}/esop/overview", headers=founder).json()
    assert ov["forfeited"] == f0["lapsed_quantity"]
    # and it appears in the narrative timeline
    tl = client.get(f"/entities/{eid}/timeline", headers=founder).json()["events"]
    assert any(e["kind"] == "forfeiture" for e in tl)


def test_waterfall_range(client):
    h = auth_headers(client)
    eid = _company(client, h)
    common = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    pref = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "CCPS", "kind": "ccps", "pref_multiple": "1"},
        headers=h,
    ).json()["id"]
    f = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Founder", "type": "founder"}, headers=h
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Investor", "type": "investor"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": common, "stakeholder_id": f, "quantity": 800_000,
              "price_per_unit": "1", "issue_date": "2025-01-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": pref, "stakeholder_id": inv, "quantity": 200_000,
              "price_per_unit": "100", "issue_date": "2025-06-01"},
        headers=h,
    )

    r = client.get(
        f"/entities/{eid}/waterfall-range?amounts=10000000,100000000", headers=h
    ).json()
    assert r["exit_amounts"] == ["10000000.00", "100000000.00"]
    by_name = {x["stakeholder_name"]: x["payouts"] for x in r["rows"]}
    # at 1cr the 2cr preference eats everything; at 10cr the (non-participating)
    # preference is paid and the entire residual goes to common
    assert by_name["Investor"][0] == "10000000.00" and by_name["Founder"][0] == "0.00"
    assert by_name["Investor"][1] == "20000000.00"
    assert by_name["Founder"][1] == "80000000.00"
    # bad input
    assert client.get(f"/entities/{eid}/waterfall-range?amounts=abc", headers=h).status_code == 400


def test_employee_exercise_request_flow(client):
    founder = auth_headers(client, email="founder@x.in")
    eid = _company(client, founder)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=founder
    ).json()["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Meera", "type": "employee", "email": "meera@x.in"},
        headers=founder,
    ).json()["id"]
    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 100000}, headers=founder
    ).json()["id"]
    grant_date = (dt.date.today() - dt.timedelta(days=800)).isoformat()  # ~26mo vested
    gid = client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": 48000,
              "exercise_price": "10", "grant_date": grant_date},
        headers=founder,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "fair_value", "fmv_per_share": "50", "valuation_date": "2026-01-01"},
        headers=founder,
    )

    meera = auth_headers(client, email="meera@x.in")
    # over-asking is rejected against vested-minus-exercised
    too_many = client.post(
        "/portal/exercise-requests", json={"grant_id": gid, "quantity": 48000}, headers=meera
    )
    assert too_many.status_code == 400
    rid = client.post(
        "/portal/exercise-requests", json={"grant_id": gid, "quantity": 10000}, headers=meera
    ).json()["id"]
    # someone else's grant is invisible
    other = auth_headers(client, email="other@x.in")
    assert client.post(
        "/portal/exercise-requests", json={"grant_id": gid, "quantity": 1}, headers=other
    ).status_code == 404

    # company sees and approves — the real exercise lands on the ledger
    reqs = client.get(f"/entities/{eid}/exercise-requests", headers=founder).json()
    assert reqs[0]["employee"] == "Meera" and reqs[0]["status"] == "open"
    r = client.post(
        f"/exercise-requests/{rid}/decide",
        json={"approve": True, "security_class_id": sc},
        headers=founder,
    ).json()
    assert r["status"] == "approved" and r["net_shares"] == 10000
    assert r["perquisite_value"] == "400000.00"  # (50-10) x 10,000
    ct = client.get(f"/entities/{eid}/cap-table", headers=founder).json()
    assert ct["total_shares"] == 10000
    # employee sees the outcome in the portal
    portal = client.get("/portal", headers=meera).json()
    g = portal["equity_grants"][0]
    assert g["exercised"] == 10000
    assert g["exercise_requests"][0]["status"] == "approved"
    # double-decide guarded
    assert client.post(
        f"/exercise-requests/{rid}/decide", json={"approve": False}, headers=founder
    ).status_code == 409
