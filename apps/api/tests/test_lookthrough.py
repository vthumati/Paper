"""Fund look-through / Schedule of Investments (FR-J-11, Mantle gap): the SOI
statement (GP) and each LP's pro-rata exposure to the underlying holdings."""
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha AIF", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "structure": "trust"}, headers=h
    ).json()["id"]
    return eid, fid


def _add(client, h, fid, name, amount, value=None, own="0"):
    inv = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": name, "amount": amount, "ownership_pct": own},
        headers=h,
    ).json()
    if value is not None:
        client.put(
            f"/funds/{fid}/portfolio/{inv['id']}/mark",
            json={"current_value": value}, headers=h,
        )
    return inv["id"]


def test_schedule_of_investments(client):
    h = auth_headers(client, email="gp@alpha.in")
    _, fid = _fund(client, h)
    _add(client, h, fid, "Zeta", "10000000", value="25000000", own="12")  # 2.5x
    _add(client, h, fid, "Yoto", "5000000")  # unmarked -> at cost, 1.0x

    soi = client.get(f"/funds/{fid}/soi", headers=h).json()
    assert soi["totals"]["cost"] == "15000000.00"
    assert soi["totals"]["current_value"] == "30000000.00"
    assert soi["totals"]["unrealized_gain"] == "15000000.00"
    assert soi["totals"]["moic"] == "2.00"
    # sorted by value desc; Zeta first, MOIC 2.5, unmarked Yoto held at cost
    z = next(x for x in soi["holdings"] if x["company_name"] == "Zeta")
    y = next(x for x in soi["holdings"] if x["company_name"] == "Yoto")
    assert z["moic"] == "2.50" and z["marked"] is True
    assert y["moic"] == "1.00" and y["marked"] is False
    assert y["current_value"] == "5000000.00"
    # %NAV: Zeta 25/30, Yoto 5/30
    assert z["pct_of_nav"] == 83.33
    assert soi["holdings"][0]["company_name"] == "Zeta"


def test_soi_report_document(client):
    h = auth_headers(client, email="gp2@alpha.in")
    _, fid = _fund(client, h)
    _add(client, h, fid, "Zeta", "1000000", value="3000000")
    r = client.post(f"/funds/{fid}/soi/report", headers=h)
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["type"] == "soi"
    assert "Zeta" in doc["content"]
    assert "SCHEDULE OF INVESTMENTS" in doc["content"]
    assert "Blended MOIC: 3.00" in doc["content"]


def test_lp_look_through_prorata(client):
    gp = auth_headers(client, email="gp3@alpha.in")
    _, fid = _fund(client, gp)
    # two LPs, 3:1 commitment split -> shares 75% / 25%
    lp_a = client.post(f"/funds/{fid}/lps", json={"name": "LP A", "email": "lpa@x.in", "commitment": "30000000"}, headers=gp).json()["id"]
    client.post(f"/funds/{fid}/lps", json={"name": "LP B", "email": "lpb@x.in", "commitment": "10000000"}, headers=gp)
    _add(client, gp, fid, "Zeta", "8000000", value="20000000")

    # before any drawdown, share falls back to commitment share (75% for LP A)
    portal = client.get("/portal", headers=auth_headers(client, email="lpa@x.in")).json()
    fund_entry = portal["funds"][0]
    lt = fund_entry["look_through"]
    assert lt["share_pct"] == 75.0
    z = lt["holdings"][0]
    assert z["company_name"] == "Zeta"
    # 75% of the fund's ₹2cr mark = ₹1.5cr look-through value
    assert z["look_through_value"] == "15000000.00"
    assert z["look_through_cost"] == "6000000.00"
    assert lt["totals"]["look_through_value"] == "15000000.00"
    _ = lp_a


def test_look_through_drawdown_weighted(client):
    gp = auth_headers(client, email="gp4@alpha.in")
    _, fid = _fund(client, gp)
    lp_a = client.post(f"/funds/{fid}/lps", json={"name": "LP A", "email": "da@x.in", "commitment": "20000000"}, headers=gp).json()["id"]
    client.post(f"/funds/{fid}/lps", json={"name": "LP B", "email": "db@x.in", "commitment": "20000000"}, headers=gp)
    _add(client, gp, fid, "Zeta", "4000000", value="8000000")
    # equal commitments -> 50% share before any drawdown
    portal = client.get("/portal", headers=auth_headers(client, email="da@x.in")).json()
    assert portal["funds"][0]["look_through"]["share_pct"] == 50.0

    # call 50%; pay ONLY LP A's notice -> paid-in becomes 100% LP A, so
    # look-through shifts to paid-in weighting
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.5"}, headers=gp).json()
    a_notice = next(n for n in call["notices"] if n["lp_id"] == lp_a)
    client.post(f"/funds/{fid}/drawdown-notices/{a_notice['id']}/pay", headers=gp)

    portal = client.get("/portal", headers=auth_headers(client, email="da@x.in")).json()
    lt = portal["funds"][0]["look_through"]
    assert lt["share_pct"] == 100.0
    # LP A now sees the full ₹80L mark through their position
    assert lt["holdings"][0]["look_through_value"] == "8000000.00"
