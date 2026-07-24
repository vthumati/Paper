from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "X Fund", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "carry_pct": "0.20"}, headers=h
    ).json()["id"]
    return eid, fid


def test_ddq_workflow_and_regulator_tag(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    # presets now carry an SEC/SEBI regulator tag
    listing = client.get(f"/funds/{fid}/ddq", headers=h).json()
    regs = {p["regulator"] for p in listing["presets"]}
    assert "sec" in regs and "sebi" in regs

    e = client.post(
        f"/funds/{fid}/ddq",
        json={"question": "Form ADV registration?", "category": "Governance & compliance",
              "regulator": "sec", "assignee": "Asha"},
        headers=h,
    ).json()
    assert e["status"] == "draft" and e["regulator"] == "sec" and e["assignee"] == "Asha"

    # collaborative workflow: answer, assign reviewer, move to approved
    upd = client.put(
        f"/funds/{fid}/ddq/{e['id']}",
        json={"answer": "Registered ERA.", "status": "approved", "reviewer": "Ravi"},
        headers=h,
    ).json()
    assert upd["status"] == "approved" and upd["reviewer"] == "Ravi" and upd["answered"] is True


def test_multi_currency_fx_translation(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)  # fund currency defaults to INR
    # a USD-denominated holding: cost $100,000, marked at $150,000
    inv = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "US NewCo", "amount": "100000", "currency": "USD"},
        headers=h,
    ).json()
    assert inv["currency"] == "USD"
    client.put(
        f"/funds/{fid}/portfolio/{inv['id']}/mark", json={"current_value": "150000"}, headers=h
    )
    # before any FX rate: SOI totals equal the raw USD number (no rate → unchanged)
    soi0 = client.get(f"/funds/{fid}/soi", headers=h).json()
    assert soi0["totals"]["current_value"] == "150000.00"

    # set USD→INR = 83; the holding now translates into the fund currency
    client.post(f"/funds/{fid}/fx-rates", json={"currency": "USD", "as_of": "2025-01-01", "rate": "83"}, headers=h)
    soi = client.get(f"/funds/{fid}/soi", headers=h).json()
    hold = soi["holdings"][0]
    assert hold["currency"] == "USD" and hold["native_value"] == "150000.00"
    assert hold["current_value"] == "12450000.00"  # 150,000 × 83
    assert soi["totals"]["cost"] == "8300000.00"    # 100,000 × 83
    # NAV in fund performance is translated too
    perf = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert perf["nav"] == "12450000.00"


def test_single_currency_fund_unaffected_by_fx(client):
    h = auth_headers(client)
    _, fid = _fund(client, h)
    inv = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "INR Co", "amount": "5000000"}, headers=h
    ).json()
    assert inv["currency"] == "INR"  # defaulted to the fund currency
    soi = client.get(f"/funds/{fid}/soi", headers=h).json()
    assert soi["totals"]["cost"] == "5000000.00"
    perf = client.get(f"/funds/{fid}/performance", headers=h).json()
    assert perf["nav"] == "5000000.00"
