"""ESOP service (FR-D): vesting computation and exercise. Exercising options
issues real shares via the cap-table ledger (so exercised options appear in
the cap table) and records the perquisite value for tax."""
import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_owned
from ..models.captable import IssuanceTransaction, SecurityClass, Stakeholder
from ..models.esop import (
    ESOPScheme,
    ExerciseTransaction,
    ExerciseWindow,
    ForfeitureEvent,
    Grant,
)
from . import valuation as valsvc
from .money import CENTS, q

# Perquisite-tax defaults (FR-D-3). The ESOP perquisite (FMV − strike) is
# taxed as salary income (s.17(2)(vi)) at the employee's slab rate and withheld
# as TDS (s.192). We can't know their other income, so we estimate at a
# marginal rate — defaulting to the top slab plus the 4% health-and-education
# cess (surcharge, which depends on income level, is left out).
TOP_MARGINAL_RATE = Decimal("0.30")
CESS_RATE = Decimal("0.04")


def months_between(start: datetime.date, end: datetime.date) -> int:
    if end < start:
        return 0
    m = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        m -= 1
    return max(0, m)


def vested_quantity(grant: Grant, as_of: datetime.date) -> int:
    m = months_between(grant.grant_date, as_of)
    if m < grant.cliff_months:
        return 0
    if m >= grant.total_months:
        return grant.quantity
    return grant.quantity * m // grant.total_months


def add_months(d: datetime.date, m: int) -> datetime.date:
    y = d.year + (d.month - 1 + m) // 12
    mo = (d.month - 1 + m) % 12 + 1
    return datetime.date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def vesting_projection(grant: Grant, as_of: datetime.date, limit: int = 3) -> dict:
    """Forward view of a grant's vesting: full-vest date and the next few
    monthly vest events (the first event after the cliff is the cliff chunk)."""
    events = []
    prev = vested_quantity(grant, as_of)
    for m in range(1, grant.total_months + 1):
        d = add_months(grant.grant_date, m)
        if d <= as_of:
            continue
        v = vested_quantity(grant, d)
        if v > prev:
            events.append({"date": d, "quantity": v - prev})
            prev = v
        if len(events) >= limit:
            break
    return {
        "full_vest_date": add_months(grant.grant_date, grant.total_months),
        "next_vests": events,
    }


def exercise_windows(db: Session, entity_id: str, as_of: datetime.date) -> list[dict]:
    """The entity's exercise windows with a derived open/upcoming/closed state."""
    rows = (
        db.query(ExerciseWindow)
        .filter_by(entity_id=entity_id)
        .order_by(ExerciseWindow.opens_on)
        .all()
    )
    out = []
    for w in rows:
        state = "open" if w.opens_on <= as_of <= w.closes_on else (
            "upcoming" if as_of < w.opens_on else "closed"
        )
        out.append(
            {
                "id": w.id,
                "name": w.name,
                "opens_on": w.opens_on.isoformat(),
                "closes_on": w.closes_on.isoformat(),
                "state": state,
            }
        )
    return out


def exercise_allowed(db: Session, entity_id: str, as_of: datetime.date) -> bool:
    """Exercise windows are opt-in: if the entity defines none, exercise is
    unrestricted; otherwise it requires an open window."""
    windows = db.query(ExerciseWindow).filter_by(entity_id=entity_id).all()
    if not windows:
        return True
    return any(w.opens_on <= as_of <= w.closes_on for w in windows)


def grant_unit_value(grant: Grant, fmv) -> Decimal | None:
    """Per-unit value at today's price: intrinsic (FMV − strike, floored at 0)
    for options; full FMV for RSUs/RSAs (no exercise cost)."""
    if fmv is None:
        return None
    fmv = Decimal(fmv)
    if grant.grant_type == "option":
        return max(Decimal("0"), fmv - Decimal(grant.exercise_price))
    return fmv


