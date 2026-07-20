from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "carry_pct": "0.20"}, headers=h
    ).json()["id"]
    return eid, fid


def _pay_all(client, h, fid):
    for c in client.get(f"/funds/{fid}/capital-calls", headers=h).json():
        for n in c["notices"]:
            client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=h)


def test_financials_empty_fund_balances_at_zero(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    fin = client.get(f"/funds/{fid}/financials", headers=h).json()
    assert fin["balances"] is True
    assert fin["balance_sheet"]["net_assets"] == "0.00"


def test_financials_tie_out(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP A", "commitment": "50000000"}, headers=h)
    # call & pay 40% -> 20,000,000 paid in
    client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.40"}, headers=h)
    _pay_all(client, h, fid)
    # invest 15,000,000, mark to 25,000,000
    iid = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "Acme", "amount": "15000000"}, headers=h
    ).json()["id"]
    client.put(
        f"/funds/{fid}/portfolio/{iid}/mark", json={"current_value": "25000000"}, headers=h
    )
    # profit distribution of 6,000,000
    client.post(f"/funds/{fid}/distributions", json={"gross_amount": "6000000", "kind": "profit"}, headers=h)

    fin = client.get(f"/funds/{fid}/financials", headers=h).json()
    bs, op, rf, cf = fin["balance_sheet"], fin["operations"], fin["capital_roll_forward"], fin["cash_flow"]

    assert op["unrealized_appreciation"] == "10000000.00"       # 25m - 15m
    assert bs["investments_at_fair_value"] == "25000000.00"
    # cash = 20m in - 15m invested - net dist - carry - fees
    # net assets ties to ending partners' capital, by construction
    assert fin["balances"] is True
    assert bs["net_assets"] == rf["ending_net_assets"]
    # total assets = investments + cash
    assert bs["total_assets"] == bs["net_assets"]              # no liabilities
    assert cf["contributions"] == "20000000.00"
    assert fin["disclosures"]["uncalled"] == "30000000.00"     # 50m committed - 20m paid


def test_financials_report_document(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    client.post(f"/funds/{fid}/lps", json={"name": "LP A", "commitment": "10000000"}, headers=h)
    client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.5"}, headers=h)
    _pay_all(client, h, fid)
    r = client.post(f"/funds/{fid}/financials/report", headers=h)
    assert r.status_code == 201
    doc = r.json()
    assert doc["subject_type"] == "fund_financials"
