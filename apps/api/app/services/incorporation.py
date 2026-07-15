"""Incorporation wizard (FR-B): one intake → filing pack → CIN → live company.

prepare()   creates the pre-registration LegalEntity (no CIN/date), the equity
            class at par, founder stakeholders, and the SPICe+/eMoA/eAoA pack.
register()  records the CIN: allots the subscription shares at par, registers
            the first directors, and generates the annual compliance calendar —
            the moment the wizard hands over to the stage guide.
"""
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist as clock_today
from ..models.captable import IssuanceTransaction, SecurityClass, SecurityKind, Stakeholder, StakeholderType
from ..models.entity import Incorporation, IncorporationStatus, LegalEntity
from ..models.governance import DirectorDesignation, DirectorOfficer
from . import compliance as compliancesvc
from . import document as docsvc


def validate_intake(data: dict) -> None:
    founders = data["founders"]
    directors = [f for f in founders if f.get("is_director", True)]
    if len(directors) < 2:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "A private limited company needs at least 2 directors",
        )
    if Decimal(str(data["paid_up_capital"])) > Decimal(str(data["authorised_capital"])):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Paid-up capital cannot exceed authorised capital"
        )
    subscribed = sum(f["shares"] for f in founders) * Decimal(str(data["par_value"]))
    if subscribed > Decimal(str(data["authorised_capital"])):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Subscribed capital (INR {subscribed}) exceeds authorised capital",
        )


def prepare(db: Session, inc: Incorporation, user_id: str) -> Incorporation:
    if inc.status != IncorporationStatus.DRAFT:
        raise HTTPException(status.HTTP_409_CONFLICT, "Filing pack is already generated")
    name = inc.name_options[0]
    entity = LegalEntity(tenant_id=inc.tenant_id, name=name, type=inc.entity_type)
    db.add(entity)
    db.flush()

    db.add(SecurityClass(
        entity_id=entity.id, name="Equity", kind=SecurityKind.EQUITY, par_value=inc.par_value,
    ))
    for f in inc.founders:
        sh = Stakeholder(
            entity_id=entity.id, name=f["name"], type=StakeholderType.FOUNDER,
            email=f.get("email"),
        )
        db.add(sh)
        db.flush()
        # founder IP belongs to the company from day one (FR-B-1 / diligence)
        docsvc.create_document(
            db, entity_id=entity.id, template_key="ip_assignment",
            data={"company": name, "name": f["name"], "title": "Founder",
                  "date": clock_today().isoformat()},
            user_id=user_id, title=f"IP Assignment — {f['name']}",
            subject_type="stakeholder", subject_id=sh.id,
        )

    directors = ", ".join(f["name"] for f in inc.founders if f.get("is_director", True))
    common = {"company": name, "state": inc.state}
    docsvc.create_document(
        db, entity_id=entity.id, template_key="spice_plus",
        data={**common, "entity_type": inc.entity_type.value,
              "authorised_capital": str(inc.authorised_capital),
              "paid_up_capital": str(inc.paid_up_capital),
              "registered_office": inc.registered_office, "directors": directors},
        user_id=user_id, title=f"SPICe+ — {name}",
        subject_type="incorporation", subject_id=inc.id,
    )
    docsvc.create_document(
        db, entity_id=entity.id, template_key="emoa",
        data={**common, "objects": "To carry on the business set out in the SPICe+ application",
              "authorised_capital": str(inc.authorised_capital)},
        user_id=user_id, title=f"eMoA — {name}",
        subject_type="incorporation", subject_id=inc.id,
    )
    docsvc.create_document(
        db, entity_id=entity.id, template_key="eaoa",
        data={**common, "modifications": "None — Table F adopted as-is"},
        user_id=user_id, title=f"eAoA — {name}",
        subject_type="incorporation", subject_id=inc.id,
    )

    inc.company_name = name
    inc.entity_id = entity.id
    inc.status = IncorporationStatus.DOCS_GENERATED
    db.commit()
    db.refresh(inc)
    return inc


def register(
    db: Session,
    inc: Incorporation,
    cin: str,
    pan: str | None,
    incorporation_date: datetime.date,
) -> dict:
    if inc.status == IncorporationStatus.REGISTERED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Company is already registered")
    if inc.status == IncorporationStatus.DRAFT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Generate the filing pack first")
    entity = db.get(LegalEntity, inc.entity_id)
    entity.cin = cin
    entity.pan = pan
    entity.incorporation_date = incorporation_date

    equity = db.query(SecurityClass).filter_by(entity_id=entity.id, name="Equity").first()
    holders = {s.name: s for s in db.query(Stakeholder).filter_by(entity_id=entity.id)}
    shares_issued = 0
    for f in inc.founders:
        db.add(IssuanceTransaction(
            entity_id=entity.id, security_class_id=equity.id,
            stakeholder_id=holders[f["name"]].id, quantity=f["shares"],
            price_per_unit=inc.par_value, issue_date=incorporation_date,
        ))
        shares_issued += f["shares"]

    directors = 0
    for f in inc.founders:
        if not f.get("is_director", True):
            continue
        db.add(DirectorOfficer(
            entity_id=entity.id, name=f["name"], din=f.get("din"),
            designation=DirectorDesignation.DIRECTOR, appointed_on=incorporation_date,
        ))
        directors += 1

    fy_end = inc.fy_end or datetime.date(
        incorporation_date.year + (1 if incorporation_date.month > 3 else 0), 3, 31
    )
    obligations = compliancesvc.generate_for_fy(db, entity.id, fy_end)

    inc.cin = cin
    inc.status = IncorporationStatus.REGISTERED
    db.commit()
    return {
        "entity_id": entity.id,
        "cin": cin,
        "shares_issued": shares_issued,
        "directors_registered": directors,
        "obligations_created": obligations,
    }
