"""Term sheet scanner (FR-E-11): rules-as-data review of pasted term-sheet
text. Each rule is a regex-driven detector that flags off-market terms with a
founder-readable explanation of the India-market standard. Deliberately
rules-based (no ML): every finding cites the matched text, so the output is
explainable and testable. This is information, not legal advice."""
import re

SNIPPET_CHARS = 90


def _snippet(text: str, start: int, end: int) -> str:
    lo, hi = max(0, start - SNIPPET_CHARS // 2), min(len(text), end + SNIPPET_CHARS // 2)
    return ("…" if lo > 0 else "") + text[lo:hi].strip() + ("…" if hi < len(text) else "")


def _finding(code, severity, title, detail, snippet=None):
    return {"code": code, "severity": severity, "title": title, "detail": detail,
            "snippet": snippet}


# ---- individual rules: each takes the lowercased text and returns findings ----

def _liquidation_multiple(text):
    out = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*[x×]\s*(?:the\s+)?(?:original|purchase|issue|liquidation)", text):
        mult = float(m.group(1))
        if mult > 1:
            out.append(_finding(
                "liq_pref_multiple", "red", f"{m.group(1)}x liquidation preference",
                "Market standard in India is a 1x non-participating preference. Anything "
                "above 1x means investors take a multiple of their money before common "
                "holders see anything.", _snippet(text, m.start(), m.end()),
            ))
    return out


def _participating(text):
    m = re.search(r"\bparticipating\b", text)
    if m is None or re.search(r"non[-\s]?participating", text):
        return []
    return [_finding(
        "participating_preferred", "red", "Participating liquidation preference",
        "Participating preferred double-dips: the investor takes the preference AND "
        "shares pro-rata in the remainder. Standard is non-participating (investor "
        "chooses preference or pro-rata, not both).", _snippet(text, m.start(), m.end()),
    )]


def _full_ratchet(text):
    m = re.search(r"full[-\s]?ratchet", text)
    if m is None:
        return []
    return [_finding(
        "full_ratchet", "red", "Full-ratchet anti-dilution",
        "Full ratchet reprices the entire investment to any lower future price, however "
        "small the down round. Broad-based weighted average is the market standard.",
        _snippet(text, m.start(), m.end()),
    )]


def _bbwa(text):
    m = re.search(r"broad[-\s]?based weighted average", text)
    if m is None:
        return []
    return [_finding(
        "bbwa", "ok", "Broad-based weighted-average anti-dilution",
        "This is the market-standard anti-dilution formula — fair to both sides.",
        _snippet(text, m.start(), m.end()),
    )]


def _exclusivity(text):
    for m in re.finditer(r"(?:exclusivity|no[-\s]?shop)[^.]{0,80}?(\d{2,3})\s*(?:calendar\s+)?days", text):
        days = int(m.group(1))
        if days > 45:
            return [_finding(
                "long_exclusivity", "amber", f"{days}-day exclusivity / no-shop",
                "30–45 days is customary. A longer lock-up leaves you unable to talk to "
                "other investors if this deal stalls.", _snippet(text, m.start(), m.end()),
            )]
    return []


def _pool_shuffle(text):
    for m in re.finditer(r"(?:esop|option)\s+pool[^.]{0,120}?(\d{1,2}(?:\.\d+)?)\s*%", text):
        pct = float(m.group(1))
        pre = re.search(r"pre[-\s]?money", text[max(0, m.start() - 120):m.end() + 120])
        if pct > 15 and pre:
            return [_finding(
                "pool_shuffle", "amber", f"{m.group(1)}% ESOP pool created pre-money",
                "A pre-money pool top-up dilutes only existing holders — the larger the "
                "pool, the lower your effective pre-money. 10–15% is typical; size it to "
                "your actual 18-month hiring plan.", _snippet(text, m.start(), m.end()),
            )]
    return []


def _redemption(text):
    m = re.search(r"\b(redeem|redemption|put option|buy[-\s]?back at the option of the investor)", text)
    if m is None:
        return []
    return [_finding(
        "redemption_put", "red", "Redemption / put right",
        "A right to force the company (or founders) to buy the investor out is "
        "off-market for venture deals — and assured-return puts to non-resident "
        "investors run into FEMA pricing restrictions.", _snippet(text, m.start(), m.end()),
    )]


def _cumulative_dividend(text):
    m = re.search(r"cumulative\s+dividend", text)
    if m is None:
        return []
    return [_finding(
        "cumulative_dividend", "amber", "Cumulative dividends",
        "Dividends that accrue whether or not declared quietly grow the preference "
        "stack every year. Venture-standard is the 0.01% statutory CCPS coupon, "
        "non-cumulative.", _snippet(text, m.start(), m.end()),
    )]


def _founder_guarantee(text):
    m = re.search(r"(personal(?:ly)?\s+guarantee|founders?\s+shall\s+(?:jointly\s+)?indemnif)", text)
    if m is None:
        return []
    return [_finding(
        "founder_guarantee", "red", "Personal guarantee / founder indemnity",
        "Founders should not personally guarantee company obligations or indemnify "
        "investors beyond fundamental warranties. Company-level indemnity is the norm.",
        _snippet(text, m.start(), m.end()),
    )]


def _drag_threshold(text):
    for m in re.finditer(r"drag[-\s]?along[^.]{0,120}?(\d{1,2}(?:\.\d+)?)\s*%", text):
        pct = float(m.group(1))
        if pct < 50:
            return [_finding(
                "low_drag_threshold", "amber", f"Drag-along triggered at {m.group(1)}%",
                "A drag exercisable by a minority can force founders to sell. Market "
                "standard requires a majority (often board + majority preferred + "
                "founder consent below a valuation floor).", _snippet(text, m.start(), m.end()),
            )]
    return []


def _standard_confirmations(text):
    """Presence of customary, founder-neutral terms — reported as 'ok'."""
    out = []
    checks = [
        (r"pro[-\s]?rata", "pro_rata", "Pro-rata rights",
         "Customary — lets the investor maintain their stake in future rounds."),
        (r"right of first refusal|rofr", "rofr", "Right of first refusal",
         "Customary on founder transfers; pair with reasonable exceptions."),
        (r"tag[-\s]?along", "tag_along", "Tag-along rights",
         "Customary minority protection on founder exits."),
        (r"information rights", "info_rights", "Information rights",
         "Customary — quarterly financials and an annual budget are typical."),
        (r"1\s*[x×]\s*(?:non[-\s]?participating)?", "one_x", "1x preference detected",
         "A 1x preference is the market standard."),
    ]
    for pattern, code, title, detail in checks:
        m = re.search(pattern, text)
        if m is not None:
            out.append(_finding(code, "ok", title, detail, None))
    return out


RULES = [
    _liquidation_multiple,
    _participating,
    _full_ratchet,
    _bbwa,
    _exclusivity,
    _pool_shuffle,
    _redemption,
    _cumulative_dividend,
    _founder_guarantee,
    _drag_threshold,
    _standard_confirmations,
]

SEVERITY_ORDER = {"red": 0, "amber": 1, "ok": 2}


def scan(text: str) -> dict:
    norm = re.sub(r"\s+", " ", text).lower()
    findings = []
    for rule in RULES:
        findings.extend(rule(norm))
    findings.sort(key=lambda f: SEVERITY_ORDER[f["severity"]])
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in ("red", "amber", "ok")}
    if counts["red"]:
        verdict = "Off-market terms found — negotiate before signing."
    elif counts["amber"]:
        verdict = "Broadly standard, with a few points worth pushing back on."
    else:
        verdict = "No off-market terms detected by the rules run."
    return {
        "verdict": verdict,
        "counts": counts,
        "rules_run": len(RULES),
        "findings": findings,
        "disclaimer": "Rules-based review for information only — not legal advice.",
    }