def grant_value_summary(db: Session, grant: Grant, as_of: datetime.date, gv: dict | None = None) -> dict:
    """Ledgy-style value framing for one grant: today's value (vested and still
    held), value already exercised/settled, and the max potential value of the
    whole grant at today's price — plus the segment split for the status bar."""
    gv = gv or grant_view(db, grant, as_of)
    uv = grant_unit_value(grant, valsvc.current_fmv(db, grant.entity_id, as_of))
    qty, vested = gv["quantity"], gv["vested"]
    if grant.grant_type == "rsa":
        # shares issued upfront: vested = no longer at repurchase risk
        exercised_seg, held_seg = 0, vested
    else:
        exercised_seg, held_seg = gv["exercised"], gv["exercisable"]
    unvested_seg = qty - vested

    def money(units: int) -> str | None:
        return str((uv * units).quantize(CENTS, ROUND_HALF_UP)) if uv is not None else None

    return {
        "unit_value": str(uv.quantize(CENTS, ROUND_HALF_UP)) if uv is not None else None,
        "today_value": money(held_seg),
        "exercised_value": money(exercised_seg),
        "max_potential_value": money(qty),
        "segments": {"exercised": exercised_seg, "vested": held_seg, "unvested": unvested_seg},
    }


def perquisite_tax(
    perquisite: Decimal,
    marginal_rate: Decimal = TOP_MARGINAL_RATE,
    cess_rate: Decimal = CESS_RATE,
) -> dict:
    """Estimated tax on an ESOP perquisite (FR-D-3): income tax at the chosen
    marginal slab rate plus health-and-education cess, which is the TDS the
    employer withholds under s.192. Estimate only — surcharge and the employee's
    actual slab depend on their total income."""
    perquisite = Decimal(perquisite)
    income_tax = perquisite * Decimal(marginal_rate)
    cess = income_tax * Decimal(cess_rate)
    return {
        "perquisite": str(q(perquisite)),
        "marginal_rate": str(Decimal(marginal_rate)),
        "cess_rate": str(Decimal(cess_rate)),
        "income_tax": str(q(income_tax)),
        "cess": str(q(cess)),
        "tds": str(q(income_tax + cess)),
    }


def exercise_tax_estimate(
    db: Session,
    grant: Grant,
    quantity: int,
    as_of: datetime.date,
    marginal_rate: Decimal = TOP_MARGINAL_RATE,
    fmv: Decimal | None = None,
) -> dict:
    """What exercising `quantity` options (or settling RSUs) would cost and be
    taxed today: the cash exercise cost, the perquisite, the estimated TDS, and
    the resulting after-tax gain — the employee's 'what if I exercise now' view."""
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    if fmv is None:
        fmv = valsvc.current_fmv(db, grant.entity_id, as_of)
    strike = Decimal(grant.exercise_price)
    # RSUs settle for no consideration; RSAs are taxed at grant, not here.
    per_unit_gain = grant_unit_value(grant, fmv)
    perquisite = (per_unit_gain or Decimal("0")) * quantity
    exercise_cost = Decimal("0") if grant.grant_type == "rsu" else strike * quantity
    tax = perquisite_tax(perquisite, marginal_rate)
    return {
        "quantity": quantity,
        "fmv_per_share": str(fmv) if fmv is not None else None,
        "exercise_price": str(strike),
        "exercise_cost": str(q(exercise_cost)),
        **tax,
        "gain_after_tax": str(q(perquisite - Decimal(tax["tds"]))),
    }


def grant_schedule(grant: Grant, as_of: datetime.date) -> list[dict]:
    """Every vesting event of the grant as a timeline: each month where vested
    units increase, with the delta, running total and whether it's in the past
    (relative to `as_of`)."""
    events = []
    prev = 0
    for m in range(1, grant.total_months + 1):
        d = add_months(grant.grant_date, m)
        v = vested_quantity(grant, d)
        if v > prev:
            events.append(
                {"date": d.isoformat(), "units": v - prev, "cumulative": v, "past": d <= as_of}
            )
            prev = v
    return events


def exercised_quantity(db: Session, grant_id: str) -> int:
    return sum(
        e.quantity for e in db.query(ExerciseTransaction).filter_by(grant_id=grant_id)
    )


def exercised_by_grant(db: Session, entity_id: str) -> dict[str, int]:
    """{grant_id: total exercised} in one grouped query (avoids per-grant N+1)."""
    rows = (
        db.query(ExerciseTransaction.grant_id, func.sum(ExerciseTransaction.quantity))
        .filter_by(entity_id=entity_id)
        .group_by(ExerciseTransaction.grant_id)
        .all()
    )
    return {gid: int(total) for gid, total in rows}


