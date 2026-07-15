"""Startup lifecycle stages (rules-as-data, ADR-3).

Each stage defines what a founder should see and do *now*: which workspace
tabs are surfaced, which feature parts are unlocked, and a guided checklist
whose items are auto-checked off from real data (predicates live in
services/stage.py, keyed by `done`). Companies only — funds/SPVs keep their
own tab set. Everything stays reachable via the UI's "show all" toggle;
stages hide noise, they never remove capability.
"""

STAGES = ["inception", "preseed", "seed", "series", "ipo"]

# Tabs every company sees at every stage.
BASE_TABS = ["dashboard", "captable", "esop", "team", "governance", "compliance",
             "documents", "workflows", "startup", "registers", "files", "services", "admin"]

# Extra tabs unlocked at (and after) a stage.
STAGE_TABS = {
    "inception": [],
    "preseed": ["fundraising", "finance"],
    "seed": ["valuations", "dataroom", "diligence", "investors"],
    "series": ["contracts"],
    "ipo": [],
}

# Feature parts within tabs, unlocked at (and after) a stage.
FEATURE_MIN_STAGE = {
    "founder_vesting": "inception",
    "fully_diluted": "preseed",
    "transfers": "seed",
    "conversions": "series",
    "buybacks": "series",
    "corporate_actions": "series",
    "waterfall": "series",
    "rights_issues": "series",
    "anti_dilution": "series",
    "demat": "ipo",
}

# checklist item: key (done-predicate in services/stage.py), title,
# what/why in one founder-readable line, and the tab that does it.
STAGE_INFO = {
    "inception": {
        "label": "Inception",
        "headline": "Set the company up right — clean ownership and filings from day one.",
        "checklist": [
            {"key": "incorporated", "title": "Record incorporation details",
             "hint": "CIN, PAN and incorporation date drive your compliance calendar.", "tab": "dashboard"},
            {"key": "founder_shares", "title": "Issue founder shares",
             "hint": "Create a share class, add founders as stakeholders, record the issuances.", "tab": "captable"},
            {"key": "founder_vesting", "title": "Put founder shares on reverse vesting",
             "hint": "Standard 4-year / 1-year-cliff protects everyone if a founder leaves.", "tab": "captable"},
            {"key": "directors", "title": "Appoint your board of directors",
             "hint": "Record directors with DINs — DIR-12 filings are tracked automatically.", "tab": "governance"},
            {"key": "compliance_calendar", "title": "Generate your compliance calendar",
             "hint": "One click creates every annual ROC filing with due dates from your FY end.", "tab": "compliance"},
            {"key": "registrations", "title": "Add GST / state registrations",
             "hint": "Track GST, PF, ESIC and Shops & Establishments numbers per state.", "tab": "registers"},
        ],
    },
    "preseed": {
        "label": "Pre-seed",
        "headline": "First money in — angels and F&F on SAFEs, team, tax benefits.",
        "checklist": [
            {"key": "esop_pool", "title": "Create an ESOP pool",
             "hint": "Investors expect a pool (typically 5–15%) before your first round.", "tab": "esop"},
            {"key": "dpiit", "title": "Get DPIIT Startup India recognition",
             "hint": "Unlocks 80-IAC tax holiday and angel-tax exemption applications.", "tab": "startup"},
            {"key": "team_onboarded", "title": "Onboard your team with IP assignment",
             "hint": "Offer letter, IP assignment and NDA are generated per hire — diligence-ready.", "tab": "team"},
            {"key": "instrument", "title": "Raise from family, friends & angels (SAFEs / notes)",
             "hint": "Tag each cheque by investor type; the Sec 42 limit of 200 offerees per FY is enforced for you.", "tab": "fundraising"},
            {"key": "pipeline", "title": "Track your investor pipeline",
             "hint": "Move prospects from contacted to committed; convert them into the round.", "tab": "fundraising"},
            {"key": "finance", "title": "Track monthly cash, burn and runway",
             "hint": "Investors ask for runway first; keep snapshots current.", "tab": "finance"},
        ],
    },
    "seed": {
        "label": "Seed",
        "headline": "Your first priced round — valuation, diligence, allotment.",
        "checklist": [
            {"key": "valuation", "title": "Get a valuation report",
             "hint": "A Rule 11UA / fair-value report prices your ESOPs and your round.", "tab": "valuations"},
            {"key": "round_open", "title": "Open a priced round",
             "hint": "Model pre-money, target and price; generate the term sheet.", "tab": "fundraising"},
            {"key": "dataroom", "title": "Set up a diligence data room",
             "hint": "Share documents with investors — access is logged and watermarked.", "tab": "dataroom"},
            {"key": "esop_granted", "title": "Grant ESOPs to early team",
             "hint": "Grants vest against the pool; exercises flow into the cap table.", "tab": "esop"},
            {"key": "round_closed", "title": "Close the round",
             "hint": "Closing allots shares and auto-adds PAS-3 (and FC-GPR for foreign money) to Compliance.", "tab": "fundraising"},
        ],
    },
    "series": {
        "label": "Series rounds",
        "headline": "Institutional capital — tighter governance, investor terms, reporting.",
        "checklist": [
            {"key": "board_meeting", "title": "Run board meetings with agenda and notice",
             "hint": "Agenda, notice and minutes per meeting — as your SHA requires.", "tab": "governance"},
            {"key": "special_resolution", "title": "Record special resolutions",
             "hint": "Charter changes need special resolutions; MGT-14 is added automatically.", "tab": "governance"},
            {"key": "anti_dilution", "title": "Add anti-dilution terms to preferred classes",
             "hint": "Broad-based weighted average is market standard; model down-rounds before signing.", "tab": "captable"},
            {"key": "investor_access", "title": "Give investors portal access",
             "hint": "Investors see their own holdings, documents and updates — nothing else.", "tab": "investors"},
            {"key": "investor_update", "title": "Publish investor updates",
             "hint": "A regular update keeps your investors engaged (and your next round warm).", "tab": "investors"},
            {"key": "contracts", "title": "Track commercial contracts and renewals",
             "hint": "MSAs and SOWs with renewal alerts — revenue diligence starts here.", "tab": "contracts"},
            {"key": "sbo_register", "title": "File SBO declarations and charges",
             "hint": "Significant-beneficial-owner and charge registers must stay current.", "tab": "registers"},
        ],
    },
    "ipo": {
        "label": "Pre-IPO",
        "headline": "Readiness — clean registers, demat, audits, zero overdue filings.",
        "checklist": [
            {"key": "demat", "title": "Dematerialise your share classes",
             "hint": "ISINs via NSDL/CDSL are mandatory before any public offer.", "tab": "captable"},
            {"key": "audit", "title": "Run a corporate / pre-diligence audit",
             "hint": "Engage an auditor to sweep the record before bankers do.", "tab": "admin"},
            {"key": "registers_complete", "title": "Complete statutory registers",
             "hint": "SBO, charges and registrations must be complete and current.", "tab": "registers"},
            {"key": "compliance_clean", "title": "Clear every overdue filing",
             "hint": "Get the compliance health score to 100% — no overdue obligations.", "tab": "compliance"},
        ],
    },
}


def stage_rank(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else 0


def tabs_for(stage: str) -> list[str]:
    tabs = list(BASE_TABS)
    for s in STAGES[: stage_rank(stage) + 1]:
        tabs += STAGE_TABS[s]
    return tabs


def features_for(stage: str) -> dict[str, bool]:
    r = stage_rank(stage)
    return {k: r >= stage_rank(v) for k, v in FEATURE_MIN_STAGE.items()}
