"""Startup lifecycle stages + feature packs (rules-as-data, ADR-3).

Two orthogonal axes, one gating system:

* **Feature pack** (starter / growth / scale) — the commercial tier a workspace
  is on. This is the *only* thing that decides which tabs and feature-parts are
  visible. Starter is day-one legal hygiene; Growth adds raising + investors;
  Scale adds institutional / pre-IPO depth. Packs are cumulative.

* **Lifecycle stage** (inception … pre-IPO) — where the company actually is.
  Stages drive ONLY the guided "what to do now" checklist and the suggested
  next step; they no longer hide tabs. A stage suggests a pack (suggested_pack)
  the same way it suggests the next stage.

Companies only — funds/SPVs keep their own tab set. Everything stays reachable
via the UI's "show all" toggle; packs hide noise, they never remove capability.
"""

PACKS = ["starter", "growth", "scale"]

PACK_INFO = {
    "starter": {
        "label": "Starter",
        "blurb": "Incorporation, cap table, ESOP, team and compliance — day-one legal hygiene.",
    },
    "growth": {
        "label": "Growth",
        "blurb": "Everything in Starter, plus raising rounds, valuations, data room and investor reporting.",
    },
    "scale": {
        "label": "Scale",
        "blurb": "Everything in Growth, plus advanced cap-table actions, managed admin and fund/SPV administration.",
    },
}

# Company tab -> the pack it first appears in (cumulative: starter ⊂ growth ⊂ scale).
TAB_PACK = {
    # Starter — day-one legal hygiene
    "dashboard": "starter",
    "tasks": "starter",
    "captable": "starter",
    "esop": "starter",
    "team": "starter",
    "governance": "starter",
    "compliance": "starter",
    "registers": "starter",
    "documents": "starter",
    "startup": "starter",
    "services": "starter",
    # Growth — raising + investors
    "fundraising": "growth",
    "valuations": "growth",
    "diligence": "growth",
    "investors": "growth",
    "contracts": "growth",
    "finance": "growth",
    "advisors": "growth",
    # Scale — institutional / pre-IPO
    "admin": "scale",
}

# Cap-table (and other in-tab) feature parts -> the pack that unlocks them.
FEATURE_PACK = {
    "founder_vesting": "starter",
    "fully_diluted": "starter",
    "dataroom": "growth",
    "transfers": "growth",
    "conversions": "growth",
    "rights_issues": "growth",
    "buybacks": "scale",
    "corporate_actions": "scale",
    "waterfall": "scale",
    "anti_dilution": "scale",
    "demat": "scale",
}

STAGES = ["inception", "preseed", "seed", "series", "ipo"]

# The pack a company at a given stage would typically be on (drives suggested_pack).
STAGE_PACK = {
    "inception": "starter",
    "preseed": "starter",
    "seed": "growth",
    "series": "growth",
    "ipo": "scale",
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
             "hint": "Share documents with investors — access is logged and watermarked.", "tab": "documents"},
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


def pack_rank(pack: str) -> int:
    return PACKS.index(pack) if pack in PACKS else 0


def tabs_for(pack: str) -> list[str]:
    """Company tabs visible on a given pack (cumulative)."""
    r = pack_rank(pack)
    return [t for t, p in TAB_PACK.items() if pack_rank(p) <= r]


def features_for(pack: str) -> dict[str, bool]:
    r = pack_rank(pack)
    return {k: r >= pack_rank(v) for k, v in FEATURE_PACK.items()}


def pack_for_stage(stage: str) -> str:
    return STAGE_PACK.get(stage, "starter")
