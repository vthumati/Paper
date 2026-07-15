"""Auth + tenant/entity scoping dependencies (RBAC, HLD §10).

Every entity-owned resource gets a `(Ctx, ctx_dep)` pair from `_entity_scoped`
below: the dependency 404s if the object is missing, resolves the caller's
role in the owning tenant (403 if not a member), and returns a small ctx
object exposing the resource under a stable attribute name plus `.role`.

Defence-in-depth note: in production these app-layer checks are paired with
PostgreSQL Row-Level Security (ADR-5). On SQLite (local dev) only the
app-layer checks apply.
"""
import inspect
from dataclasses import make_dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models.captable import RightsIssue
from .models.clm import Contract
from .models.compliance import ComplianceObligation
from .models.crm import ProspectInvestor
from .models.dataroom import DataRoom, DataRoomQuestion
from .models.document import Document, SignatureRequest
from .models.entity import LegalEntity
from .models.esop import ExerciseRequest, Grant
from .models.founders import FounderVesting
from .models.fund import Deal, Fund
from .models.governance import DirectorOfficer, Meeting, Resolution
from .models.identity import WRITE_ROLES, Membership, Role, Tenant, User
from .models.instruments import ConvertibleInstrument
from .models.managed import AdminSubscription
from .models.marketplace import ServiceEngagement
from .models.portal import SecondaryRequest
from .models.registers import Charge
from .models.round import Round
from .models.spv import SPV
from .models.startup import TaxBenefitApplication
from .models.team import TeamMember
from .models.workflow import WorkflowRun
from .security import decode_token

bearer = HTTPBearer(auto_error=True)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    sub = decode_token(creds.credentials)
    user = db.get(User, sub) if sub else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def _membership(db: Session, user: User, tenant_id: str) -> Membership:
    m = db.query(Membership).filter_by(user_id=user.id, tenant_id=tenant_id).first()
    if m is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not a member of this tenant")
    return m


def require_write(role: Role) -> None:
    if role not in WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Write access required")


def get_owned(db: Session, model, obj_id: str, entity_id: str, label: str):
    """Fetch a row referenced in a request body and require it to belong to
    the entity in scope — the shared guard against cross-entity id injection."""
    obj = db.get(model, obj_id)
    if obj is None or obj.entity_id != entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown {label} for this entity")
    return obj


PageCtx = make_dataclass("PageCtx", [("limit", int), ("offset", int)])


def page(limit: int = 100, offset: int = 0):
    """Shared pagination query params, clamped to sane bounds."""
    return PageCtx(limit=max(1, min(limit, 500)), offset=max(0, offset))


# --- the two root scopes (tenant / entity) are handwritten ---

def _direct_entity_id(obj, db):  # default owner resolver
    return obj.entity_id


TenantCtx = make_dataclass("TenantCtx", [("tenant", Tenant), ("role", Role)])
EntityCtx = make_dataclass("EntityCtx", [("entity", LegalEntity), ("role", Role)])