def grant_view(db: Session, grant: Grant, as_of: datetime.date) -> dict:
    vested = vested_quantity(grant, as_of)
    exercised = exercised_quantity(db, grant.id)
    sh = db.get(Stakeholder, grant.stakeholder_id)
    view = {
        "id": grant.id,
        "scheme_id": grant.scheme_id,
        "stakeholder_id": grant.stakeholder_id,
        "stakeholder_name": sh.name if sh else None,
        "grant_type": grant.grant_type,
        "quantity": grant.quantity,
        "exercise_price": grant.exercise_price,
        "grant_date": grant.grant_date,
        "cliff_months": grant.cliff_months,
        "total_months": grant.total_months,
        "vested": vested,
        "exercised": exercised,
        # options/RSUs: how many vested units remain to exercise/settle
        "exercisable": vested - exercised,
        # RSAs: shares are issued upfront, so the meaningful figure is how many
        # are still subject to repurchase (unvested), not "exercisable".
        "unvested": grant.quantity - vested,
    }
    if grant.grant_type == "rsa":
        view["exercisable"] = 0
    return view


def esop_overview(db: Session, entity_id: str, as_of: datetime.date) -> dict:
    """Aggregate ESOP dashboard (FR-D-1): pool usage, option states across all
    grants, grantee count, grant-type mix, and a top-grants leaderboard. All
    derived from the grants/exercise ledger — read-only."""
    schemes = db.query(ESOPScheme).filter_by(entity_id=entity_id).all()
    pool_size = sum(s.pool_size for s in schemes)
    grants = db.query(Grant).filter_by(entity_id=entity_id).all()
    granted = vested = exercised = 0
    per_holder: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for g in grants:
        gv = grant_view(db, g, as_of)
        granted += gv["quantity"]
        vested += gv["vested"]
        exercised += gv["exercised"]
        per_holder[g.stakeholder_id] = per_holder.get(g.stakeholder_id, 0) + gv["quantity"]
        by_type[g.grant_type] = by_type.get(g.grant_type, 0) + 1
    exercisable = vested - exercised
    unvested = granted - vested
    available = max(0, pool_size - granted)
    forfeited = sum(
        f.lapsed_quantity for f in db.query(ForfeitureEvent).filter_by(entity_id=entity_id)
    )

    names = {s.id: s.name for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}
    leaderboard = [
        {"name": names.get(sid, "—"), "granted": qty}
        for sid, qty in sorted(per_holder.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]
    return {
        "pool_size": pool_size,
        "granted": granted,
        "available": available,
        "used_pct": round(granted / pool_size * 100, 2) if pool_size else 0.0,
        "vested": vested,
        "exercised": exercised,
        "exercisable": exercisable,
        "unvested": unvested,
        "forfeited": forfeited,
        "grantees": len(per_holder),
        "schemes": len(schemes),
        "by_type": by_type,
        "leaderboard": leaderboard,
        # donut segments over the whole pool (sum to pool_size)
        "pool_segments": {
            "exercised": exercised,
            "vested_unexercised": exercisable,
            "unvested": unvested,
            "available": available,
        },
    }


def generate_scheme_pack(db: Session, scheme: ESOPScheme, user_id: str) -> list:
    """The statutory ESOP-adoption pack (FR-D-1, s.62(1)(b)): board resolution,
    EGM notice with the special resolution, and the scheme policy — the
    documents a company needs to adopt an ESOP pool."""
    from ..clock import today_ist
    from ..models.entity import LegalEntity
    from . import document as docsvc

    entity = db.get(LegalEntity, scheme.entity_id)
    company = entity.name if entity else ""
    date = today_ist().isoformat()
    common = {"company": company, "scheme": scheme.name, "pool_size": f"{scheme.pool_size:,}", "date": date}
    specs = [
        ("board_resolution", f"Board Resolution — {scheme.name}", {
            **common,
            "resolution_text": (
                f"the {scheme.name} employee stock option scheme, with a pool of "
                f"{scheme.pool_size:,} options, be adopted subject to the approval of "
                "the members by special resolution, and the Board be authorised to "
                "administer the scheme and grant options thereunder"
            ),
            "signatory": "Authorised Director",
        }),
        ("esop_egm_notice", f"EGM Notice — {scheme.name}", common),
        ("esop_policy", f"ESOP Policy — {scheme.name}", common),
    ]
    docs = []
    for template_key, title, data in specs:
        docs.append(
            docsvc.create_document(
                db, entity_id=scheme.entity_id, template_key=template_key, data=data,
                user_id=user_id, title=title, subject_type="esop_scheme", subject_id=scheme.id,
            )
        )
    return docs


def create_grant(
    db: Session,
    scheme: ESOPScheme,
    stakeholder_id: str,
    quantity: int,
    exercise_price: Decimal,
    grant_date: datetime.date,
    cliff_months: int,
    total_months: int,
    grant_type: str = "option",
    security_class_id: str | None = None,
    fmv: Decimal = Decimal("0"),
) -> Grant:
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    if grant_type not in ("option", "rsu", "rsa"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown grant type")
    get_owned(db, Stakeholder, stakeholder_id, scheme.entity_id, "stakeholder")
    used = sum(g.quantity for g in db.query(Grant).filter_by(scheme_id=scheme.id))
    if used + quantity > scheme.pool_size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Grant exceeds scheme pool size")
    # RSUs have no strike — they settle to shares at vesting for no consideration.
    if grant_type == "rsu":
        exercise_price = Decimal("0")
    grant = Grant(
        scheme_id=scheme.id,
        entity_id=scheme.entity_id,
        stakeholder_id=stakeholder_id,
        grant_type=grant_type,
        quantity=quantity,
        exercise_price=exercise_price,
        grant_date=grant_date,
        cliff_months=cliff_months,
        total_months=total_months,
    )
    db.add(grant)
    db.flush()

    # RSAs are issued upfront: the shares exist from the grant date (subject to
    # repurchase of the unvested portion on early exit), and the discount to FMV
    # is a perquisite recognised at allotment (Sec 17(2)).
    if grant_type == "rsa":
        if not security_class_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "RSA needs a security class to issue shares into"
            )
        get_owned(db, SecurityClass, security_class_id, scheme.entity_id, "security class")
        fmv_used = Decimal(fmv)
        if fmv_used <= 0:
            looked_up = valsvc.current_fmv(db, scheme.entity_id, grant_date)
            fmv_used = looked_up if looked_up is not None else Decimal("0")
        issuance = IssuanceTransaction(
            entity_id=scheme.entity_id,
            security_class_id=security_class_id,
            stakeholder_id=stakeholder_id,
            quantity=quantity,
            price_per_unit=exercise_price,
            issue_date=grant_date,
        )
        db.add(issuance)
        db.flush()
        perquisite = max(Decimal("0"), fmv_used - exercise_price) * quantity
        db.add(
            ExerciseTransaction(
                grant_id=grant.id,
                entity_id=scheme.entity_id,
                quantity=quantity,
                fmv_per_share=fmv_used,
                exercise_price=exercise_price,
                perquisite_value=perquisite,
                issuance_id=issuance.id,
                date=grant_date,
                net_shares=quantity,
            )
        )

    db.commit()
    db.refresh(grant)
    return grant


def next_certificate_no(db: Session, entity_id: str) -> str:
    """Next sequential ESOP share-certificate number for the entity."""
    from ..models.document import Document

    n = (
        db.query(Document)
        .filter_by(entity_id=entity_id, template_key="share_certificate")
        .count()
    )
    return f"ESOP-{n + 1:04d}"


def _issue_share_certificate(
    db: Session, grant: Grant, ex: ExerciseTransaction, security_class_id: str,
    cert_no: str, quantity: int, user_id: str,
):
    """Generate a numbered share certificate for shares issued on exercise."""
    from ..models.entity import LegalEntity
    from . import document as docsvc

    entity = db.get(LegalEntity, grant.entity_id)
    sh = db.get(Stakeholder, grant.stakeholder_id)
    sc = db.get(SecurityClass, security_class_id)
    return docsvc.create_document(
        db,
        entity_id=grant.entity_id,
        template_key="share_certificate",
        data={
            "company": entity.name if entity else "",
            "certificate_no": cert_no,
            "holder": sh.name if sh else "",
            "quantity": f"{quantity:,}",
            "security_class": sc.name if sc else "",
            "par_value": str(sc.par_value) if sc else "0",
        },
        user_id=user_id,
        title=f"Share Certificate {cert_no} — {sh.name if sh else ''}",
        subject_type="esop_exercise",
        subject_id=ex.id,
    )


def generate_grant_letter(db: Session, grant: Grant, user_id: str):
    """The employee's grant letter (FR-D-2): the award terms and vesting
    schedule as a downloadable document, linked to the grant."""
    from ..models.entity import LegalEntity
    from . import document as docsvc

    entity = db.get(LegalEntity, grant.entity_id)
    sh = db.get(Stakeholder, grant.stakeholder_id)
    scheme = db.get(ESOPScheme, grant.scheme_id)
    label = {
        "option": "stock options",
        "rsu": "restricted stock units (RSUs)",
        "rsa": "restricted stock (issued upfront)",
    }.get(grant.grant_type, "stock options")
    full_vest = add_months(grant.grant_date, grant.total_months)
    return docsvc.create_document(
        db,
        entity_id=grant.entity_id,
        template_key="grant_letter",
        data={
            "company": entity.name if entity else "",
            "employee": sh.name if sh else "",
            "grant_date": grant.grant_date.isoformat(),
            "grant_type": label,
            "quantity": f"{grant.quantity:,}",
            "exercise_price": str(grant.exercise_price),
            "scheme": scheme.name if scheme else "",
            "cliff_months": grant.cliff_months,
            "total_months": grant.total_months,
            "full_vest_date": full_vest.isoformat(),
        },
        user_id=user_id,
        title=f"Grant Letter — {sh.name if sh else ''} ({grant.grant_date.isoformat()})",
        subject_type="esop_grant",
        subject_id=grant.id,
    )


def exercise(
    db: Session,
    grant: Grant,
    quantity: int,
    security_class_id: str,
    fmv_per_share: Decimal,
    as_of: datetime.date,
    cashless: bool = False,
    issued_by: str | None = None,
) -> ExerciseTransaction:
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    if grant.grant_type == "rsa":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "RSA shares are issued at grant — there is nothing to exercise or settle",
        )
    get_owned(db, SecurityClass, security_class_id, grant.entity_id, "security class")
    exercisable = vested_quantity(grant, as_of) - exercised_quantity(db, grant.id)
    if quantity > exercisable:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Only {exercisable} options are exercisable"
        )
    # If no FMV supplied, fall back to the entity's current valuation (FR-L).
    fmv = Decimal(fmv_per_share)
    if fmv <= 0:
        looked_up = valsvc.current_fmv(db, grant.entity_id, as_of)
        if looked_up is not None:
            fmv = looked_up

    strike = Decimal(grant.exercise_price)
    # gross `quantity` options are consumed from the grant; cashless withholds
    # shares worth the aggregate strike, so fewer net shares are issued.
    net_shares = quantity
    if cashless:
        if fmv <= strike:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cashless exercise needs FMV above the strike price"
            )
        net_shares = int(quantity * (fmv - strike) / fmv)

    issuance = IssuanceTransaction(
        entity_id=grant.entity_id,
        security_class_id=security_class_id,
        stakeholder_id=grant.stakeholder_id,
        quantity=net_shares,
        price_per_unit=Decimal("0") if cashless else strike,
        issue_date=as_of,
    )
    db.add(issuance)
    db.flush()
    perquisite = max(Decimal("0"), fmv - strike) * quantity
    ex = ExerciseTransaction(
        grant_id=grant.id,
        entity_id=grant.entity_id,
        quantity=quantity,
        fmv_per_share=fmv,
        exercise_price=strike,
        perquisite_value=perquisite,
        issuance_id=issuance.id,
        date=as_of,
        net_shares=net_shares,
        cashless=cashless,
    )
    db.add(ex)
    db.flush()
    # A board-approved exercise issues shares, so auto-generate a numbered share
    # certificate for them (FR-D-3), linked to this exercise.
    if issued_by is not None and net_shares > 0:
        cert_no = next_certificate_no(db, grant.entity_id)
        issuance.certificate_no = cert_no
        _issue_share_certificate(db, grant, ex, security_class_id, cert_no, net_shares, issued_by)
    db.commit()
    db.refresh(ex)
    return ex
