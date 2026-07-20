from tests.conftest import auth_headers


def _fund(client, h, carry="0.20", fee="0.02"):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund",
        json={"sebi_category": "II", "carry_pct": carry, "mgmt_fee_pct": fee},
        headers=h,
    ).json()["id"]
    return eid, fid


PLAN = {
    "fund_size": "50000000",
    "fund_life_years": 10,
    "investment_period_years": 4,
    "est_expenses": "1000000",
    "reserve_pct": "0.40",
    "avg_initial_cheque": "10000000",
    "avg_entry_valuation": "100000000",
    "projected_gross_moic": "3",
}


def test_plan_defaults_before_saved(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    p = client.get(f"/funds/{fid}/plan", headers=h).json()
    assert p["has_plan"] is False
    # no fund_size set yet -> everything zero, but the shape is complete
    assert p["derived"]["investable"] == "0.00"
    assert len(p["pacing"]) == 4  # default 4-year investment period


def test_plan_construction_math(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    p = client.put(f"/funds/{fid}/plan", json=PLAN, headers=h).json()
    d = p["derived"]
    assert p["has_plan"] is True
    assert d["lifetime_fees"] == "10000000.00"     # 2% * 50m * 10
    assert d["investable"] == "39000000.00"         # 50m - 10m fees - 1m expenses
    assert d["reserve_capital"] == "15600000.00"    # 39m * 40%
    assert d["initial_capital"] == "23400000.00"    # 39m - 15.6m
    assert d["num_initial_deals"] == 2              # 23.4m / 10m -> floor 2
    assert d["avg_entry_ownership_pct"] == "10.00"  # 10m / 100m
    # returns: gross proceeds = 39m * 3 = 117m
    assert d["gross_tvpi"] == "2.34"                # 117m / 50m
    assert d["gp_carry"] == "13400000.00"           # 20% * (117m - 50m)
    assert d["net_to_lps"] == "103600000.00"
    assert d["net_tvpi"] == "2.07"
    assert d["net_irr_pct"] is not None


def test_plan_pacing_sums_to_investable(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    p = client.put(f"/funds/{fid}/plan", json=PLAN, headers=h).json()
    pacing = p["pacing"]
    assert [row["year"] for row in pacing] == [1, 2, 3, 4]
    # cumulative deployment reaches the full investable capital by the last year
    assert pacing[-1]["cumulative"] == p["derived"]["investable"]


def test_plan_vs_actual_reads_live_ledgers(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    client.post(
        f"/funds/{fid}/lps", json={"name": "LP One", "commitment": "50000000"}, headers=h
    )
    client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "Acme", "amount": "10000000"}, headers=h
    )
    p = client.put(f"/funds/{fid}/plan", json=PLAN, headers=h).json()
    a = p["actual"]
    assert a["committed"] == "50000000.00"
    assert a["committed_vs_target_pct"] == 100.0
    assert a["deployed"] == "10000000.00"
    assert a["deals"] == 1
    assert a["deals_vs_plan_pct"] == 50.0  # 1 of 2 planned


def test_plan_upsert_replaces(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    client.put(f"/funds/{fid}/plan", json=PLAN, headers=h)
    p2 = client.put(f"/funds/{fid}/plan", json={**PLAN, "fund_size": "100000000"}, headers=h).json()
    assert p2["inputs"]["fund_size"] == "100000000.00"
    # a fresh GET reflects the update (single row per fund, not duplicated)
    g = client.get(f"/funds/{fid}/plan", headers=h).json()
    assert g["inputs"]["fund_size"] == "100000000.00"


def test_plan_requires_write_role(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    # viewer token cannot save a plan
    viewer = auth_headers(client, email="viewer@x.in")
    r = client.put(f"/funds/{fid}/plan", json=PLAN, headers=viewer)
    assert r.status_code in (403, 404)
