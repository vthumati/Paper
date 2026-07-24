from tests.conftest import auth_headers


def _company(client, h):
    tid = client.post("/tenants", json={"name": "S", "type": "company"}, headers=h).json()["id"]
    return client.post(
        f"/tenants/{tid}/entities", json={"name": "S Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]


def test_sh7_increase_authorised_capital(client):
    h = auth_headers(client)
    eid = _company(client, h)
    d = client.post(
        f"/entities/{eid}/mca/sh7", json={"new_authorised_capital": "1000000"}, headers=h
    ).json()
    assert "FORM SH-7" in d["content"]
    assert "1000000.00" in d["content"] and "Increase:" in d["content"]
    # SH-7 obligation is now on the calendar
    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "SH-7" for o in obs)
    # authorised capital was raised → a lower new value is rejected
    assert client.post(
        f"/entities/{eid}/mca/sh7", json={"new_authorised_capital": "500000"}, headers=h
    ).status_code == 400
    # a higher one is accepted
    assert client.post(
        f"/entities/{eid}/mca/sh7", json={"new_authorised_capital": "2500000"}, headers=h
    ).status_code == 201


def test_pas3_prefilled_from_ledger(client):
    h = auth_headers(client)
    eid = _company(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    sh = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Ravi", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(f"/entities/{eid}/issuances", json={"security_class_id": sc,
        "stakeholder_id": sh, "quantity": 100000, "price_per_unit": "10",
        "issue_date": "2025-02-01"}, headers=h)
    d = client.post(f"/entities/{eid}/mca/pas3", headers=h).json()
    assert "FORM PAS-3" in d["content"]
    assert "Ravi" in d["content"] and "100,000" in d["content"]
    assert "1000000.00" in d["content"]  # 100,000 × 10 consideration


def test_fc_gpr_and_fema_tracker(client):
    h = auth_headers(client)
    eid = _company(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    nri = client.post(
        f"/entities/{eid}/stakeholders",
        json={"name": "Overseas VC", "type": "investor", "residency": "non_resident",
              "country": "Singapore"},
        headers=h,
    ).json()
    assert nri["residency"] == "non_resident" and nri["country"] == "Singapore"
    client.post(f"/entities/{eid}/issuances", json={"security_class_id": sc,
        "stakeholder_id": nri["id"], "quantity": 50000, "price_per_unit": "20",
        "issue_date": "2025-03-01"}, headers=h)
    d = client.post(f"/entities/{eid}/mca/fc-gpr", headers=h).json()
    assert "FORM FC-GPR" in d["content"] and "SINGLE MASTER FORM" in d["content"]
    assert "Overseas VC" in d["content"] and "Singapore" in d["content"]
    assert "50,000" in d["content"]
    # the FEMA tracker surfaces the non-resident holder + the SMF checklist
    t = client.get(f"/entities/{eid}/fema/tracker", headers=h).json()
    assert len(t["non_resident_holders"]) == 1
    assert t["non_resident_holders"][0]["name"] == "Overseas VC"
    assert len(t["smf_checklist"]) >= 5


def test_mgt14_and_obligation_prefill(client):
    h = auth_headers(client)
    eid = _company(client, h)
    res = client.post(f"/entities/{eid}/resolutions", json={
        "type": "special", "title": "Adopt new AoA", "text": "RESOLVED THAT the Articles be amended."
    }, headers=h).json()["id"]
    # direct MGT-14 pre-fill from the resolution
    d = client.post(f"/resolutions/{res}/mca/mgt14", headers=h).json()
    assert "FORM MGT-14" in d["content"] and "Adopt new AoA" in d["content"]
    assert "the Articles be amended" in d["content"]
    # passing a special resolution auto-creates the MGT-14 obligation
    client.post(f"/resolutions/{res}/status", json={"status": "passed"}, headers=h)
    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    mgt = next(o for o in obs if o["form_code"] == "MGT-14")
    assert mgt["document_id"] is None
    # pre-fill via the obligation links the generated form to it
    client.post(f"/compliance/{mgt['id']}/prefill", json={"resolution_id": res}, headers=h)
    obs2 = client.get(f"/entities/{eid}/compliance", headers=h).json()
    mgt2 = next(o for o in obs2 if o["form_code"] == "MGT-14")
    assert mgt2["document_id"] is not None


def test_meeting_attendees_and_resolution_votes(client):
    h = auth_headers(client)
    eid = _company(client, h)
    mid = client.post(f"/entities/{eid}/meetings", json={
        "type": "board", "title": "Q1 Board Meeting", "date": "2026-04-10", "quorum": 2
    }, headers=h).json()["id"]
    for name, present in [("Asha", True), ("Ravi", True), ("Meera", False)]:
        client.post(f"/meetings/{mid}/attendees",
                    json={"name": name, "role": "director", "present": present}, headers=h)
    att = client.get(f"/meetings/{mid}/attendees", headers=h).json()
    assert att["present"] == 2 and att["quorum_met"] is True

    res = client.post(f"/entities/{eid}/resolutions", json={
        "meeting_id": mid, "type": "board", "title": "Approve budget", "text": "RESOLVED to approve the FY budget."
    }, headers=h).json()["id"]
    for voter, vote in [("Asha", "for"), ("Ravi", "for"), ("Meera", "against")]:
        client.post(f"/resolutions/{res}/votes", json={"voter": voter, "vote": vote}, headers=h)
    tally = client.get(f"/resolutions/{res}/votes", headers=h).json()["tally"]
    assert tally["for"] == 2 and tally["against"] == 1 and tally["total"] == 3
    # the generated resolution PDF folds in attendees + the vote result
    doc = client.post(f"/resolutions/{res}/document", headers=h).json()
    assert "Present: Asha, Ravi (2 present)" in doc["content"]
    assert "Result: For 2, Against 1, Abstain 0" in doc["content"]
