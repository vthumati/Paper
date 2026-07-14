from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "Imp", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "Imp Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


CSV = (
    "stakeholder_name,stakeholder_type,email,security_class,class_kind,quantity,price_per_unit,issue_date\n"
    "Aisha,founder,,Equity,equity,4000000,1,2024-05-01\n"
    "Rohan,founder,,Equity,equity,3000000,1,2024-05-01\n"
    "Blume Ventures,investor,ops@blume.vc,Seed CCPS,ccps,400000,100,2025-01-15\n"
)


def test_import_dry_run_then_apply(client):
    h = auth_headers(client)
    eid = _company(client, h)

    # dry run: full report, nothing created
    r = client.post(f"/entities/{eid}/cap-table/import", json={"csv": CSV}, headers=h).json()
    assert r["valid"] and r["summary"]["issuances"] == 3
    assert r["summary"]["classes_to_create"] == ["Equity", "Seed CCPS"]
    assert r["summary"]["total_shares"] == 7_400_000
    assert r["summary"]["warning"] is None
    assert client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"] == 0

    # apply: everything lands atomically
    r = client.post(f"/entities/{eid}/cap-table/import", json={"csv": CSV, "apply": True}, headers=h).json()
    assert r["applied"] and r["classes_created"] == 2 and r["stakeholders_created"] == 3
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 7_400_000
    assert ct["total_invested"] == "47000000.00"  # 7M @1 + 400k @100

    # re-validating warns that the ledger already has entries
    again = client.post(f"/entities/{eid}/cap-table/import", json={"csv": CSV}, headers=h).json()
    assert "appends to the ledger" in again["summary"]["warning"]


def test_import_rejects_bad_rows_atomically(client):
    h = auth_headers(client)
    eid = _company(client, h)
    bad = (
        "stakeholder_name,security_class,quantity\n"
        "Aisha,Equity,1000\n"
        ",Equity,50\n"           # missing name
        "Rohan,Equity,-5\n"      # bad quantity
    )
    r = client.post(f"/entities/{eid}/cap-table/import", json={"csv": bad}, headers=h).json()
    assert not r["valid"] and len(r["errors"]) == 2
    assert r["errors"][0]["row"] == 2

    # apply with errors -> 400, nothing imported
    res = client.post(f"/entities/{eid}/cap-table/import", json={"csv": bad, "apply": True}, headers=h)
    assert res.status_code == 400
    assert client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"] == 0

    # missing required column
    r = client.post(
        f"/entities/{eid}/cap-table/import", json={"csv": "name,qty\nA,1\n"}, headers=h
    ).json()
    assert not r["valid"] and "Missing column" in r["errors"][0]["error"]


def test_import_template_download(client):
    h = auth_headers(client)
    eid = _company(client, h)
    r = client.get(f"/entities/{eid}/cap-table/import-template", headers=h)
    assert r.status_code == 200 and "stakeholder_name" in r.text


def test_document_pdf_download(client):
    h = auth_headers(client)
    eid = _company(client, h)
    doc = client.post(
        f"/entities/{eid}/documents",
        json={"template_key": "nda", "title": "NDA — Imp Pvt Ltd",
              "data": {"company": "Imp Pvt Ltd", "name": "Partner", "date": "2026-07-14"}},
        headers=h,
    ).json()
    r = client.get(f"/documents/{doc['id']}/pdf", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert 'filename="NDA - Imp Pvt Ltd.pdf"' in r.headers["content-disposition"]


def test_lp_downloads_own_statement_pdf(client):
    gp = auth_headers(client, email="gp@pdf.in")
    tid = client.post("/tenants", json={"name": "GP", "type": "fund"}, headers=gp).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": "Pdf Fund", "type": "fund"}, headers=gp
    ).json()["id"]
    fid = client.post(f"/entities/{eid}/fund", json={"sebi_category": "II"}, headers=gp).json()["id"]
    lp = client.post(
        f"/funds/{fid}/lps",
        json={"name": "Anita LP", "email": "anita@lp.in", "commitment": "10000000"},
        headers=gp,
    ).json()["id"]
    doc = client.post(f"/funds/{fid}/lps/{lp}/statement", headers=gp).json()

    anita = auth_headers(client, email="anita@lp.in")
    r = client.get(f"/portal/documents/{doc['id']}/pdf", headers=anita)
    assert r.status_code == 200 and r.content[:5] == b"%PDF-"
    # someone else's email cannot fetch it
    other = auth_headers(client, email="other@x.in")
    assert client.get(f"/portal/documents/{doc['id']}/pdf", headers=other).status_code == 404
