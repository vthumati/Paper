"""Private-placement guardrail (Companies Act 2013, Sec 42 + Rule 14 PAS-4):
a company may not offer securities to more than 200 persons in a financial
year (QIBs and ESOP allottees are statutorily excluded — not separately
modelled, so every recorded offeree counts; conservative by design).

This is what makes family-and-friends rounds safe to run: F&F cheques are
many small offerees, and blowing the 200 cap converts the raise into a
deemed public offer. Offerees = distinct investor names across convertible
instruments (by issue date) and round commitments (by commitment date) in
the FY (April–March)."""
import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.instruments import ConvertibleInstrument
from ..models.round import Commitment, Round
from . import fy

MAX_OFFEREES_PER_FY = 200


def offerees_in_fy(db: Session, entity_id: str, as_of: datetime.date) -> set[str]:
    start = fy.fy_start(as_of)
    names = {
        i.investor_name
        for i in db.query(ConvertibleInstrument)
        .filter(ConvertibleInstrument.entity_id == entity_id)
        .filter(ConvertibleInstrument.issue_date >= start)
    }
    names |= {
        c.investor_name
        for c in db.query(Commitment)
        .join(Round, Commitment.round_id == Round.id)
        .filter(Round.entity_id == entity_id)
        .filter(Commitment.created_at >= datetime.datetime.combine(start, datetime.time.min))
    }
    return names


def check_offeree_limit(
    db: Session, entity_id: str, investor_name: str, as_of: datetime.date
) -> None:
    names = offerees_in_fy(db, entity_id, as_of)
    if investor_name in names:
        return  # an existing offeree this FY doesn't add to the count
    if len(names) >= MAX_OFFEREES_PER_FY:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Private-placement limit reached: securities already offered to "
            f"{len(names)} persons this financial year (Sec 42 caps this at "
            f"{MAX_OFFEREES_PER_FY}; exceeding it becomes a deemed public offer).",
        )
