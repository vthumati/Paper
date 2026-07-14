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
