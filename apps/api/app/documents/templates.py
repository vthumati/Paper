"""Document templates as data (HLD §6.4, FR-F-1). Bodies use $placeholders
(string.Template); missing placeholders render blank so partial data is fine."""
from dataclasses import dataclass
from string import Template


@dataclass(frozen=True)
class DocumentTemplate:
    key: str
    name: str
    doc_type: str
    body: str


REGISTRY: dict[str, DocumentTemplate] = {}


def register(t: DocumentTemplate) -> None:
    REGISTRY[t.key] = t


class _Blank(dict):
    def __missing__(self, key):  # render unknown placeholders as empty
        return ""


def render(template_key: str, data: dict) -> str:
    t = REGISTRY[template_key]
    safe = _Blank({k: ("" if v is None else str(v)) for k, v in (data or {}).items()})
    return Template(t.body).substitute(safe)


register(
    DocumentTemplate(
        "board_resolution",
        "Board Resolution",
        "board_resolution",
        "BOARD RESOLUTION OF $company\n"
        "Date: $date\n\n"
        "RESOLVED THAT $resolution_text\n\n"
        "For $company\n$signatory, Director\n",
    )
)
register(
    DocumentTemplate(
        "share_certificate",
        "Share Certificate",
        "share_certificate",
        "SHARE CERTIFICATE\n"
        "Company: $company\nCertificate No: $certificate_no\n\n"
        "This certifies that $holder holds $quantity $security_class shares "
        "of face value INR $par_value each.\n",
    )
)
register(
    DocumentTemplate(
        "sha",
        "Shareholders Agreement (summary)",
        "sha",
        "SHAREHOLDERS AGREEMENT (summary)\n"
        "Company: $company\nInvestor: $investor\n\n"
        "Investment of INR $amount for $shares shares at INR $price per share.\n",
    )
)
register(
    DocumentTemplate(
        "term_sheet",
        "Term Sheet",
        "term_sheet",
        "TERM SHEET — $round\n"
        "Company: $company\nInstrument: $instrument\n\n"
        "Pre-money valuation: INR $pre_money\nRound size: INR $target\n"
        "Price per share: INR $price\n",
    )
)
register(
    DocumentTemplate(
        "spice_plus",
        "SPICe+ (incorporation) — summary",
        "spice_plus",
        "SPICe+ INCORPORATION APPLICATION (summary)\n"
        "Proposed name: $company\nType: $entity_type\nState: $state\n"
        "Authorised capital: INR $authorised_capital\nPaid-up capital: INR $paid_up_capital\n"
        "Registered office: $registered_office\nFirst directors: $directors\n",
    )
)
register(
    DocumentTemplate(
        "emoa",
        "Memorandum of Association (eMoA)",
        "emoa",
        "MEMORANDUM OF ASSOCIATION\nName clause: $company\n"
        "State: $state\nObjects: $objects\n"
        "Liability: Limited by shares\nCapital: INR $authorised_capital\n",
    )
)
register(
    DocumentTemplate(
        "eaoa",
        "Articles of Association (eAoA)",
        "eaoa",
        "ARTICLES OF ASSOCIATION\nCompany: $company\n"
        "Adopts Table F of the Companies Act, 2013 with the following modifications:\n"
        "$modifications\n",
    )
)
register(
    DocumentTemplate(
        "meeting_notice",
        "Notice of Meeting",
        "meeting_notice",
        "NOTICE OF $meeting_type MEETING\n$company\n\n"
        "Notice is hereby given that a meeting will be held on $date"
        " at $venue.\n\nAGENDA:\n$agenda\n\nQuorum required: $quorum\n",
    )
)
register(
    DocumentTemplate(
        "indemnification",
        "Director & Officer Indemnification Agreement",
        "indemnification",
        "DIRECTOR & OFFICER INDEMNIFICATION AGREEMENT\n"
        "Company: $company\nIndemnitee: $name ($designation)\nDate: $date\n\n"
        "The Company agrees to indemnify the Indemnitee against liabilities "
        "reasonably incurred in the good-faith discharge of their duties, to the "
        "fullest extent permitted by the Companies Act, 2013.\n",
    )
)
register(
    DocumentTemplate(
        "msa",
        "Master Services Agreement",
        "msa",
        "MASTER SERVICES AGREEMENT\n"
        "Between: $company (Company)\nAnd: $counterparty (Counterparty)\n"
        "Title: $title\nValue: INR $value\nDate: $date\n\n"
        "The parties agree to the terms set out in the attached schedules.\n",
    )
)
register(
    DocumentTemplate(
        "sow",
        "Statement of Work",
        "sow",
        "STATEMENT OF WORK\n"
        "Company: $company\nCounterparty: $counterparty\nEngagement: $title\n"
        "Value: INR $value\nDate: $date\n",
    )
)
register(
    DocumentTemplate(
        "offer_letter",
        "Employment Offer Letter",
        "offer_letter",
        "OFFER LETTER\n$company\nDate: $date\n\n"
        "Dear $name,\n\n"
        "We are pleased to offer you the position of $title at $company.\n"
        "This offer is subject to the company's policies and the execution of the "
        "enclosed IP assignment and confidentiality agreement.\n\n"
        "For $company\n",
    )
)
register(
    DocumentTemplate(
        "ip_assignment",
        "IP Assignment & Confidentiality",
        "ip_assignment",
        "IP ASSIGNMENT & CONFIDENTIALITY AGREEMENT\n"
        "Company: $company\nIndividual: $name\nDate: $date\n\n"
        "$name hereby assigns to $company all right, title and interest in any "
        "intellectual property created in the course of engagement, and agrees to "
        "keep the company's confidential information confidential.\n",
    )
)
register(
    DocumentTemplate(
        "nda",
        "Non-Disclosure Agreement",
        "nda",
        "MUTUAL NON-DISCLOSURE AGREEMENT\n"
        "Between $company and $name\nDate: $date\n\n"
        "The parties agree to protect each other's confidential information.\n",
    )
)
register(
    DocumentTemplate(
        "pas4",
        "Form PAS-4 (Private Placement Offer Letter)",
        "pas4",
        "FORM PAS-4 — PRIVATE PLACEMENT OFFER LETTER\n"
        "Company: $company\n\n"
        "Offer of $shares shares at INR $price per share to $investor.\n",
    )
)
register(
    DocumentTemplate(
        "lp_statement",
        "LP Capital Account Statement",
        "lp_statement",
        "CAPITAL ACCOUNT STATEMENT\n"
        "Fund: $fund\nLimited Partner: $lp\nAs of: $as_of\n\n"
        "Commitment:            INR $committed\n"
        "Capital contributed:   INR $drawn\n"
        "Undrawn commitment:    INR $remaining\n"
        "Distributions to date: INR $distributed\n"
        "Management fees charged: INR $fees_charged\n"
        "Units held:            $units (par INR 10)\n\n"
        "Fund performance (whole-fund): DPI $dpi | TVPI $tvpi | XIRR $xirr%\n"
        "Fund NAV (portfolio marks):    INR $nav | NAV per unit: INR $nav_per_unit\n\n"
        "This statement is generated from the fund's drawdown and distribution\n"
        "ledgers and is provided for information only.\n",
    )
)
register(
    DocumentTemplate(
        "form_64c",
        "Form 64C (Income distributed to unit holder)",
        "form_64c",
        "FORM 64C\n"
        "Statement of income distributed by an investment fund to a unit holder\n"
        "(under section 115UB read with rule 12CB)\n\n"
        "Investment fund: $fund (SEBI AIF Category $category)\n"
        "Unit holder:     $lp\n"
        "Financial year:  $fy\n\n"
        "Income distributed during the year: INR $distributed\n"
        "Units held: $units\n\n"
        "Note: prepared from the fund's distribution ledger for information;\n"
        "verify classification of income heads with your tax advisor.\n",
    )
)
register(
    DocumentTemplate(
        "form_64d",
        "Form 64D (Income distributed by investment fund)",
        "form_64d",
        "FORM 64D\n"
        "Statement of income distributed by an investment fund\n"
        "(under section 115UB read with rule 12CB)\n\n"
        "Investment fund: $fund (SEBI AIF Category $category)\n"
        "Financial year:  $fy\n\n"
        "Total income distributed to unit holders: INR $total_distributed\n\n"
        "Distribution by unit holder:\n$rows\n"
        "Note: prepared from the fund's distribution ledger for information.\n",
    )
)
register(
    DocumentTemplate(
        "subscription_agreement",
        "Subscription Agreement",
        "subscription_agreement",
        "SUBSCRIPTION AGREEMENT\n"
        "Vehicle: $vehicle\nTarget investment: $target\n"
        "Subscriber: $investor\nDate: $date\n\n"
        "The Subscriber irrevocably subscribes for an interest in the Vehicle\n"
        "with a capital commitment of INR $amount, payable as called by the\n"
        "sponsor ($sponsor).\n\n"
        "Key terms: carried interest $carry% to the sponsor; minimum\n"
        "commitment INR $min_ticket; no management fee.\n\n"
        "The Subscriber confirms the commitment is made under the private\n"
        "placement provisions of the Companies Act, 2013 / applicable SEBI\n"
        "regulations, and that no public solicitation was involved.\n",
    )
)
register(
    DocumentTemplate(
        "pas4_offer_letter",
        "PAS-4 Private Placement Offer Letter",
        "pas4_offer_letter",
        "FORM PAS-4\n"
        "PRIVATE PLACEMENT OFFER CUM APPLICATION LETTER\n"
        "(pursuant to section 42 and rule 14(3) of the Companies\n"
        "(Prospectus and Allotment of Securities) Rules, 2014)\n\n"
        "Company: $company\nOffer: $round\nInstrument: $instrument\n"
        "Offeree: $investor\nDate: $date\n\n"
        "Offer: $shares securities at INR $price each, aggregating INR $amount.\n\n"
        "This offer is made only to the named offeree and is not transferable.\n"
        "Payment must be made from the offeree's own bank account. The company\n"
        "shall allot within 60 days of receiving application money and file\n"
        "PAS-3 within 15 days of allotment.\n",
    )
)
register(
    DocumentTemplate(
        "charter_amendment",
        "Charter Amendment (MoA/AoA alteration)",
        "charter_amendment",
        "CHARTER AMENDMENT — $kind\n"
        "Company: $company\nDate: $date\n\n"
        "Proposed alteration:\n$description\n\n"
        "Approved by special resolution ($resolution_title). MGT-14 must be\n"
        "filed with the Registrar within 30 days of the resolution passing.\n",
    )
)
register(
    DocumentTemplate(
        "offer_letter_packages",
        "Offer Letter (compensation packages)",
        "offer_letter",
        "OFFER OF EMPLOYMENT\n"
        "Company: $company\nCandidate: $candidate\nPosition: $position\nDate: $date\n\n"
        "Congratulations! We are delighted to offer you a position at $company.\n\n"
        "YOUR CHOICE OF COMPENSATION PACKAGES\n"
        "Pick the balance of cash and equity that fits you best:\n\n"
        "$packages\n"
        "Equity terms: ESOP options, $vesting vesting. Options are granted\n"
        "under the company's ESOP scheme subject to board approval.\n\n"
        "$projection\n"
        "This offer is open for acceptance for 7 days.\n\nFor $company\n$signatory\n",
    )
)
register(
    DocumentTemplate(
        "safe_agreement",
        "SAFE / Convertible Note Agreement",
        "safe_agreement",
        "$instrument_label AGREEMENT (iSAFE-style summary)\n"
        "Company: $company\nInvestor: $investor\nDate: $date\n\n"
        "Investment amount: INR $principal\n"
        "Valuation cap:     $cap\n"
        "Discount:          $discount\n"
        "MFN:               $mfn\n"
        "Interest:          $interest\n\n"
        "On a qualifying priced round the investment converts into the round's\n"
        "security at the lower of the cap price and the discounted round price.\n"
        "Issued under the private placement provisions of section 42 of the\n"
        "Companies Act, 2013; board approval recorded separately.\n",
    )
)
register(
    DocumentTemplate(
        "diligence_report",
        "Diligence Readiness Report",
        "diligence_report",
        "DILIGENCE READINESS REPORT\n"
        "Company: $company\nAs of: $date\n\n"
        "Readiness score: $score / 100\n"
        "Checks run: $checks_run | Findings: $finding_count\n\n"
        "$findings\n"
        "Generated by the diligence engine from the company's own records;\n"
        "resolve high-severity items before opening a data room to investors.\n",
    )
)
register(
    DocumentTemplate(
        "esop_expense",
        "ESOP Expense Report (Ind AS 102)",
        "esop_expense",
        "SHARE-BASED PAYMENT EXPENSE — Ind AS 102\n"
        "Company: $company\nAs of: $date\n\n"
        "Valuation assumptions: $assumptions\n\n"
        "Per grant (grant-date fair value):\n$grants\n\n"
        "Expense by financial year (straight-line over vesting):\n$by_fy\n\n"
        "Total grant-date fair value: INR $total_fair_value\n"
        "Recognised to date: INR $recognized_to_date\n"
        "Unrecognised (future periods): INR $unrecognized\n\n"
        "Options are valued using Black-Scholes at grant; RSUs/RSAs at full FMV. "
        "Forfeiture true-ups are not modelled — review with your auditor.\n",
    )
)
register(
    DocumentTemplate(
        "investor_report",
        "Investor Report",
        "investor_report",
        "INVESTOR REPORT — $period\n"
        "Company: $company\n\n"
        "KEY METRICS\n$metrics\n\n"
        "HIGHLIGHTS\n$highlights\n",
    )
)
register(
    DocumentTemplate(
        "esop_egm_notice",
        "EGM Notice — ESOP Scheme (s.62(1)(b))",
        "esop_egm_notice",
        "NOTICE OF EXTRAORDINARY GENERAL MEETING\n"
        "$company\nDate of notice: $date\n\n"
        "Notice is hereby given that an EGM of the members will be held to consider, "
        "and if thought fit, to pass the following as a SPECIAL RESOLUTION under "
        "Section 62(1)(b) of the Companies Act, 2013:\n\n"
        "\"RESOLVED THAT approval of the members be and is hereby accorded to the "
        "$scheme employee stock option scheme, and to the creation of a pool of "
        "$pool_size options exercisable into equity shares, and that the Board be "
        "authorised to grant, and to do all acts necessary to give effect to the scheme.\"\n\n"
        "Explanatory statement (s.102) and the scheme policy are annexed.\n"
        "By order of the Board, $company\n",
    )
)
register(
    DocumentTemplate(
        "esop_policy",
        "ESOP Scheme Policy",
        "esop_policy",
        "EMPLOYEE STOCK OPTION SCHEME — $scheme\n"
        "Company: $company\nAdopted: $date\n\n"
        "1. Pool size: $pool_size options.\n"
        "2. Eligibility: permanent employees and directors (excluding promoters and "
        "independent directors, per SBEB norms).\n"
        "3. Vesting: minimum one-year cliff from grant; balance over the vesting term "
        "set per grant.\n"
        "4. Exercise: within the exercise window(s) notified by the Board; lapse on the "
        "terms in the grant letter on cessation of employment.\n"
        "5. Administration: the Board (or its Compensation Committee) administers the "
        "scheme and fixes the exercise price at or above face value.\n"
        "6. Adjustments: the pool and grants adjust for splits, bonuses and other "
        "corporate actions.\n",
    )
)
register(
    DocumentTemplate(
        "soi_statement",
        "Schedule of Investments",
        "soi",
        "SCHEDULE OF INVESTMENTS\n"
        "Fund: $fund\nAs of: $date\n\n"
        "Holdings ($count):\n"
        "$holdings\n\n"
        "Total cost: ₹$total_cost\n"
        "Total fair value: ₹$total_value\n"
        "Unrealised gain: ₹$total_gain\n"
        "Blended MOIC: $moic\n\n"
        "Fair values are the fund's own marks; unmarked positions are held at cost.\n",
    )
)
register(
    DocumentTemplate(
        "valuation_estimate",
        "Indicative Valuation Workpaper",
        "valuation_estimate",
        "INDICATIVE VALUATION WORKPAPER\n"
        "Company: $company\nScenario: $label\nAs of: $date\n\n"
        "$methods\n"
        "Method weighting: $weights\n"
        "Blended enterprise value: ₹$blended_value\n"
        "Fully-diluted shares: $fd_shares\n"
        "Indicative value per share: ₹$per_share\n\n"
        "$disclaimer\n",
    )
)
