from tests.conftest import auth_headers


def _company_with_investor(client, owner):
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=owner).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=owner
    ).json()["id"]
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=owner
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Seed Fund", "type": "investor", "email": "lp@seedfund.in"},
        headers=owner,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": inv, "quantity": 2000, "price_per_unit": "100", "issue_date": "2026-01-01"},
        headers=owner,
    )
    return eid, inv


def test_grant_access_and_publish_update(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid, inv = _company_with_investor(client, owner)
    acc = client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "lp@seedfund.in", "stakeholder_id": inv},
        headers=owner,
    )
    assert acc.status_code == 201 and acc.json()["status"] == "active"
    upd = client.post(
        f"/entities/{eid}/investor-updates",
        json={"title": "Q1 update", "body": "Revenue up 30%."},
        headers=owner,
    )
    assert upd.status_code == 201
    assert len(client.get(f"/entities/{eid}/investor-access", headers=owner).json()) == 1


def test_investor_sees_scoped_portal(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid, inv = _company_with_investor(client, owner)
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "lp@seedfund.in", "stakeholder_id": inv},
        headers=owner,
    )
    client.post(
        f"/entities/{eid}/investor-updates",
        json={"title": "Q1 update", "body": "Revenue up 30%."},
        headers=owner,
    )

    # the investor logs in (separate user, matched by email) and sees their portal
    investor = auth_headers(client, email="lp@seedfund.in")
    portal = client.get("/portal", headers=investor).json()
    assert portal["summary"]["companies"] == 1
    entry = portal["companies"][0]
    assert entry["entity_name"] == "Acme Pvt Ltd"
    assert len(entry["holdings"]) == 1 and entry["holdings"][0]["quantity"] == 2000
    assert len(entry["updates"]) == 1 and entry["updates"][0]["title"] == "Q1 update"
    # 2000 @ 100 = 200000 invested, reflected in the portfolio summary
    assert portal["summary"]["total_invested"] == "200000.00"


def test_portal_is_empty_for_uninvited_user(client):
    owner = auth_headers(client, email="founder@acme.in")
    _company_with_investor(client, owner)
    stranger = auth_headers(client, email="stranger@nowhere.in")
    p = client.get("/portal", headers=stranger).json()
    assert p["companies"] == [] and p["funds"] == []
    assert p["summary"]["companies"] == 0 and p["summary"]["funds"] == 0


def test_lp_sees_fund_capital_account(client):
    gp = auth_headers(client, email="gp@fund.in")
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=gp).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=gp
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=gp).json()["id"]
    # LP added with an email -> that user sees their capital account in the portal
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "LP One", "email": "lp1@invest.in", "commitment": "10000000"},
        headers=gp,
    )
    # draw 25%
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.25"}, headers=gp).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=gp)

    lp = auth_headers(client, email="lp1@invest.in")
    portal = client.get("/portal", headers=lp).json()
    assert portal["summary"]["funds"] == 1
    assert portal["summary"]["total_committed"] == "10000000.00"
    fund_entry = portal["funds"][0]
    assert fund_entry["fund_name"] == "Alpha Fund I"
    assert fund_entry["account"]["committed"] == "10000000.00"
    assert fund_entry["account"]["drawn"] == "2500000.00"


def test_shared_documents_appear_in_portal(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid, inv = _company_with_investor(client, owner)
    did = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "sha", "title": "Series A SHA", "data": {"company": "Acme"}},
        headers=owner,
    ).json()["id"]
    rid = client.post(f"/entities/{eid}/data-rooms", json={"name": "Investor room"}, headers=owner).json()["id"]
    client.post(f"/data-rooms/{rid}/items", json={"document_id": did}, headers=owner)
    client.post(f"/data-rooms/{rid}/grants", json={"email": "lp@seedfund.in"}, headers=owner)
    client.post(
        f"/entities/{eid}/investor-access", json={"email": "lp@seedfund.in", "stakeholder_id": inv}, headers=owner
    )

    investor = auth_headers(client, email="lp@seedfund.in")
    entry = client.get("/portal", headers=investor).json()["companies"][0]
    assert any(d["title"] == "Series A SHA" for d in entry["documents"])


def test_investor_cannot_access_admin_endpoints(client):
    owner = auth_headers(client, email="founder@acme.in")
    eid, inv = _company_with_investor(client, owner)
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "lp@seedfund.in", "stakeholder_id": inv},
        headers=owner,
    )
    investor = auth_headers(client, email="lp@seedfund.in")
    # investor is not a tenant member -> cannot see the full cap table or publish
    assert client.get(f"/entities/{eid}/cap-table", headers=investor).status_code == 403
    assert (
        client.post(
            f"/entities/{eid}/investor-updates",
            json={"title": "x", "body": "y"},
            headers=investor,
        ).status_code
        == 403
    )
