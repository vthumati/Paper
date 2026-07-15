"""Savvi/PaperOS-parity features: diligence readiness engine (FR-I-5),
public fundraising funnel (FR-E-8), financing doc automation (subscription
agreements + PAS-4), and the small fills (founder IP at incorporation,
charter amendments, offboarding option lapse)."""
import datetime as dt

from tests.conftest import auth_headers


def _company(client, h, name="Savvi Test"):
    tid = client.post("/tenants", json={"name": name, "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities", json={"name": f"{name} Pvt Ltd", "type": "pvt_ltd"}, headers=h
    ).json()["id"]
    return tid, eid


# ---------- gap 1: diligence readiness engine ----------

def test_diligence_findings_and_score(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    sc = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    founder = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Asha F", "type": "founder"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/issuances",
        json={"security_class_id": sc, "stakeholder_id": founder, "quantity": 100000,
              "price_per_unit": "10", "issue_date": "2025-01-01"},
        headers=h,
    )
    # ESOP grant with no valuation on record
    client.post(f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 10000}, headers=h)
    scheme = client.get(f"/entities/{eid}/esop/schemes", headers=h).json()[0]["id"]
    emp = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Emp", "type": "employee"}, headers=h
    ).json()["id"]
    client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": emp, "quantity": 1000,
              "exercise_price": "10", "grant_date": "2025-01-01"},
        headers=h,
    )

    d = client.get(f"/entities/{eid}/diligence", headers=h).json()
    codes = {f["code"] for f in d["findings"]}
    # founder without IP assignment + vesting, grants w/o valuation,
    # issuances w/o resolution, no directors, stakeholders w/o email
    assert {"founder_ip", "founder_vesting", "esop_no_valuation",
            "issuances_no_resolution", "directors_register",
            "stakeholder_emails"} <= codes
    assert d["score"] < 50
    # high severity sorts first
    assert d["findings"][0]["severity"] == "high"

    # fixing items moves the score: pass a resolution + add a valuation
    client.post(
        f"/entities/{eid}/resolutions",
        json={"type": "board", "title": "Allotment", "text": "Approve allotment"},
        headers=h,
    )
    res = client.get(f"/entities/{eid}/resolutions", headers=h).json()[0]["id"]
    client.post(f"/resolutions/{res}/status", json={"status": "passed"}, headers=h)
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "rule_11ua", "fmv_per_share": "25",
              "valuation_date": "2026-01-01", "status": "final"},
        headers=h,
    )
    d2 = client.get(f"/entities/{eid}/diligence", headers=h).json()
    codes2 = {f["code"] for f in d2["findings"]}
    assert "issuances_no_resolution" not in codes2
    assert "esop_no_valuation" not in codes2
    assert d2["score"] > d["score"]


def test_diligence_report_document(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    r = client.post(f"/entities/{eid}/diligence/report", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["template_key"] == "diligence_report"
    assert "Readiness score" in body["content"]


# ---------- gap 2: public fundraising funnel ----------

def _round_with_link(client, h, eid, with_room=True):
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Seed", "instrument": "ccps", "pre_money": "40000000",
              "target_amount": "10000000", "price_per_share": "40"},
        headers=h,
    ).json()["id"]
    room = None
    if with_room:
        room = client.post(f"/entities/{eid}/data-rooms", json={"name": "Pitch"}, headers=h).json()["id"]
    link = client.post(
        f"/entities/{eid}/rounds/{rid}/funnel-link",
        json={"data_room_id": room}, headers=h,
    ).json()
    return rid, room, link


def test_funnel_public_optin(client):
    h = auth_headers(client, email="founder@savvi.in")
    _, eid = _company(client, h)
    rid, room, link = _round_with_link(client, h, eid)
    token = link["token"]

    # public info needs no auth
    info = client.get(f"/public/funnel/{token}")
    assert info.status_code == 200
    assert info.json()["round"] == "Seed" and info.json()["has_data_room"] is True

    # opt in (still no auth) -> prospect + data-room grant
    r = client.post(
        f"/public/funnel/{token}/interest",
        json={"name": "Priya Angel", "email": "priya@angels.in", "firm": "Solo",
              "check_size": "2500000"},
    )
    assert r.status_code == 201 and r.json()["data_room_granted"] is True

    funnel = client.get(f"/entities/{eid}/rounds/{rid}/funnel", headers=h).json()
    assert len(funnel["prospects"]) == 1
    p = funnel["prospects"][0]
    assert p["email"] == "priya@angels.in" and p["stage"] == "contacted"
    grants = client.get(f"/data-rooms/{room}", headers=h).json()["grants"]
    assert any(g["email"] == "priya@angels.in" for g in grants)

    # resubmitting updates, not duplicates
    client.post(
        f"/public/funnel/{token}/interest",
        json={"name": "Priya Angel", "email": "priya@angels.in", "check_size": "5000000"},
    )
    funnel = client.get(f"/entities/{eid}/rounds/{rid}/funnel", headers=h).json()
    assert len(funnel["prospects"]) == 1
    assert funnel["prospects"][0]["check_size"] == "5000000.00"

    # commitment linkage by email shows in the funnel
    client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Priya Angel", "investor_email": "priya@angels.in",
              "amount": "5000000"},
        headers=h,
    )
    funnel = client.get(f"/entities/{eid}/rounds/{rid}/funnel", headers=h).json()
    assert funnel["prospects"][0]["commitment"]["amount"] == "5000000.00"

    # deactivating kills the public link
    client.post(f"/entities/{eid}/rounds/{rid}/funnel-link/deactivate", headers=h)
    assert client.get(f"/public/funnel/{token}").status_code == 404
    assert client.post(
        f"/public/funnel/{token}/interest",
        json={"name": "X", "email": "x@y.in"},
    ).status_code == 404


