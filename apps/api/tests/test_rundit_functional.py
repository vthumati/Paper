"""Rundit functional batch: follow-on investment rounds, fund expense ledger,
company notes, CSV exports, and investor-update audiences."""
from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def _inv(client, h, fid, name="Acme", amount="10000000"):
    return client.post(
        f"/funds/{fid}/portfolio",
        json={"company_name": name, "amount": amount, "invested_on": "2025-06-01"},
        headers=h,
    ).json()["id"]


def test_follow_on_rounds_grow_total_cost(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid)

    r = client.post(
        f"/funds/{fid}/portfolio/{iid}/rounds",
        json={"amount": "5000000", "round_label": "Series A", "invested_on": "2026-03-01"},
        headers=h,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["initial"]["amount"] == "10000000.00"
    assert data["rounds"][0]["round_label"] == "Series A"
    assert data["total_cost"] == "15000000.00"

    # the running total flows into the SOI cost
    soi = client.get(f"/funds/{fid}/soi", headers=h).json()
    assert soi["holdings"][0]["cost"] == "15000000.00"

    # invalid amount rejected at the schema layer
    assert client.post(
        f"/funds/{fid}/portfolio/{iid}/rounds", json={"amount": "0"}, headers=h
    ).status_code == 422


def test_fund_expenses_flow_into_financials(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    ls = client.post(
        f"/funds/{fid}/expenses",
        json={"date": "2026-04-01", "category": "audit", "amount": "500000", "note": "FY26 audit"},
        headers=h,
    ).json()
    assert ls["total"] == "500000.00" and ls["expenses"][0]["category"] == "audit"

    fin = client.get(f"/funds/{fid}/financials", headers=h).json()
    assert fin["operations"]["fund_expenses"] == "500000.00"
    assert fin["cash_flow"]["fund_expenses_paid"] == "-500000.00"
    assert fin["balances"] is True  # statements still tie out

    eid = ls["expenses"][0]["id"]
    assert client.delete(f"/funds/{fid}/expenses/{eid}", headers=h).status_code == 204
    assert client.get(f"/funds/{fid}/expenses", headers=h).json()["total"] == "0.00"


def test_company_notes_crud(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid)
    notes = client.post(
        f"/funds/{fid}/portfolio/{iid}/notes",
        json={"body": "Founder call went well — pushing for the board seat."},
        headers=h,
    ).json()
    assert len(notes) == 1 and notes[0]["author"] is not None
    nid = notes[0]["id"]
    assert client.delete(f"/funds/{fid}/portfolio/{iid}/notes/{nid}", headers=h).status_code == 204
    assert client.get(f"/funds/{fid}/portfolio/{iid}/notes", headers=h).json() == []


def test_csv_exports(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid)
    client.post(
        f"/funds/{fid}/portfolio/{iid}/kpis",
        json={"period_label": "Q1", "as_of": "2026-03-31", "revenue": "1000000"},
        headers=h,
    )
    for path, must_contain in [
        ("export/holdings", "Acme"),
        ("export/capital-accounts", "lp_name"),
        ("export/kpis", "Q1"),
    ]:
        r = client.get(f"/funds/{fid}/{path}", headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert must_contain in r.text


def test_update_audience_scopes_visibility(client):
    owner = auth_headers(client, email="founder@acme.in")
    tid = client.post("/tenants", json={"name": "Acme", "type": "company"}, headers=owner).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Acme Pvt Ltd", "type": "pvt_ltd"}, headers=owner
    ).json()["id"]
    for email in ("lp@seedfund.in", "angel@solo.in"):
        client.post(f"/entities/{eid}/investor-access", json={"email": email}, headers=owner)

    # audience-restricted update: only lp@seedfund.in sees it
    upd = client.post(
        f"/entities/{eid}/investor-updates",
        json={"title": "For the fund only", "body": "Confidential.", "audience": ["lp@seedfund.in"]},
        headers=owner,
    ).json()
    assert upd["audience"] == ["lp@seedfund.in"]

    lp = auth_headers(client, email="lp@seedfund.in")
    angel = auth_headers(client, email="angel@solo.in")
    lp_updates = client.get("/portal", headers=lp).json()["companies"][0]["updates"]
    angel_updates = client.get("/portal", headers=angel).json()["companies"][0]["updates"]
    assert [u["title"] for u in lp_updates] == ["For the fund only"]
    assert angel_updates == []

    # view recording honours the audience too
    assert client.post(f"/portal/updates/{upd['id']}/view", headers=lp).status_code == 200
    assert client.post(f"/portal/updates/{upd['id']}/view", headers=angel).status_code == 404


# --- QA/polish pass fixes ----------------------------------------------------
def test_deleting_custom_metric_removes_its_alert_rules(client):
    """QA: an alert rule on custom.<key> must not linger as a no-op once its
    metric definition is deleted."""
    h = auth_headers(client)
    fid = _fund(client, h)
    d = client.post(
        f"/funds/{fid}/kpi-definitions", json={"label": "CO2 tonnes", "unit": "number"}, headers=h
    ).json()
    key = d["key"]
    rule = client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": f"custom.{key}", "comparator": "gt", "threshold": "100"},
        headers=h,
    )
    assert rule.status_code == 201
    assert len(client.get(f"/funds/{fid}/alert-rules", headers=h).json()["rules"]) == 1

    assert client.delete(f"/funds/{fid}/kpi-definitions/{d['id']}", headers=h).status_code == 204
    # the orphaned rule is gone, not left referencing an unknown metric
    assert client.get(f"/funds/{fid}/alert-rules", headers=h).json()["rules"] == []


def test_fund_lp_can_record_update_view(client):
    """QA: a fund LP sees fund updates in the portal but has no company-level
    InvestorAccess row — view recording must still work for them."""
    owner = auth_headers(client, email="gp@house.in")
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=owner).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Beta Fund I", "type": "fund"}, headers=owner
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=owner).json()["id"]
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "Pension LP", "email": "lp@pension.in", "commitment": "50000000"},
        headers=owner,
    )
    # fund publishes an update on its own entity
    upd = client.post(
        f"/entities/{eid}/investor-updates",
        json={"title": "Q2 fund letter", "body": "Portfolio is tracking well."},
        headers=owner,
    ).json()

    lp = auth_headers(client, email="lp@pension.in")
    seen = client.get("/portal", headers=lp).json()["funds"][0]["updates"]
    assert [u["title"] for u in seen] == ["Q2 fund letter"]
    # the LP can record engagement despite having no InvestorAccess row
    r = client.post(f"/portal/updates/{upd['id']}/view", headers=lp)
    assert r.status_code == 200 and r.json()["view_count"] == 1
