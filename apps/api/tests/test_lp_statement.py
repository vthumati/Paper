from tests.conftest import auth_headers


def test_lp_statement_document_and_portal(client):
    gp = auth_headers(client, email="gp@fund.in")
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=gp).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=gp
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=gp
    ).json()["id"]
    lp = client.post(
        f"/funds/{fid}/lps",
        json={"name": "Anita LP", "email": "anita@lp.in", "commitment": "10000000"},
        headers=gp,
    ).json()["id"]
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "0.25"}, headers=gp).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=gp)

    doc = client.post(f"/funds/{fid}/lps/{lp}/statement", headers=gp)
    assert doc.status_code == 201
    body = doc.json()["content"]
    assert "Anita LP" in body and "Alpha Fund I" in body
    assert "Commitment:            INR 10000000.00" in body
    assert "Capital contributed:   INR 2500000.00" in body
    assert "Undrawn commitment:    INR 7500000.00" in body

    # the LP sees the statement in their portal without any explicit grant
    anita = auth_headers(client, email="anita@lp.in")
    portal = client.get("/portal", headers=anita).json()
    stmts = portal["funds"][0]["statements"]
    assert len(stmts) == 1 and "Anita LP" in stmts[0]["title"]

    # unknown LP 404s
    assert client.post(f"/funds/{fid}/lps/nope/statement", headers=gp).status_code == 404
