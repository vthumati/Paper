import datetime as dt

from app.clock import today_ist
from tests.conftest import auth_headers


def _fy_end() -> str:
    t = today_ist()
    y = t.year + 1 if t.month > 3 else t.year
    return dt.date(y, 3, 31).isoformat()


def test_form_64c_64d_generation(client):
    gp = auth_headers(client, email="gp@tax.in")
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=gp).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Tax Fund I", "type": "fund"}, headers=gp
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "hurdle_pct": "0"}, headers=gp
    ).json()["id"]
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "Anita LP", "email": "anita@lp.in", "commitment": "10000000"},
        headers=gp,
    )
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "1.0"}, headers=gp).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=gp)
    # a return-of-capital distribution today (inside the FY window)
    client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "2000000", "kind": "return_of_capital"},
        headers=gp,
    )

    r = client.post(
        f"/funds/{fid}/tax-statements", json={"financial_year_end": _fy_end()}, headers=gp
    ).json()
    assert r["form_64c"] == 1 and r["form_64d"] == 1
    assert r["total_distributed"] == "2000000.00"

    # the LP sees their 64C alongside statements in the portal
    anita = auth_headers(client, email="anita@lp.in")
    portal = client.get("/portal", headers=anita).json()
    titles = [s["title"] for s in portal["funds"][0]["statements"]]
    assert any("Form 64C" in t for t in titles)

    # 64D lands in the fund entity's documents
    docs = client.get(f"/entities/{eid}/documents", headers=gp).json()
    assert any("Form 64D" in d["title"] for d in docs)
