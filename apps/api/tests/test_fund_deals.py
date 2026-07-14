from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Deal Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]
    return eid, fid


def test_deal_pipeline_to_investment(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    deal = client.post(
        f"/funds/{fid}/deals",
        json={"company_name": "RocketCo", "sector": "SaaS", "amount": "20000000",
              "stage": "diligence", "notes": "Warm intro via LP"},
        headers=h,
    )
    assert deal.status_code == 201
    did = deal.json()["id"]

    # advance through IC to term sheet
    r = client.post(f"/deals/{did}/stage", json={"stage": "ic"}, headers=h).json()
    assert r["stage"] == "ic"
    client.post(f"/deals/{did}/stage", json={"stage": "term_sheet"}, headers=h)

    # invest: creates the portfolio position and links it
    r = client.post(f"/deals/{did}/invest", json={"ownership_pct": "12.5"}, headers=h).json()
    assert r["stage"] == "invested" and r["investment_id"]
    port = client.get(f"/funds/{fid}/portfolio", headers=h).json()
    assert port[0]["company_name"] == "RocketCo" and port[0]["amount"] == "20000000.00"
    assert port[0]["ownership_pct"] == "12.50"

    # double-invest guarded
    assert client.post(f"/deals/{did}/invest", json={}, headers=h).status_code == 409


def test_deal_access_control(client):
    owner = auth_headers(client, email="gp@deals.in")
    eid, fid = _fund(client, owner)
    did = client.post(
        f"/funds/{fid}/deals", json={"company_name": "X", "amount": "1"}, headers=owner
    ).json()["id"]
    outsider = auth_headers(client, email="outsider@evil.in")
    assert client.get(f"/funds/{fid}/deals", headers=outsider).status_code == 403
    assert client.post(f"/deals/{did}/stage", json={"stage": "ic"}, headers=outsider).status_code == 403


def test_aif_compliance_calendar(client):
    h = auth_headers(client)
    eid, fid = _fund(client, h)
    obs = client.post(
        f"/entities/{eid}/compliance/generate-aif",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    ).json()
    sebi = [o for o in obs if o["category"] == "SEBI"]
    assert len(sebi) == 6  # 4 quarterly + PPM audit + compliance test report
    forms = {o["form_code"] for o in sebi}
    assert forms == {"AIF-QR", "AIF-PPM", "AIF-CTR"}
    q4 = next(o for o in sebi if o["period_label"] == "Q4 FY2026")
    assert q4["due_date"] == "2026-04-15"
    # idempotent
    again = client.post(
        f"/entities/{eid}/compliance/generate-aif",
        json={"financial_year_end": "2026-03-31"},
        headers=h,
    ).json()
    assert len([o for o in again if o["category"] == "SEBI"]) == 6
