from tests.conftest import auth_headers

INTAKE = {
    "name_options": ["Zephyr Labs Pvt Ltd", "Zephyr Technologies Pvt Ltd"],
    "state": "Karnataka",
    "registered_office": "1 MG Road, Bengaluru 560001",
    "authorised_capital": "1000000",
    "paid_up_capital": "100000",
    "par_value": "10",
    "founders": [
        {"name": "Aisha", "email": "aisha@zephyr.in", "din": "01234567", "shares": 6000},
        {"name": "Rohan", "shares": 4000},
    ],
}


def _tenant(client, h):
    return client.post("/tenants", json={"name": "Zephyr", "type": "company"}, headers=h).json()["id"]


def test_incorporation_wizard_end_to_end(client):
    h = auth_headers(client)
    tid = _tenant(client, h)

    # intake
    inc = client.post(f"/tenants/{tid}/incorporations", json=INTAKE, headers=h)
    assert inc.status_code == 201
    iid = inc.json()["id"]
    assert inc.json()["status"] == "draft"

    # filing pack: pre-registration entity + SPICe+/eMoA/eAoA
    r = client.post(f"/tenants/{tid}/incorporations/{iid}/prepare", headers=h).json()
    assert r["status"] == "docs_generated" and r["company_name"] == "Zephyr Labs Pvt Ltd"
    eid = r["entity_id"]
    entity = client.get(f"/entities/{eid}", headers=h).json()
    assert entity["cin"] is None and entity["incorporation_date"] is None
    docs = client.get(f"/entities/{eid}/documents", headers=h).json()
    titles = {d["title"] for d in docs}
    assert any("SPICe+" in t for t in titles) and any("eMoA" in t for t in titles)
    # no shares allotted yet
    assert client.get(f"/entities/{eid}/cap-table", headers=h).json()["total_shares"] == 0

    # SRN then CIN
    r = client.post(f"/tenants/{tid}/incorporations/{iid}/filed", json={"srn": "T998877"}, headers=h).json()
    assert r["status"] == "filed" and r["srn"] == "T998877"
    result = client.post(
        f"/tenants/{tid}/incorporations/{iid}/registered",
        json={"cin": "U72900KA2026PTC123456", "pan": "AAACZ9999Z", "incorporation_date": "2026-07-01"},
        headers=h,
    ).json()
    assert result["shares_issued"] == 10000
    assert result["directors_registered"] == 2
    assert result["obligations_created"] > 0

    # the company is live: CIN set, founders hold subscription shares at par
    entity = client.get(f"/entities/{eid}", headers=h).json()
    assert entity["cin"] == "U72900KA2026PTC123456" and entity["incorporation_date"] == "2026-07-01"
    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    assert ct["total_shares"] == 10000 and ct["total_invested"] == "100000.00"
    directors = client.get(f"/entities/{eid}/directors", headers=h).json()
    assert len(directors) == 2
    # stage guide reflects the setup the wizard did
    g = client.get(f"/entities/{eid}/stage-guide", headers=h).json()
    done = {c["key"] for c in g["checklist"] if c["done"]}
    assert {"incorporated", "founder_shares", "directors", "compliance_calendar"} <= done

    # registering twice is guarded
    again = client.post(
        f"/tenants/{tid}/incorporations/{iid}/registered",
        json={"cin": "X", "incorporation_date": "2026-07-01"},
        headers=h,
    )
    assert again.status_code == 409


def test_incorporation_intake_validation(client):
    h = auth_headers(client)
    tid = _tenant(client, h)
    # one director is not enough for a pvt ltd
    bad = {**INTAKE, "founders": [
        {"name": "Solo", "shares": 10000},
        {"name": "Investor", "shares": 1, "is_director": False},
    ]}
    r = client.post(f"/tenants/{tid}/incorporations", json=bad, headers=h)
    assert r.status_code == 400 and "at least 2 directors" in r.json()["detail"]
    # paid-up above authorised
    bad = {**INTAKE, "paid_up_capital": "99999999"}
    assert client.post(f"/tenants/{tid}/incorporations", json=bad, headers=h).status_code == 400
    # subscription above authorised capital
    bad = {**INTAKE, "founders": [
        {"name": "A", "shares": 900000}, {"name": "B", "shares": 900000},
    ]}
    assert client.post(f"/tenants/{tid}/incorporations", json=bad, headers=h).status_code == 400
    # registering before the pack exists
    iid = client.post(f"/tenants/{tid}/incorporations", json=INTAKE, headers=h).json()["id"]
    r = client.post(
        f"/tenants/{tid}/incorporations/{iid}/registered",
        json={"cin": "X", "incorporation_date": "2026-07-01"},
        headers=h,
    )
    assert r.status_code == 400


def test_new_provider_categories(client):
    h = auth_headers(client)
    p = client.post(
        "/service-providers",
        json={"name": "WeOffice Bengaluru", "category": "registered_office"},
        headers=h,
    )
    assert p.status_code == 201
    p = client.post(
        "/service-providers", json={"name": "FinLedger vCFO", "category": "virtual_cfo"}, headers=h
    )
    assert p.status_code == 201
    listed = client.get("/service-providers?category=virtual_cfo", headers=h).json()
    assert len(listed) == 1 and listed[0]["name"] == "FinLedger vCFO"
