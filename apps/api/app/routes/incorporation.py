from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import TenantCtx, get_current_user, require_write, tenant_ctx
from ..models.entity import Incorporation, IncorporationStatus
from ..models.identity import User
from ..schemas import (
    IncorporationFiledIn,
    IncorporationIn,
    IncorporationOut,
    IncorporationRegisteredIn,
)
from ..services import incorporation as svc

router = APIRouter(prefix="/tenants/{tenant_id}/incorporations", tags=["incorporation"])


def _get(db: Session, ctx: TenantCtx, inc_id: str) -> Incorporation:
    inc = db.get(Incorporation, inc_id)
    if inc is None or inc.tenant_id != ctx.tenant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incorporation not found")
    return inc


@router.post("", response_model=IncorporationOut, status_code=201)
def create_incorporation(
    body: IncorporationIn, ctx: TenantCtx = Depends(tenant_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    data = body.model_dump(mode="json")
    svc.validate_intake(data)
    inc = Incorporation(
        tenant_id=ctx.tenant.id,
        name_options=data["name_options"],
        entity_type=body.entity_type,
        state=body.state,
        registered_office=body.registered_office,
        authorised_capital=body.authorised_capital,
        paid_up_capital=body.paid_up_capital,
        par_value=body.par_value,
        fy_end=body.fy_end,
        founders=data["founders"],
    )
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


@router.get("", response_model=list[IncorporationOut])
def list_incorporations(ctx: TenantCtx = Depends(tenant_ctx), db: Session = Depends(get_db)):
    return (
        db.query(Incorporation)
        .filter_by(tenant_id=ctx.tenant.id)
        .order_by(Incorporation.created_at.desc())
        .all()
    )


@router.post("/{inc_id}/prepare", response_model=IncorporationOut)
def prepare_filing_pack(
    inc_id: str,
    ctx: TenantCtx = Depends(tenant_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.prepare(db, _get(db, ctx, inc_id), user.id)


@router.post("/{inc_id}/filed", response_model=IncorporationOut)
def mark_filed(
    inc_id: str,
    body: IncorporationFiledIn,
    ctx: TenantCtx = Depends(tenant_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inc = _get(db, ctx, inc_id)
    if inc.status not in (IncorporationStatus.DOCS_GENERATED, IncorporationStatus.FILED):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Generate the filing pack first")
    inc.srn = body.srn
    inc.status = IncorporationStatus.FILED
    db.commit()
    db.refresh(inc)
    return inc


@router.post("/{inc_id}/registered")
def mark_registered(
    inc_id: str,
    body: IncorporationRegisteredIn,
    ctx: TenantCtx = Depends(tenant_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.register(db, _get(db, ctx, inc_id), body.cin, body.pan, body.incorporation_date)
