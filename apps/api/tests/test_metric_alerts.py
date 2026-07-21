"""Metric alert rules (Visible-style thresholds): CRUD + validation, and
breach evaluation surfacing as portfolio signals."""
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


def test_rule_crud_and_validation(client):
    h = auth_headers(client)
    fid = _fund(client, h)

    r = client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": "runway_months", "comparator": "lt", "threshold": "9", "severity": "high"},
        headers=h,
    )
    assert r.status_code == 201 and r.json()["threshold"] == "9.00"

    # unknown metric -> 400; bad comparator -> 422 at the schema layer
    assert client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": "made_up", "comparator": "lt", "threshold": "1"},
        headers=h,
    ).status_code == 400
    assert client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": "revenue", "comparator": "between", "threshold": "1"},
        headers=h,
    ).status_code == 422

    ls = client.get(f"/funds/{fid}/alert-rules", headers=h).json()
    assert len(ls["rules"]) == 1
    assert any(m["key"] == "runway_months" for m in ls["metrics"])

    rid = ls["rules"][0]["id"]
    assert client.delete(f"/funds/{fid}/alert-rules/{rid}", headers=h).status_code == 204
    assert client.delete(f"/funds/{fid}/alert-rules/{rid}", headers=h).status_code == 404


def test_breach_fires_signal_with_rule_severity(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid, "Acme")
    # revenue 10L; runway 20 months (well above the built-in low-runway rule)
    client.post(
        f"/funds/{fid}/portfolio/{iid}/kpis",
        json={"period_label": "Q1", "as_of": "2026-03-31", "revenue": "1000000",
              "cash": "40000000", "monthly_burn": "2000000"},
        headers=h,
    )
    client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": "revenue", "comparator": "lt", "threshold": "2000000", "severity": "high"},
        headers=h,
    )

    s = client.get(f"/funds/{fid}/signals", headers=h).json()
    alerts = [
        sig
        for c in s["companies"]
        for sig in c["signals"]
        if sig["kind"] == "metric_alert"
    ]
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "high"
    assert "Revenue" in alerts[0]["message"] and "below" in alerts[0]["message"]
    assert s["totals"]["high"] == 1

    # not breached in the other direction: a gt rule on the same value stays quiet
    ls = client.get(f"/funds/{fid}/alert-rules", headers=h).json()
    client.delete(f"/funds/{fid}/alert-rules/{ls['rules'][0]['id']}", headers=h)
    client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": "revenue", "comparator": "gt", "threshold": "2000000"},
        headers=h,
    )
    s = client.get(f"/funds/{fid}/signals", headers=h).json()
    assert not any(
        sig["kind"] == "metric_alert" for c in s["companies"] for sig in c["signals"]
    )


def test_custom_metric_alert(client):
    h = auth_headers(client)
    fid = _fund(client, h)
    iid = _inv(client, h, fid, "Acme")
    client.post(f"/funds/{fid}/kpi-definitions", json={"label": "GMV", "unit": "inr"}, headers=h)
    client.post(
        f"/funds/{fid}/portfolio/{iid}/kpis",
        json={"period_label": "Q1", "as_of": "2026-03-31", "custom": {"gmv": "5000000"}},
        headers=h,
    )
    client.post(
        f"/funds/{fid}/alert-rules",
        json={"metric": "custom.gmv", "comparator": "gt", "threshold": "4000000"},
        headers=h,
    )
    s = client.get(f"/funds/{fid}/signals", headers=h).json()
    alerts = [
        sig for c in s["companies"] for sig in c["signals"] if sig["kind"] == "metric_alert"
    ]
    assert len(alerts) == 1 and alerts[0]["severity"] == "warn"
    assert "GMV" in alerts[0]["message"] and "above" in alerts[0]["message"]
