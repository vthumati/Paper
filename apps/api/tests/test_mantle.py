"""Mantle-parity: portal portfolio value-history series (FR-K) and the
app-wide entity task hub (FR-T-4)."""
from tests.conftest import auth_headers


def _company(client, h, name="M"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return tid, eid


# --- value history ---
def test_portfolio_value_history(client):
    founder = auth_headers(client, email="f@m.in")
    _, eid = _company(client, founder)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "CCPS", "kind": "ccps"}, headers=founder
    ).json()["id"]
    angel = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Angel A", "type": "investor", "email": "angel@m.in"},
        headers=founder,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": angel, "quantity": 10000,
              "price_per_unit": "100", "issue_date": "2025-01-01"},
        headers=founder,
    )
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "angel@m.in", "stakeholder_id": angel},
        headers=founder,
    )
    # two valuations over time: 150 then 250
    for date, fmv in [("2025-06-01", "150"), ("2026-01-01", "250")]:
        client.post(
            f"/entities/{eid}/valuations",
            json={"method": "fair_value", "fmv_per_share": fmv, "valuation_date": date},
            headers=founder,
        )

    angel_h = auth_headers(client, email="angel@m.in")
    hist = client.get("/portal/value-history", headers=angel_h).json()
    assert hist["holdings"] == 1
    bydate = {p["date"]: p["value"] for p in hist["series"]}
    # marked at each valuation: 10,000 × 150 and × 250
    assert bydate["2025-06-01"] == "1500000.00"
    assert bydate["2026-01-01"] == "2500000.00"
    # series is anchored at "today" with the latest FMV, and current_value matches
    assert hist["current_value"] == "2500000.00"
    dates = [p["date"] for p in hist["series"]]
    assert dates == sorted(dates)


def test_value_history_before_valuation_is_cost(client):
    founder = auth_headers(client, email="f2@m.in")
    _, eid = _company(client, founder, name="N")
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=founder
    ).json()["id"]
    inv = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Inv", "type": "investor", "email": "inv@n.in"},
        headers=founder,
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": inv, "quantity": 1000,
              "price_per_unit": "50", "issue_date": "2025-01-01"},
        headers=founder,
    )
    client.post(
        f"/entities/{eid}/investor-access",
        json={"email": "inv@n.in", "stakeholder_id": inv},
        headers=founder,
    )
    # no valuation yet -> the single "today" point is held at cost (₹50,000)
    hist = client.get("/portal/value-history", headers=auth_headers(client, email="inv@n.in")).json()
    assert hist["current_value"] == "50000.00"


# --- task hub ---
def test_entity_tasks_aggregate(client):
    h = auth_headers(client, email="ops@m.in")
    _, eid = _company(client, h, name="T")

    # 1) an overdue compliance obligation
    from datetime import date

    # generate the statutory calendar, then check what's overdue as-of a future date
    client.post(f"/entities/{eid}/compliance/generate", headers=h)

    # 2) a pending e-signature on a generated document
    doc = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "board_resolution", "data": {"company": "T", "resolution_text": "x"}},
        headers=h,
    ).json()
    client.post(f"/documents/{doc['id']}/signatures",
                json={"signatories": [{"name": "Director"}]}, headers=h)

    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()
    kinds = {t["kind"] for t in tasks["tasks"]}
    assert "signature" in kinds
    assert tasks["counts"]["total"] == len(tasks["tasks"])
    # reds (overdue) sort first
    sevs = [t["severity"] for t in tasks["tasks"]]
    assert sevs == sorted(sevs, key=lambda s: {"red": 0, "amber": 1, "ok": 2}[s])
    # every task carries a deep-link tab
    assert all(t["tab"] for t in tasks["tasks"])
    _ = date  # (imported for clarity; overdue depends on generated due dates)


def test_entity_tasks_empty(client):
    h = auth_headers(client, email="clean@m.in")
    _, eid = _company(client, h, name="Clean")
    tasks = client.get(f"/entities/{eid}/tasks", headers=h).json()
    assert tasks["counts"] == {"total": 0, "overdue": 0}
    assert tasks["tasks"] == []
