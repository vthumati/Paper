"""Seed a realistic demo workspace into the dev database.

Creates a demo user who owns a startup (cap table, founders' vesting, ESOP,
SAFE, a closed seed round with a foreign investor, CRM pipeline, governance,
compliance calendars, contracts, data room, finance snapshots, registers,
DPIIT) and a fund (LPs, capital call, distribution, portfolio) — everything
exercised through the real API.

Usage (from apps/api):
    .venv\\Scripts\\python scripts/seed_demo.py --fresh

--fresh deletes paper_dev.db first. Prints demo credentials and a summary.
"""
import argparse
import datetime as dt
import os
import pathlib
import sys

API_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

EMAIL = "demo@acme.in"
PASSWORD = "demo-pass-123"


def month_start(d: dt.date, months_back: int) -> str:
    y, m = d.year, d.month - months_back
    while m < 1:
        m += 12
        y -= 1
    return dt.date(y, m, 1).isoformat()


def seed(client) -> None:
    from app.clock import today_ist

    today = today_ist()

    def call(method: str, path: str, token: str | None = None, payload: dict | None = None):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        r = client.request(method, path, json=payload, headers=headers)
        assert r.status_code < 400, f"{method} {path} -> {r.status_code}: {r.text}"
        return r.json() if r.content else None

    # --- user ---
    client.post("/auth/signup", json={"email": EMAIL, "full_name": "Demo Founder", "password": PASSWORD})
    token = call("POST", "/auth/login", payload={"email": EMAIL, "password": PASSWORD})["access_token"]

    def post(path, **payload):
        return call("POST", path, token, payload)

    def put(path, **payload):
        return call("PUT", path, token, payload)

    def get(path):
        return call("GET", path, token)

    # --- startup: tenant, entity, cap table ---
    tid = post("/tenants", name="Acme Ventures", type="company")["id"]
    eid = post(f"/tenants/{tid}/entities", name="Acme Labs Pvt Ltd", type="pvt_ltd",
               incorporation_date="2024-05-01")["id"]
    equity = post(f"/entities/{eid}/security-classes", name="Equity", kind="equity", par_value="1")["id"]
    ccps = post(f"/entities/{eid}/security-classes", name="Seed CCPS", kind="ccps",
                pref_multiple="1", seniority=1)["id"]
    aditi = post(f"/entities/{eid}/stakeholders", name="Aditi Sharma", type="founder")["id"]
    rohan = post(f"/entities/{eid}/stakeholders", name="Rohan Mehta", type="founder")["id"]
    asha = post(f"/entities/{eid}/stakeholders", name="Asha Rao", type="employee", email="asha@acme.in")["id"]
    for sh, qty in ((aditi, 4_000_000), (rohan, 3_000_000)):
        post(f"/entities/{eid}/issuances", security_class_id=equity, stakeholder_id=sh,
             quantity=qty, price_per_unit="1", issue_date="2024-05-01")
    post(f"/entities/{eid}/founder-vesting", stakeholder_id=aditi, security_class_id=equity,
         total_shares=4_000_000, cliff_months=12, total_months=48, start_date="2024-05-01")

    # --- governance: directors, meeting with agenda + notice, special resolution ---
    post(f"/entities/{eid}/directors", name="Aditi Sharma", din="01234567",
         designation="managing_director", appointed_on="2024-05-01")
    post(f"/entities/{eid}/directors", name="Rohan Mehta", designation="director",
         appointed_on="2024-05-01")
    mid = post(f"/entities/{eid}/meetings", type="board", title="Q1 FY27 Board Meeting",
               date=(today + dt.timedelta(days=7)).isoformat(), quorum=2, location="Bengaluru HQ")["id"]
    post(f"/meetings/{mid}/agenda", title="Adopt audited financials", order_index=1)
    post(f"/meetings/{mid}/agenda", title="Approve ESOP pool top-up", order_index=2)
    post(f"/meetings/{mid}/notice")
    rid = post(f"/entities/{eid}/resolutions", type="special", title="Adopt amended AoA",
               text="RESOLVED THAT the amended Articles of Association be and are hereby adopted.")["id"]
    post(f"/resolutions/{rid}/status", status="passed")

    # --- ESOP + valuations ---
    scheme = post(f"/entities/{eid}/esop/schemes", name="ESOP 2024", pool_size=1_000_000)["id"]
    post(f"/entities/{eid}/esop/grants", scheme_id=scheme, stakeholder_id=asha, quantity=48_000,
         exercise_price="10", grant_date="2024-06-01")
    post(f"/entities/{eid}/valuations", method="rule_11ua", fmv_per_share="100",
         valuation_date=(today - dt.timedelta(days=120)).isoformat(), valuer_name="XYZ Merchant Bankers")
    post(f"/entities/{eid}/valuations", method="fair_value", fmv_per_share="120",
         valuation_date=(today - dt.timedelta(days=30)).isoformat())

    # --- SAFEs (angel + family-and-friends) + seed round (one foreign investor -> FC-GPR) + CRM ---
    post(f"/entities/{eid}/instruments", investor_name="Bala Angel LLP", instrument_type="safe",
         investor_kind="angel", principal="2500000", discount_pct="0.20", issue_date="2024-08-01")
    post(f"/entities/{eid}/instruments", investor_name="Sunita Sharma", instrument_type="safe",
         investor_kind="friend_family", investor_email=EMAIL, principal="500000",
         discount_pct="0.15", issue_date="2024-07-01")
    round_id = post(f"/entities/{eid}/rounds", name="Seed", instrument="ccps", pre_money="300000000",
                    target_amount="60000000", price_per_share="100", security_class_id=ccps)["id"]
    post(f"/rounds/{round_id}/term-sheet")
    for name, amount, foreign in (("Blume Ventures", "40000000", False), ("Lightspeed India", "20000000", True)):
        cid = post(f"/rounds/{round_id}/commitments", investor_name=name, amount=amount, is_foreign=foreign)["id"]
        post(f"/rounds/{round_id}/commitments/{cid}/status", status="funded")
    post(f"/rounds/{round_id}/close")
    post(f"/entities/{eid}/investor-pipeline", name="Peak XV", firm="Peak XV Partners",
         stage="term_sheet", check_size="100000000")
    post(f"/entities/{eid}/investor-pipeline", name="Accel", stage="contacted", check_size="50000000")
    put(f"/entities/{eid}/stage", stage="series")  # seed round closed -> series stage

    # --- compliance (annual + GST/TDS), mark one filed ---
    fy_end = dt.date(today.year, 3, 31) if today.month > 3 else dt.date(today.year - 1, 3, 31)
    obligations = post(f"/entities/{eid}/compliance/generate", financial_year_end=fy_end.isoformat())
    post(f"/entities/{eid}/compliance/generate-periodic", financial_year_end=fy_end.isoformat())
    post(f"/compliance/{obligations[0]['id']}/status", status="filed", srn="T00123456")

    # --- team, contracts ---
    member = post(f"/entities/{eid}/team", name="Vikram Iyer", title="Founding Engineer",
                  employment_type="employee")["id"]
    post(f"/team/{member}/onboard")
    cp = post(f"/entities/{eid}/counterparties", name="BigCo Retail", kind="customer")["id"]
    contract = post(f"/entities/{eid}/contracts", counterparty_id=cp, title="Enterprise MSA",
                    type="msa", value="12000000", renewal_date=(today + dt.timedelta(days=21)).isoformat())["id"]
    post(f"/contracts/{contract}/status", status="active")
    msa_doc = post(f"/contracts/{contract}/document", template_key="msa")["id"]

    # --- data room with docs, access, Q&A ---
    room = post(f"/entities/{eid}/data-rooms", name="Series A diligence")["id"]
    sha_doc = post(f"/entities/{eid}/documents", template_key="sha", title="Seed SHA",
                   data={"company": "Acme Labs Pvt Ltd", "investor": "Blume Ventures"})["id"]
    for doc in (sha_doc, msa_doc):
        post(f"/data-rooms/{room}/items", document_id=doc)
    post(f"/data-rooms/{room}/grants", email="investor@peakxv.in")
    post(f"/data-rooms/{room}/questions", question="What is the current monthly burn and runway?")

    # --- finance, registers, DPIIT ---
    for back, cash in ((2, "60000000"), (1, "56000000"), (0, "52000000")):
        post(f"/entities/{eid}/finance/snapshots", period=month_start(today, back),
             cash_balance=cash, monthly_burn="4000000", revenue="1500000")
    post(f"/entities/{eid}/registrations", kind="gst", state="Karnataka", number="29ABCDE1234F1Z5")
    post(f"/entities/{eid}/sbo", name="Aditi Sharma", pan="ABCDE1234F", percentage="40")
    post(f"/entities/{eid}/charges", holder="HDFC Bank", amount="5000000",
         charge_type="hypothecation", created_on="2025-01-15")
    put(f"/entities/{eid}/startup/recognition", status="recognised", dpiit_number="DIPP123456",
        recognised_on="2025-01-01")
    benefit = post(f"/entities/{eid}/startup/benefits", type="section_80iac")["id"]
    post(f"/startup-benefits/{benefit}/status", status="approved", reference="CBDT/80IAC/777")

    # --- investor portal: link demo user to the Blume holding + publish an update ---
    blume = next(s for s in get(f"/entities/{eid}/stakeholders") if s["name"] == "Blume Ventures")
    post(f"/entities/{eid}/investor-access", email=EMAIL, stakeholder_id=blume["id"])
    post(f"/entities/{eid}/investor-updates", title="Q1 FY27 update",
         body="ARR crossed Rs 1.8 Cr; seed round closed; hiring 6 engineers.")
    post(f"/resolutions/{rid}/consents")  # reserved-matter consent -> investor portal

    # --- fund side: demo user is also an LP ---
    ftid = post("/tenants", name="Nimbus Capital", type="fund")["id"]
    feid = post(f"/tenants/{ftid}/entities", name="Nimbus Ventures Fund I", type="fund")["id"]
    fund = post(f"/entities/{feid}/fund", sebi_category="II", carry_pct="0.20")["id"]
    demo_lp = post(f"/funds/{fund}/lps", name="Demo Founder", email=EMAIL, commitment="20000000")["id"]
    post(f"/funds/{fund}/lps", name="Family Office X", commitment="30000000")
    for notice in post(f"/funds/{fund}/capital-calls", pct="0.25", purpose="First close deployments")["notices"]:
        post(f"/funds/{fund}/drawdown-notices/{notice['id']}/pay")
    post(f"/funds/{fund}/distributions", gross_amount="3000000", kind="profit")
    inv = post(f"/funds/{fund}/portfolio", company_name="Acme Labs Pvt Ltd", amount="40000000", ownership_pct="11.4")
    put(f"/funds/{fund}/portfolio/{inv['id']}/mark", current_value="60000000")  # marked up post-round
    post(f"/funds/{fund}/lps/{demo_lp}/statement")  # capital-account statement -> LP portal
    # 64C/64D for the FY containing today's distribution
    post(f"/funds/{fund}/tax-statements",
         financial_year_end=dt.date(fy_end.year + 1, 3, 31).isoformat())
    post(f"/funds/{fund}/deals", company_name="RocketCo", sector="SaaS", stage="diligence",
         amount="25000000", notes="Warm intro via Acme founders")
    post(f"/funds/{fund}/deals", company_name="GreenGrid", sector="Climate", stage="sourced",
         amount="15000000")
    post(f"/entities/{feid}/compliance/generate-aif", financial_year_end=fy_end.isoformat())

    # --- sweep alerts into notifications ---
    swept = post("/alerts/sweep")

    # --- summary ---
    dash = get(f"/entities/{eid}/dashboard")
    runway = get(f"/entities/{eid}/finance/runway")
    health = get(f"/entities/{eid}/compliance/health")
    portal = get("/portal")
    print("\n=== Demo workspace seeded ===")
    print(f"  login:            {EMAIL} / {PASSWORD}")
    print(f"  company:          {dash['entity']['name']}")
    print(f"  shares issued:    {dash['cap_table']['total_shares']:,} across {dash['cap_table']['holders']} holders")
    print(f"  capital raised:   Rs {dash['cap_table']['total_invested']}")
    print(f"  compliance:       {health['filed']}/{health['total']} filed, {health['overdue']} overdue (score {health['score']}%)")
    print(f"  runway:           {runway['runway_months']} months (cash Rs {runway['latest_cash']})")
    print(f"  portal:           {portal['summary']['companies']} company, {portal['summary']['funds']} fund (LP), "
          f"Rs {portal['summary']['total_committed']} committed")
    print(f"  reminders swept:  {swept['notifications_created']} notifications")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Paper demo workspace")
    parser.add_argument("--fresh", action="store_true", help="delete paper_dev.db first")
    args = parser.parse_args()

    db_path = API_DIR / "paper_dev.db"
    if args.fresh and db_path.exists():
        db_path.unlink()
    os.environ["PAPER_DATABASE_URL"] = "sqlite:///" + db_path.as_posix()

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        seed(client)


if __name__ == "__main__":
    main()
