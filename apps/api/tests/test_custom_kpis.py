from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    return client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=h).json()["id"]


def _inv(client, h, fid, name, amount="10000000"):
    return client.post(
        f"/funds/{fid}/portfolio", json={"company_name": name, "amount": amount}, headers=h
    ).json()["id"]


def test_definitions_crud_and_presets(client):
    h = auth_headers(client)
    fid = _fund(client, h)

    r = client.post(f"/funds/{fid}/kpi-definitions", json={"label": "GMV (monthly)", "unit": "inr"}, headers=h)
    assert r.status_code == 201
    assert r.json()["key"] == "gmv_monthly"  # slug derived from the label
    # duplicate key -> 409; bad unit -> 422 at the schema layer
    assert client.post(f"/funds/{fid}/kpi-definitions", json={"label": "GMV monthly"}, headers=h).status_code == 409
    assert client.post(f"/funds/{fid}/kpi-definitions", json={"label": "NPS", "unit": "widgets"}, headers=h).status_code == 422

    # ESG preset added like any definition
    ls = client.get(f"/funds/{fid}/kpi-definitions", headers=h).json()
    preset = ls["presets"][0]
    client.post(f"/funds/{fid}/kpi-definitions", json=preset, headers=h)  # preset carries its key
    defs = client.get(f"/funds/{fid}/kpi-definitions", headers=h).json()["definitions"]
    assert [d["key"] for d in defs] == ["gmv_monthly", "female_headcount_pct"]

    # delete drops it from the list
    did = defs[0]["id"]
    assert client.delete(f"/funds/{fid}/kpi-definitions/{did}", headers=h).status_code == 204
    defs = client.get(f"/funds/{fid}/kpi-definitions", headers=h).json()["definitions"]
    assert [d["key"] for d in defs] == ["female_headcount_pct"]
    assert client.delete(f"/funds/{fid}/kpi-definitions/{did}", headers=h).status_code == 404


def test_custom_values_stored_and_filtered(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid, "Acme")
    client.post(f"/funds/{fid}/kpi-definitions", json={"label": "GMV", "unit": "inr"}, headers=h)

    hist = client.post(
        f"/funds/{fid}/portfolio/{iid}/kpis",
        json={"period_label": "Q1", "as_of": "2026-03-31", "revenue": "1000000",
              "custom": {"gmv": "5000000", "undefined_metric": "42"}},
        headers=h,
    ).json()
    # only defined keys survive
    assert hist[0]["custom"] == {"gmv": "5000000"}

    mon = client.get(f"/funds/{fid}/portfolio-monitoring", headers=h).json()
    assert mon["companies"][0]["latest"]["custom"] == {"gmv": "5000000"}


def test_benchmarks_medians_and_rows(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    client.post(f"/funds/{fid}/kpi-definitions", json={"label": "GMV", "unit": "inr"}, headers=h)

    # three companies; medians over the latest period of each
    for name, rev, cash, gmv in [
        ("Low Co", "1000000", "10000000", "2000000"),
        ("Mid Co", "2000000", "20000000", None),
        ("High Co", "3000000", "60000000", "8000000"),
    ]:
        iid = _inv(client, h, fid, name)
        body = {"period_label": "Q2", "as_of": "2026-06-30", "revenue": rev,
                "cash": cash, "monthly_burn": "2000000", "headcount": 10}
        if gmv:
            body["custom"] = {"gmv": gmv}
        client.post(f"/funds/{fid}/portfolio/{iid}/kpis", json=body, headers=h)

    b = client.get(f"/funds/{fid}/benchmarks", headers=h).json()
    assert [m["key"] for m in b["metrics"]] == [
        "revenue", "revenue_growth_pct", "monthly_burn", "runway_months", "headcount", "custom.gmv",
    ]
    assert b["medians"]["revenue"] == 2000000.0
    assert b["medians"]["runway_months"] == 10.0          # 5 / 10 / 30 months
    assert b["medians"]["custom.gmv"] == 5000000.0        # median of the two reporters
    assert b["medians"]["revenue_growth_pct"] is None     # single period, no growth
    by = {r["company_name"]: r["values"] for r in b["rows"]}
    assert by["Mid Co"]["custom.gmv"] is None
    assert by["High Co"]["runway_months"] == 30.0

    # distribution stats (Visible-style quartiles, inclusive method)
    rev = b["stats"]["revenue"]
    assert rev == {
        "min": 1000000.0, "q1": 1500000.0, "median": 2000000.0,
        "q3": 2500000.0, "max": 3000000.0, "total": 6000000.0,
        "avg": 2000000.0, "reporters": 3,
    }
    assert b["stats"]["revenue_growth_pct"] is None  # nobody has 2 periods yet
