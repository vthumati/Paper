from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund",
        json={"sebi_category": "II", "carry_pct": "0.20"},
        headers=h,
    ).json()["id"]
    return eid, fid


def test_create_fund_is_unique_per_entity(client):
    h = auth_headers(client)
    eid, _ = _fund(client, h)
    dup = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h)
    assert dup.status_code == 409


def test_capital_call_pro_rata_and_accounts(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    lp1 = client.post(
        f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h
    ).json()["id"]
    lp2 = client.post(
        f"/funds/{fid}/lps", json={"name": "LP Two", "commitment": "30000000"}, headers=h
    ).json()["id"]

    # 25% capital call -> LP1 2,500,000 ; LP2 7,500,000
    call = client.post(
        f"/funds/{fid}/capital-calls", json={"pct": "0.25", "purpose": "Deal 1"}, headers=h
    ).json()
    by_lp = {n["lp_id"]: n for n in call["notices"]}
    assert by_lp[lp1]["amount"] == "2500000.00"
    assert by_lp[lp2]["amount"] == "7500000.00"

    # pay both notices
    for n in call["notices"]:
        r = client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)
        assert r.status_code == 200 and r.json()["paid"] is True

    acc = client.get(f"/funds/{fid}/capital-accounts", headers=h).json()
    assert acc["totals"]["committed"] == "40000000.00"
    assert acc["totals"]["drawn"] == "10000000.00"
    assert acc["totals"]["remaining"] == "30000000.00"
    accounts = {a["lp_id"]: a for a in acc["accounts"]}
    assert accounts[lp1]["drawn"] == "2500000.00"
    assert accounts[lp2]["remaining"] == "22500000.00"


def test_distribution_waterfall_roc_before_carry(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    lp1 = client.post(
        f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h
    ).json()["id"]
    lp2 = client.post(
        f"/funds/{fid}/lps", json={"name": "LP Two", "commitment": "10000000"}, headers=h
    ).json()["id"]
    # draw 100% so paid-in is equal (1:1)
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "1.0"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)

    # profit of 1,000,000 while capital is unreturned -> all return of capital, no carry
    dist = client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "1000000", "kind": "profit"},
        headers=h,
    ).json()
    assert dist["carry_amount"] == "0.00"
    assert dist["roc_amount"] == "1000000.00"

    # 21,000,000 more (same day, so no pref accrued): fills ROC to 20M,
    # then 2,000,000 of profit -> carry 20% = 400,000
    dist2 = client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "21000000", "kind": "profit"},
        headers=h,
    ).json()
    assert dist2["roc_amount"] == "19000000.00"
    assert dist2["carry_amount"] == "400000.00"

    acc = client.get(f"/funds/{fid}/capital-accounts", headers=h).json()
    accounts = {a["lp_id"]: a for a in acc["accounts"]}
    # LP net total = 22,000,000 - 400,000 carry = 21,600,000 -> 10,800,000 each
    assert accounts[lp1]["distributed"] == "10800000.00"
    assert accounts[lp2]["distributed"] == "10800000.00"
    assert acc["totals"]["distributed"] == "21600000.00"


def test_distribution_waterfall_hurdle_and_catchup(client):
    import datetime as dt

    from app.clock import today_ist

    h = auth_headers(client)
    eid, fid = _fund(client, h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "10000000"}, headers=h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP Two", "commitment": "10000000"}, headers=h)
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "1.0"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)

    # one year later: pref = 20M x 8% = 1,600,000 (simple, 365 days)
    later = (today_ist() + dt.timedelta(days=365)).isoformat()
    # 24M gross: 20M ROC + 1.6M pref + 400k GP catch-up (0.2/0.8 x pref)
    # + 2M split 80/20 -> carry total 800,000
    dist = client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "24000000", "kind": "profit", "date": later},
        headers=h,
    ).json()
    assert dist["roc_amount"] == "20000000.00"
    assert dist["pref_amount"] == "1600000.00"
    assert dist["catchup_amount"] == "400000.00"
    assert dist["carry_amount"] == "800000.00"

    # past the catch-up, further profit splits straight 80/20
    dist2 = client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "1000000", "kind": "profit", "date": later},
        headers=h,
    ).json()
    assert dist2["carry_amount"] == "200000.00"
    assert dist2["roc_amount"] == "0.00"
    assert dist2["pref_amount"] == "0.00"
    assert dist2["catchup_amount"] == "0.00"


def test_capital_call_requires_lps(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    r = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.25"}, headers=h)
    assert r.status_code == 400


def test_portfolio_tracking(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    inv = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "Acme Pvt Ltd", "amount": "5000000", "ownership_pct": "12.5"},
        headers=h,
    )
    assert inv.status_code == 201
    items = client.get(f"/funds/{fid}/portfolio", headers=h).json()
    assert len(items) == 1 and items[0]["company_name"] == "Acme Pvt Ltd"


def test_fund_access_control(client):
    owner = auth_headers(client, email="gp@fund.in")
    _, fid = _fund(client, owner)
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/funds/{fid}/lps", headers=outsider).status_code == 403
    assert (
        client.post(
            f"/funds/{fid}/lps", json={"name": "X", "commitment": "1"}, headers=outsider
        ).status_code
        == 403
    )