def test_funnel_rate_limit(client, monkeypatch):
    from app import ratelimit

    monkeypatch.setattr(ratelimit.funnel_limiter, "max_failures", 3)
    h = auth_headers(client)
    _, eid = _company(client, h)
    _, _, link = _round_with_link(client, h, eid, with_room=False)
    for i in range(3):
        client.post(
            f"/public/funnel/{link['token']}/interest",
            json={"name": f"P{i}", "email": f"p{i}@x.in"},
        )
    r = client.post(
        f"/public/funnel/{link['token']}/interest",
        json={"name": "P9", "email": "p9@x.in"},
    )
    assert r.status_code == 429


# ---------- gap 3: financing document automation ----------

def test_spv_commit_generates_subscription_agreement(client):
    lead = auth_headers(client, email="lead2@syndicate.in")
    tid = client.post("/tenants", json={"name": "Syn", "type": "fund"}, headers=lead).json()["id"]
    spv_entity = client.post(
        f"/tenants/{tid}/entities", json={"name": "Deal SPV II", "type": "spv"}, headers=lead
    ).json()["id"]
    sid = client.post(
        f"/entities/{spv_entity}/spv",
        json={"sponsor": "Lead GP", "target_company": "Rocket Pvt Ltd"},
        headers=lead,
    ).json()["id"]
    client.post(f"/spvs/{sid}/terms", json={"carry_pct": "0.2", "min_ticket": "100000"}, headers=lead)
    ci = client.post(
        f"/spvs/{sid}/co-investors",
        json={"name": "Backer B", "email": "backer2@angels.in"},
        headers=lead,
    ).json()

    backer = auth_headers(client, email="backer2@angels.in")
    client.post(
        "/portal/spv-commitments",
        json={"co_investor_id": ci["id"], "amount": "500000"},
        headers=backer,
    )

    # the agreement exists on the SPV entity and shows in the backer's portal
    docs = client.get(f"/entities/{spv_entity}/documents", headers=lead).json()
    sub = [d for d in docs if d["template_key"] == "subscription_agreement"]
    assert len(sub) == 1
    p = client.get("/portal", headers=backer).json()
    deal_docs = p["spvs"][0]["documents"]
    assert len(deal_docs) == 1 and "Subscription Agreement" in deal_docs[0]["title"]
    # the backer can download their own agreement as PDF; a stranger cannot
    pdf = client.get(f"/portal/documents/{deal_docs[0]['id']}/pdf", headers=backer)
    assert pdf.status_code == 200 and pdf.headers["content-type"].startswith("application/pdf")
    stranger = auth_headers(client, email="nosy@evil.in")
    assert client.get(f"/portal/documents/{deal_docs[0]['id']}/pdf", headers=stranger).status_code == 404

    # a revised commitment re-versions the same document, not a duplicate
    client.post(
        "/portal/spv-commitments",
        json={"co_investor_id": ci["id"], "amount": "750000"},
        headers=backer,
    )
    docs = client.get(f"/entities/{spv_entity}/documents", headers=lead).json()
    sub = [d for d in docs if d["template_key"] == "subscription_agreement"]
    assert len(sub) == 1 and sub[0]["current_version"] == 2

    # direct lead-side add with a commitment also generates one
    client.post(
        f"/spvs/{sid}/co-investors", json={"name": "Direct D", "commitment": "300000"}, headers=lead
    )
    docs = client.get(f"/entities/{spv_entity}/documents", headers=lead).json()
    assert len([d for d in docs if d["template_key"] == "subscription_agreement"]) == 2


