"""Fund ↔ startup seam: link a portfolio holding to the company's Paper entity
and pull the company's own reported financials into the fund's monitoring."""
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def _company(client, h, name="Portfolio Co"):
    tid = client.post("/tenants", json={"name": name + " Grp", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": name, "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_link_and_pull_financials(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    cid = _company(client, h, "Acme Labs")

    # the company reports monthly financials in its own workspace
    client.post(
        f"/entities/{cid}/finance/snapshots",
        json={"period": "2026-06-01", "cash_balance": "3000000", "monthly_burn": "500000", "revenue": "1800000"},
        headers=h,
    )

    # it shows up as a linkable company for the fund
    links = client.get(f"/funds/{fid}/linkable-companies", headers=h).json()
    assert cid in [c["id"] for c in links]

    # add a holding linked to it — name is synced from the entity
    inv = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "ignored", "company_entity_id": cid, "amount": "5000000"},
        headers=h,
    ).json()
    assert inv["company_entity_id"] == cid
    assert inv["company_name"] == "Acme Labs"

    # pull the company's latest financials in as a KPI period — no request round-trip
    kpi = client.post(f"/funds/{fid}/portfolio/{inv['id']}/pull-financials", headers=h)
    assert kpi.status_code == 200
    body = kpi.json()
    assert body["revenue"] == "1800000.00"
    assert body["cash"] == "3000000.00"
    assert body["monthly_burn"] == "500000.00"

    # it flows into monitoring like any reported KPI
    mon = client.get(f"/funds/{fid}/portfolio-monitoring", headers=h).json()
    acme = next(c for c in mon["companies"] if c["company_name"] == "Acme Labs")
    assert acme["latest"]["revenue"] == "1800000.00"

    # pulling again updates the same period rather than duplicating
    client.post(
        f"/entities/{cid}/finance/snapshots",
        json={"period": "2026-06-01", "cash_balance": "2500000", "monthly_burn": "500000", "revenue": "2000000"},
        headers=h,
    )
    again = client.post(f"/funds/{fid}/portfolio/{inv['id']}/pull-financials", headers=h).json()
    assert again["revenue"] == "2000000.00"
    hist = client.get(f"/funds/{fid}/portfolio/{inv['id']}/kpis", headers=h).json()
    assert len([k for k in hist if k["period_label"] == again["period_label"]]) == 1


def test_pull_requires_link(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    inv = client.post(
        f"/funds/{fid}/portfolio", json={"company_name": "Unlinked Co", "amount": "1000000"}, headers=h
    ).json()
    assert client.post(f"/funds/{fid}/portfolio/{inv['id']}/pull-financials", headers=h).status_code == 400


def test_cannot_link_company_without_access(client):
    owner = auth_headers(client, email="gp@house.in")
    fid = _fund(client, owner)
    # a company owned by someone else
    other = auth_headers(client, email="founder@other.in")
    cid = _company(client, other, "Not Yours")
    # the GP can neither see it as linkable nor link to it
    links = client.get(f"/funds/{fid}/linkable-companies", headers=owner).json()
    assert cid not in [c["id"] for c in links]
    r = client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": "x", "company_entity_id": cid, "amount": "1000000"},
        headers=owner,
    )
    assert r.status_code == 403