def tenant_ctx(
    tenant_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return TenantCtx(tenant, _membership(db, user, tenant_id).role)


def entity_ctx(
    entity_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entity = db.get(LegalEntity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    return EntityCtx(entity, _membership(db, user, entity.tenant_id).role)


# --- factory for every entity-owned resource ---

def _entity_scoped(attr: str, model, param: str, label: str, owner=_direct_entity_id):
    """Return (CtxClass, dependency) for a resource owned by a LegalEntity.

    `param` becomes the FastAPI path-parameter name: the inner function takes
    **kwargs and we substitute an explicit __signature__ so FastAPI binds the
    right path param and injects user/db as usual. `owner(obj, db)` resolves
    the owning entity id (override for indirectly-owned resources).
    """
    ctx_cls = make_dataclass(f"{model.__name__}Ctx", [(attr, object), ("role", Role)])

    def dep(**kwargs):
        db, user = kwargs["db"], kwargs["user"]
        obj = db.get(model, kwargs[param])
        if obj is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
        entity = db.get(LegalEntity, owner(obj, db))
        return ctx_cls(obj, _membership(db, user, entity.tenant_id).role)

    p = inspect.Parameter
    dep.__signature__ = inspect.Signature(
        [
            p(param, p.POSITIONAL_OR_KEYWORD, annotation=str),
            p("user", p.POSITIONAL_OR_KEYWORD, annotation=User, default=Depends(get_current_user)),
            p("db", p.POSITIONAL_OR_KEYWORD, annotation=Session, default=Depends(get_db)),
        ]
    )
    dep.__name__ = f"{param}_ctx"
    return ctx_cls, dep


RunCtx, run_ctx = _entity_scoped("run", WorkflowRun, "run_id", "Workflow run")
DocCtx, doc_ctx = _entity_scoped("document", Document, "document_id", "Document")
SignatureCtx, signature_ctx = _entity_scoped(
    "signature", SignatureRequest, "signature_id", "Signature request",
    owner=lambda sig, db: db.get(Document, sig.document_id).entity_id,
)
DataRoomCtx, dataroom_ctx = _entity_scoped("room", DataRoom, "dataroom_id", "Data room")
ObligationCtx, obligation_ctx = _entity_scoped(
    "obligation", ComplianceObligation, "obligation_id", "Obligation"
)
FundCtx, fund_ctx = _entity_scoped("fund", Fund, "fund_id", "Fund")
DealCtx, deal_ctx = _entity_scoped(
    "deal", Deal, "deal_id", "Deal",
    owner=lambda d, db: db.get(Fund, d.fund_id).entity_id,
)
GrantCtx, grant_ctx = _entity_scoped("grant", Grant, "grant_id", "Grant")
ExerciseRequestCtx, exercise_request_ctx = _entity_scoped(
    "request", ExerciseRequest, "request_id", "Exercise request"
)
EngagementCtx, engagement_ctx = _entity_scoped(
    "engagement", ServiceEngagement, "engagement_id", "Engagement"
)
SubscriptionCtx, subscription_ctx = _entity_scoped(
    "subscription", AdminSubscription, "subscription_id", "Subscription"
)
SPVCtx, spv_ctx = _entity_scoped("spv", SPV, "spv_id", "SPV")
RoundCtx, round_ctx = _entity_scoped("round", Round, "round_id", "Round")
MeetingCtx, meeting_ctx = _entity_scoped("meeting", Meeting, "meeting_id", "Meeting")
ResolutionCtx, resolution_ctx = _entity_scoped(
    "resolution", Resolution, "resolution_id", "Resolution"
)
TeamMemberCtx, team_member_ctx = _entity_scoped(
    "member", TeamMember, "member_id", "Team member"
)
ContractCtx, contract_ctx = _entity_scoped("contract", Contract, "contract_id", "Contract")
RightsIssueCtx, rights_issue_ctx = _entity_scoped(
    "rights_issue", RightsIssue, "rights_issue_id", "Rights issue"
)
DirectorCtx, director_ctx = _entity_scoped(
    "director", DirectorOfficer, "director_id", "Director"
)
ProspectCtx, prospect_ctx = _entity_scoped(
    "prospect", ProspectInvestor, "prospect_id", "Prospect"
)
BenefitCtx, benefit_ctx = _entity_scoped(
    "benefit", TaxBenefitApplication, "benefit_id", "Benefit application"
)
ChargeCtx, charge_ctx = _entity_scoped("charge", Charge, "charge_id", "Charge")
SecondaryCtx, secondary_ctx = _entity_scoped(
    "request", SecondaryRequest, "request_id", "Secondary request"
)
InstrumentCtx, instrument_ctx = _entity_scoped(
    "instrument", ConvertibleInstrument, "instrument_id", "Instrument"
)
FounderVestingCtx, founder_vesting_ctx = _entity_scoped(
    "vesting", FounderVesting, "vesting_id", "Founder vesting"
)
QuestionCtx, question_ctx = _entity_scoped(
    "question", DataRoomQuestion, "question_id", "Question",
    owner=lambda q, db: db.get(DataRoom, q.data_room_id).entity_id,
)
