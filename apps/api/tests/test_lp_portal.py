from tests.conftest import auth_headers


def _fund(client, h):
    tid = client.post("/tenants", json={"name": "GP House", "type": "fund"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Alpha Fund I", "type": "fund"}, headers=h
    ).json()["id"]
    fid = client.post(
        f"/entities/{eid}/fund", json={"sebi_category": "II", "carry_pct": "0.20"}, headers=h
    ).json()["id"]
    return eid, fid


def test_banking_payment_verification_and_notice_doc(client):
    gp = auth_headers(client, email="gp@x.in")
    eid, fid = _fund(client, gp)
    client.put(
        f"/funds/{fid}/bank",
        json={"bank_name": "HDFC", "bank_account": "0012345", "bank_ifsc": "HDFC0000123"},
        headers=gp,
    )
    lp = client.post(
        f"/funds/{fid}/lps",
        json={"name": "LP One", "commitment": "10000000", "email": "lp@x.in",
              "bank_name": "ICICI", "bank_account": "55501"},
        headers=gp,
    ).json()
    assert lp["bank_name"] == "ICICI" and lp["bank_account"] == "55501"

    call = client.post(
        f"/funds/{fid}/capital-calls", json={"pct": "0.5", "purpose": "Deal 1"}, headers=gp
    ).json()
    nid = call["notices"][0]["id"]
    # drawdown notice PDF carries the fund's remittance details
    doc = client.post(f"/funds/{fid}/drawdown-notices/{nid}/notice", headers=gp).json()
    assert "DRAWDOWN NOTICE" in doc["content"] and "HDFC0000123" in doc["content"]
    assert "5000000.00" in doc["content"]

    # payment verification: mark paid with a UTR
    paid = client.post(
        f"/funds/{fid}/drawdown-notices/{nid}/pay", json={"payment_ref": "UTR12345"}, headers=gp
    ).json()
    assert paid["paid"] is True and paid["payment_ref"] == "UTR12345"

    # the LP sees the payment ref + fund bank + the downloadable notice in their portal
    lp_h = auth_headers(client, email="lp@x.in")
    portal = client.get("/portal", headers=lp_h).json()
    fund_entry = portal["funds"][0]
    assert fund_entry["bank"]["bank_ifsc"] == "HDFC0000123"
    assert fund_entry["capital_calls"][0]["payment_ref"] == "UTR12345"
    # the LP can download the drawdown notice; a stranger cannot
    assert client.get(f"/portal/documents/{doc['id']}/pdf", headers=lp_h).status_code == 200
    other = auth_headers(client, email="nobody@x.in")
    assert client.get(f"/portal/documents/{doc['id']}/pdf", headers=other).status_code == 404


def test_distribution_history_and_tax_vault(client):
    gp = auth_headers(client, email="gp2@x.in")
    eid, fid = _fund(client, gp)
    client.post(
        f"/funds/{fid}/lps",
        json={"name": "LP One", "commitment": "10000000", "email": "lp2@x.in"},
        headers=gp,
    )
    call = client.post(f"/funds/{fid}/capital-calls", json={"pct": "1.0"}, headers=gp).json()
    for n in call["notices"]:
        client.post(f"/funds/{fid}/drawdown-notices/{n['id']}/pay", headers=gp)
    client.post(
        f"/funds/{fid}/distributions",
        json={"gross_amount": "3000000", "kind": "return_of_capital"},
        headers=gp,
    )
    # audited financials doc (GP)
    fin = client.post(
        f"/funds/{fid}/audited-financials", json={"auditor_name": "PwC"}, headers=gp
    ).json()
    assert "AUDITED FINANCIAL STATEMENTS" in fin["content"] and "PwC" in fin["content"]

    lp_h = auth_headers(client, email="lp2@x.in")
    portal = client.get("/portal", headers=lp_h).json()
    fund_entry = portal["funds"][0]
    # distribution history is now surfaced per-LP
    assert len(fund_entry["distributions"]) == 1
    d0 = fund_entry["distributions"][0]
    assert d0["kind"] == "return_of_capital" and d0["amount"] == "3000000.00"
    # the LP can download the fund's audited financials from the vault
    assert client.get(f"/portal/documents/{fin['id']}/pdf", headers=lp_h).status_code == 200
    # a non-LP of the fund cannot
    stranger = auth_headers(client, email="stranger2@x.in")
    assert client.get(f"/portal/documents/{fin['id']}/pdf", headers=stranger).status_code == 404
