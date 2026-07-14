"""End-to-end founder journey: inception -> pre-seed (team, ESOP, family &
friends + angel SAFEs) -> seed (valuation, priced round, close). Walks the
stage guide exactly as the UI directs and asserts every hand-off is seamless:
checklists auto-complete, stages advance, SAFEs auto-convert at close, and
every participant (F&F investor, employee) sees the result in their portal."""
import datetime as dt

from tests.conftest import auth_headers


def _guide(client, h, eid):
    return client.get(f"/entities/{eid}/stage-guide", headers=h).json()


def test_founder_journey_inception_to_series(client):
    h = auth_headers(client, email="founder@zenith.in")

    # ============ INCEPTION — set the company up ============
    tid = client.post("/tenants", json={"name": "Zenith", "type": "company"}, headers=h).json()["id"]
    eid = client.post(
        f"/tenants/{tid}/entities",
        json={"name": "Zenith Labs Pvt Ltd", "type": "pvt_ltd", "incorporation_date": "2025-04-01"},
        headers=h,
    ).json()["id"]
    g = _guide(client, h, eid)
    assert g["stage"] == "inception" and g["progress"]["done"] == 1  # incorporation recorded

    equity = client.post(
        f"/entities/{eid}/security-classes", json={"name": "Equity", "kind": "equity"}, headers=h
    ).json()["id"]
    aisha = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Aisha", "type": "founder"}, headers=h
    ).json()["id"]
    rohan = client.post(
        f"/entities/{eid}/stakeholders", json={"name": "Rohan", "type": "founder"}, headers=h
    ).json()["id"]
    for sh, qty in ((aisha, 4_000_000), (rohan, 3_000_000)):
        client.post(
            f"/entities/{eid}/issuances",
            json={"security_class_id": equity, "stakeholder_id": sh, "quantity": qty,
                  "price_per_unit": "1", "issue_date": "2025-04-01"},
            headers=h,
        )
    client.post(
        f"/entities/{eid}/founder-vesting",
        json={"stakeholder_id": aisha, "security_class_id": equity, "total_shares": 4_000_000,
              "start_date": "2025-04-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/directors",
        json={"name": "Aisha", "din": "07654321", "designation": "managing_director",
              "appointed_on": "2025-04-01"},
        headers=h,
    )
    client.post(f"/entities/{eid}/compliance/generate",
                json={"financial_year_end": "2026-03-31"}, headers=h)
    client.post(
        f"/entities/{eid}/registrations",
        json={"kind": "gst", "state": "Karnataka", "number": "29ZENITH1234Z1"},
        headers=h,
    )
    g = _guide(client, h, eid)
    assert g["progress"]["done"] == g["progress"]["total"] == 6  # inception complete

    # ============ PRE-SEED — first money in ============
    g = client.put(f"/entities/{eid}/stage", json={"stage": "preseed"}, headers=h).json()
    assert "fundraising" in g["tabs"]  # SAFEs now reachable

    scheme = client.post(
        f"/entities/{eid}/esop/schemes", json={"name": "ESOP 2025", "pool_size": 1_000_000}, headers=h
    ).json()["id"]
    client.put(
        f"/entities/{eid}/startup/recognition",
        json={"status": "recognised", "dpiit_number": "DIPP777", "recognised_on": "2025-06-01"},
        headers=h,
    )
    member = client.post(
        f"/entities/{eid}/team",
        json={"name": "Meera", "email": "meera@zenith.in", "title": "Founding Engineer"},
        headers=h,
    ).json()["id"]
    client.post(f"/team/{member}/onboard", headers=h)
    # onboarding created an ESOP-eligible employee stakeholder — grant against the pool
    meera_sh = next(
        s for s in client.get(f"/entities/{eid}/stakeholders", headers=h).json()
        if s["name"] == "Meera"
    )["id"]
    grant_date = (dt.date.today() - dt.timedelta(days=400)).isoformat()  # past the 1y cliff
    client.post(
        f"/entities/{eid}/esop/grants",
        json={"scheme_id": scheme, "stakeholder_id": meera_sh, "quantity": 60_000,
              "exercise_price": "5", "grant_date": grant_date},
        headers=h,
    )
    # family & friends + angel cheques on SAFEs
    r = client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Ramesh Uncle", "investor_email": "ramesh@family.in",
              "investor_kind": "friend_family", "instrument_type": "safe",
              "principal": "500000", "discount_pct": "0.15", "issue_date": "2025-08-01"},
        headers=h,
    )
    assert r.status_code == 201
    client.post(
        f"/entities/{eid}/instruments",
        json={"investor_name": "Zed Angels", "investor_kind": "angel", "instrument_type": "safe",
              "principal": "2000000", "discount_pct": "0.20", "issue_date": "2025-09-01"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/investor-pipeline",
        json={"name": "Matrix Partners", "stage": "meeting", "check_size": "30000000"},
        headers=h,
    )
    client.post(
        f"/entities/{eid}/finance/snapshots",
        json={"period": "2026-06-01", "cash_balance": "2500000", "monthly_burn": "400000"},
        headers=h,
    )
    g = _guide(client, h, eid)
    assert g["progress"]["done"] == g["progress"]["total"] == 6  # pre-seed complete

    # ============ SEED — the priced round ============
    g = client.put(f"/entities/{eid}/stage", json={"stage": "seed"}, headers=h).json()
    client.post(
        f"/entities/{eid}/valuations",
        json={"method": "rule_11ua", "fmv_per_share": "40", "valuation_date": "2026-05-01"},
        headers=h,
    )
    ccps = client.post(
        f"/entities/{eid}/security-classes",
        json={"name": "Seed CCPS", "kind": "ccps", "pref_multiple": "1"},
        headers=h,
    ).json()["id"]
    rid = client.post(
        f"/entities/{eid}/rounds",
        json={"name": "Seed", "instrument": "ccps", "pre_money": "350000000",
              "target_amount": "35000000", "price_per_share": "50", "security_class_id": ccps},
        headers=h,
    ).json()["id"]
    client.post(f"/entities/{eid}/data-rooms", json={"name": "Seed diligence"}, headers=h)

    # ESOP granted at pre-seed already satisfies the seed checklist item
    g = _guide(client, h, eid)
    done = {c["key"] for c in g["checklist"] if c["done"]}
    assert {"valuation", "round_open", "dataroom", "esop_granted"} <= done
    assert "round_closed" not in done

    # CRM prospect -> commitment; plus a small F&F cheque in the round itself
    matrix = client.post(
        f"/entities/{eid}/investor-pipeline",
        json={"name": "Matrix Partners", "stage": "term_sheet", "check_size": "30000000",
              "round_id": rid},
        headers=h,
    ).json()["id"]
    cid = client.post(f"/pipeline/{matrix}/convert", headers=h).json()["commitment_id"]
    ff_cid = client.post(
        f"/rounds/{rid}/commitments",
        json={"investor_name": "Ramesh Uncle", "investor_kind": "friend_family", "amount": "250000"},
        headers=h,
    ).json()["id"]
    for c in (cid, ff_cid):
        client.post(f"/rounds/{rid}/commitments/{c}/status", json={"status": "funded"}, headers=h)

    # close: allotments + automatic SAFE conversion + PAS-3
    res = client.post(f"/rounds/{rid}/close", headers=h).json()
    assert res["issued"] == 2
    assert res["instruments_converted"] == 2  # both SAFEs converted automatically

    ct = client.get(f"/entities/{eid}/cap-table", headers=h).json()
    by_name = {}
    for r_ in ct["holders"]:
        by_name.setdefault(r_["stakeholder_name"], 0)
        by_name[r_["stakeholder_name"]] += r_["quantity"]
    assert by_name["Matrix Partners"] == 600_000            # 30,000,000 / 50
    assert by_name["Zed Angels"] == 50_000                  # 2,000,000 / (50 x 0.80)
    assert by_name["Ramesh Uncle"] == 11_764 + 5_000        # SAFE @42.50 + round cheque

    # PAS-3 filing obligation was created
    obs = client.get(f"/entities/{eid}/compliance", headers=h).json()
    assert any(o["form_code"] == "PAS-3" for o in obs)

    # seed checklist complete; the data now suggests Series rounds
    g = _guide(client, h, eid)
    assert g["progress"]["done"] == g["progress"]["total"] == 5
    assert g["suggested_stage"] == "series"

    # ============ every participant sees their side ============
    # the F&F investor: converted SAFE + shares, no explicit grant needed
    ramesh = auth_headers(client, email="ramesh@family.in")
    portal = client.get("/portal", headers=ramesh).json()
    inst = portal["companies"][0]["instruments"][0]
    assert inst["status"] == "converted" and inst["converted_shares"] == 11_764

    # the employee: vested options priced off the valuation
    meera = auth_headers(client, email="meera@zenith.in")
    portal = client.get("/portal", headers=meera).json()
    eg = portal["equity_grants"][0]
    assert eg["granted"] == 60_000 and eg["vested"] > 0
    assert eg["current_fmv"] == "40.0000"
