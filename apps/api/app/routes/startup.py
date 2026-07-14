
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import BenefitCtx, EntityCtx, benefit_ctx, entity_ctx, require_write
from ..models.startup import (
    BenefitType,
    RecognitionStatus,
    StartupRecognition,
    TaxBenefitApplication,
)
from ..schemas import (
    BenefitIn,
    BenefitOut,
    BenefitStatusIn,
    RecognitionIn,
    RecognitionOut,
)
from ..services import startup as svc

router = APIRouter(tags=["startup-india"])


@router.get("/entities/{entity_id}/startup/eligibility")
def eligibility(ctx: EntityCtx = Depends(entity_ctx)):
    return svc.eligibility(ctx.entity, today_ist())


@router.put("/entities/{entity_id}/startup/recognition", response_model=RecognitionOut)
def upsert_recognition(
    body: RecognitionIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    rec = db.query(StartupRecognition).filter_by(entity_id=ctx.entity.id).first()
    if rec is None:
        rec = StartupRecognition(entity_id=ctx.entity.id)
        db.add(rec)
    rec.status = body.status
    rec.dpiit_number = body.dpiit_number
    rec.recognised_on = body.recognised_on
    rec.valid_until = body.valid_until
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/entities/{entity_id}/startup/recognition", response_model=RecognitionOut)
def get_recognition(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    rec = db.query(StartupRecognition).filter_by(entity_id=ctx.entity.id).first()
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No recognition on record")
    return rec


@router.post("/entities/{entity_id}/startup/benefits", response_model=BenefitOut, status_code=201)
def apply_benefit(
    body: BenefitIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    rec = db.query(StartupRecognition).filter_by(entity_id=ctx.entity.id).first()
    if rec is None or rec.status != RecognitionStatus.RECOGNISED:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "DPIIT recognition is required before applying for tax benefits.",
        )
    b = TaxBenefitApplication(entity_id=ctx.entity.id, type=body.type)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


@router.get("/entities/{entity_id}/startup/benefits", response_model=list[BenefitOut])
def list_benefits(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(TaxBenefitApplication).filter_by(entity_id=ctx.entity.id).all()


@router.post("/startup-benefits/{benefit_id}/status", response_model=BenefitOut)
def update_benefit(
    body: BenefitStatusIn, ctx: BenefitCtx = Depends(benefit_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.benefit.status = body.status
    if body.reference is not None:
        ctx.benefit.reference = body.reference
    db.commit()
    db.refresh(ctx.benefit)
    return ctx.benefit
