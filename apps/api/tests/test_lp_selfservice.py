from tests.conftest import auth_headers

LP_EMAIL = "lp-self@x.in"


def _fund_with_lp(client, h, name="Alpha Fund I", commitment="20000000"):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": name, "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    lpid = client.post(
        f"/funds/{fid}/lps",
        json={"name": "Self LP", "email": LP_EMAIL, "commitment": commitment},
        headers=h,
    ).json()["id"]
    return fid, lpid


def test_consolidated_lp_summary_across_funds(client):
    h = auth_headers(client)
    f1, _ = _fund_with_lp(client, h, "Alpha Fund I", "20000000")
    f2, _ = _fund_with_lp(client, h, "Beta Fund II", "30000000")
    # call 50% in fund 1 and pay it
    call = client.post(f"/funds/{f1}/capital-calls", json={"pct": "0.5"}, headers=h).json()
    for n in call["notices"]:
        client.post(f"/funds/{f1}/drawdown-notices/{n['id']}/pay", headers=h)

    lp_h = auth_headers(client, email=LP_EMAIL)
    p = client.get("/portal", headers=lp_h).json()
    s = p["lp_summary"]
    assert s["funds"] == 2
    assert s["committed"] == "50000000.00"     # 20m + 30m
    assert s["drawn"] == "10000000.00"          # 50% of 20m
    assert s["remaining"] == "40000000.00"
    assert s["pending_calls"] == 0              # the only notice is paid


def test_portal_capital_call_notices_and_ack(client):
    h = auth_headers(client)
    fid, _ = _fund_with_lp(client, h)
    client.post(
        f"/funds/{fid}/capital-calls",
        json={"pct": "0.25", "purpose": "Deal 1", "due_date": "2026-01-01"},  # past-due
        headers=h,
    )

    lp_h = auth_headers(client, email=LP_EMAIL)
    p = client.get("/portal", headers=lp_h).json()
    fund = p["funds"][0]
    assert len(fund["capital_calls"]) == 1
    n = fund["capital_calls"][0]
    assert n["purpose"] == "Deal 1"
    assert n["paid"] is False and n["overdue"] is True
    assert n["acknowledged_at"] is None
    assert p["lp_summary"]["pending_calls"] == 1

    # acknowledge from the portal; idempotent
    r = client.post(f"/portal/notices/{n['notice_id']}/ack", headers=lp_h)
    assert r.status_code == 200 and r.json()["acknowledged_at"] is not None
    first = r.json()["acknowledged_at"]
    again = client.post(f"/portal/notices/{n['notice_id']}/ack", headers=lp_h).json()
    assert again["acknowledged_at"] == first

    # GP sees the acknowledgement on the notice
    calls = client.get(f"/funds/{fid}/capital-calls", headers=h).json()
    assert calls[0]["notices"][0]["acknowledged_at"] is not None


def test_ack_scoped_to_own_notices(client):
    h = auth_headers(client)
    fid, _ = _fund_with_lp(client, h)
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.1"}, headers=h).json()
    nid = call["notices"][0]["id"]
    stranger = auth_headers(client, email="stranger@x.in")
    assert client.post(f"/portal/notices/{nid}/ack", headers=stranger).status_code == 404