def test_round_pas4_offer_letter(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Seed", "instrument": "ccps", "pre_money": "40000000",
              "target_amount": "10000000", "price_per_share": "40"},
        headers=h,
    ).json()["id"]
    cid = client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Blume", "amount": "4000000"},
        headers=h,
    ).json()["id"]
    r = client.post(f"/rounds/{rid}/commitments/{cid}/offer-letter", headers=h)
    assert r.status_code == 201
    body = r.json()
    assert body["template_key"] == "pas4_offer_letter"
    assert "PAS-4" in body["content"] and "Blume" in body["content"]
    assert "100000 securities" in body["content"]  # 4,000,000 / 40

    # commitment must belong to the round
    rid2 = client.post(
        f"/entities/{eid}/rounds", json={"name": "Bridge"}, headers=h
    ).json()["id"]
    assert client.post(f"/rounds/{rid2}/commitments/{cid}/offer-letter", headers=h).status_code == 404


# ---------- gap 6: small fills ----------

def test_incorporation_generates_founder_ip_assignments(client):
    h = auth_headers(client)
    tid = client.post("/tenants", json={"name": "NewCo Org", "type": "company"}, headers=h).json()["id"]
    inc = client.post(
        f"/tenants/{tid}/incorporations",
        json={"name_options": ["Zeta Labs Pvt Ltd"], "entity_type": "pvt_ltd",
              "state": "Karnataka", "registered_office": "Bengaluru",
              "authorised_capital": "1000000", "paid_up_capital": "100000", "par_value": "10",
              "founders": [
                  {"name": "A", "email": "a@zeta.in", "shares": 5000, "is_director": True},
                  {"name": "B", "email": "b@zeta.in", "shares": 5000, "is_director": True},
              ]},
        headers=h,
    ).json()
    prepared = client.post(f"/tenants/{tid}/incorporations/{inc['id']}/prepare", headers=h).json()
    docs = client.get(f"/entities/{prepared['entity_id']}/documents", headers=h).json()
    ip_docs = [d for d in docs if d["template_key"] == "ip_assignment"]
    assert len(ip_docs) == 2
    assert all(d["subject_type"] == "stakeholder" for d in ip_docs)
    # and the diligence engine is satisfied on founder IP
    d = client.get(f"/entities/{prepared['entity_id']}/diligence", headers=h).json()
    assert "founder_ip" not in {f["code"] for f in d["findings"]}


def test_charter_amendment_resolution_and_mgt14(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    r = client.post(
        f"/entities/{eid}/charter-amendments",
        json={"kind": "aoa", "description": "Insert ESOP enabling clause in the Articles"},
        headers=h,
    )
    assert r.status_code == 201
    out = r.json()
    assert out["status"] == "draft"
    res = client.get(f"/entities/{eid}/resolutions", headers=h).json()[0]
    assert res["type"] == "special" and "Charter amendment (AOA)" in res["title"]
    doc = client.get(f"/documents/{out['document_id']}", headers=h).json()
    assert "CHARTER AMENDMENT — AOA" in doc["content"]

    # passing the special resolution files MGT-14 into compliance
    client.post(f"/resolutions/{out['resolution_id']}/status", json={"status": "passed"}, headers=h)
    obligations = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "MGT-14" for o in obligations)


def test_offboard_lapses_unvested_options(client):
    h = auth_headers(client)
    _, eid = _company(client, h)
    mid = client.post(
        f"/entities/{eid}/team", json={"name": "Leaver", "email": "leaver@x.in"}, headers=h
    ).json()["id"]
    client.post(f"/team/{mid}/onboard", headers=h)
    client.post(f"/entities/{eid}/esop/schemes", json={"name": "ESOP", "pool_size": 10000}, headers=h)
    scheme = client.get(f"/entities/{eid}/esop/schemes", headers=h).json()[0]["id"]
    sh = client.get(f"/entities/{eid}/team", headers=h).json()[0]["stakeholder_id"]
    grant_date = "2024-01-01"
    gid = client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": sh, "quantity": 4800,
              "exercise_price": "10", "grant_date": grant_date,
              "cliff_months": 12, "total_months": 48},
        headers=h,
    ).json()["id"]

    # leaves exactly 24 months in -> 2400 vested, 2400 lapse back to the pool
    r = client.post(f"/team/{mid}/offboard", json={"left_on": "2026-01-01"}, headers=h)
    assert r.status_code == 200
    assert r.json() == {"member_id": mid, "lapsed_options": 2400, "grants_affected": 1}
    member = client.get(f"/entities/{eid}/team", headers=h).json()[0]
    assert member["status"] == "exited" and member["left_on"] == "2026-01-01"
    grants = client.get(f"/entities/{eid}/esop/grants", headers=h).json()
    assert grants[0]["quantity"] == 2400
    # the freed pool can be granted again (2400 + 7600 <= 10000)
    r2 = client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": sh, "quantity": 7600,
              "exercise_price": "10", "grant_date": "2026-07-01"},
        headers=h,
    )
    assert r2.status_code == 201
