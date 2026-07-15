import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models.captable import (
    CorporateActionType,
    RightsIssueStatus,
    SecurityKind,
    StakeholderType,
)
from .models.clm import ContractStatus, CounterpartyKind
from .models.compliance import ObligationStatus
from .models.crm import PipelineStage
from .models.document import DocumentStatus, SignatureStatus
from .models.entity import EntityType
from .models.instruments import InstrumentStatus, InstrumentType
from .models.registers import RegistrationKind
from .models.fund import DealStage, DistributionKind, SebiCategory
from .models.identity import Role, TenantType
from .models.governance import (
    DirectorDesignation,
    MeetingStatus,
    MeetingType,
    ResolutionStatus,
    ResolutionType,
)
from .models.managed import AuditStatus, AuditType, SubscriptionTier
from .models.marketplace import EngagementStatus, ProviderCategory
from .models.round import CommitmentStatus, RoundInstrument, RoundStatus
from .models.startup import BenefitStatus, BenefitType, RecognitionStatus
from .models.tax import TaxRecordType
from .models.team import EmploymentType
from .models.valuation import ValuationMethod, ValuationStatus
from .models.workflow import RunStatus, StepStatus, StepType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# who an investment is from — shared by SAFEs/notes and round commitments
InvestorKind = Literal["friend_family", "angel", "institutional"]


# --- auth ---
class SignupIn(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORMModel):
    id: str
    email: str
    full_name: str


# --- tenants ---
class TenantIn(BaseModel):
    name: str
    type: TenantType = TenantType.COMPANY


class TenantOut(ORMModel):
    id: str
    name: str
    type: TenantType


class MembershipOut(ORMModel):
    tenant_id: str
    role: Role


# --- entities ---
class EntityIn(BaseModel):
    name: str
    type: EntityType = EntityType.PVT_LTD
    cin: str | None = None
    pan: str | None = None
    incorporation_date: datetime.date | None = None


class IncorporationFounder(BaseModel):
    name: str
    email: EmailStr | None = None
    din: str | None = None
    shares: int = Field(gt=0)
    is_director: bool = True


class IncorporationIn(BaseModel):
    name_options: list[str] = Field(min_length=1, max_length=3)
    entity_type: EntityType = EntityType.PVT_LTD
    state: str
    registered_office: str
    authorised_capital: Decimal = Field(gt=0)
    paid_up_capital: Decimal = Field(gt=0)
    par_value: Decimal = Field(default=Decimal("10"), gt=0)
    fy_end: datetime.date | None = None
    founders: list[IncorporationFounder] = Field(min_length=2)


class IncorporationFiledIn(BaseModel):
    srn: str


class IncorporationRegisteredIn(BaseModel):
    cin: str
    pan: str | None = None
    incorporation_date: datetime.date


class IncorporationOut(ORMModel):
    id: str
    tenant_id: str
    status: str
    name_options: list
    company_name: str | None
    entity_type: EntityType
    state: str
    registered_office: str
    authorised_capital: Decimal
    paid_up_capital: Decimal
    par_value: Decimal
    fy_end: datetime.date | None
    founders: list
    srn: str | None
    cin: str | None
    entity_id: str | None


class EntityOut(ORMModel):
    id: str
    tenant_id: str
    name: str
    type: EntityType
    cin: str | None
    pan: str | None
    incorporation_date: datetime.date | None
    stage: str


class StageIn(BaseModel):
    stage: Literal["inception", "preseed", "seed", "series", "ipo"]


# --- cap table ---
class SecurityClassIn(BaseModel):
    name: str
    kind: SecurityKind
    par_value: Decimal = Decimal("0")
    pref_multiple: Decimal = Decimal("0")
    participating: bool = False
    seniority: int = 0
    anti_dilution: Literal["none", "broad_based", "full_ratchet"] = "none"
    orig_issue_price: Decimal | None = None


class SecurityClassOut(ORMModel):
    id: str
    name: str
    kind: SecurityKind
    par_value: Decimal
    pref_multiple: Decimal
    participating: bool
    seniority: int
    anti_dilution: str
    orig_issue_price: Decimal | None


class StakeholderIn(BaseModel):
    name: str
    type: StakeholderType
    email: EmailStr | None = None


class StakeholderOut(ORMModel):
    id: str
    name: str
    type: StakeholderType
    email: str | None


class IssuanceIn(BaseModel):
    security_class_id: str
    stakeholder_id: str
    quantity: int
    price_per_unit: Decimal = Decimal("0")
    issue_date: datetime.date
    certificate_no: str | None = None


class IssuanceOut(ORMModel):
    id: str
    security_class_id: str
    stakeholder_id: str
    quantity: int
    price_per_unit: Decimal
    issue_date: datetime.date
    certificate_no: str | None


class TransferIn(BaseModel):
    security_class_id: str
    from_stakeholder_id: str
    to_stakeholder_id: str
    quantity: int
    price_per_unit: Decimal = Decimal("0")
    transfer_date: datetime.date | None = None


class TransferOut(ORMModel):
    id: str
    security_class_id: str
    from_stakeholder_id: str
    to_stakeholder_id: str
    quantity: int
    price_per_unit: Decimal
    transfer_date: datetime.date
    stamp_duty: Decimal


class ConversionIn(BaseModel):
    stakeholder_id: str
    from_class_id: str
    to_class_id: str
    from_quantity: int
    ratio: Decimal = Decimal("1")


class ConversionOut(ORMModel):
    id: str
    stakeholder_id: str
    from_class_id: str
    to_class_id: str
    from_quantity: int
    to_quantity: int
    date: datetime.date


class BuybackIn(BaseModel):
    security_class_id: str
    stakeholder_id: str
    quantity: int
    price_per_unit: Decimal = Decimal("0")


class CorporateActionIn(BaseModel):
    security_class_id: str
    type: CorporateActionType
    numerator: int
    denominator: int = 1


class CorporateActionOut(ORMModel):
    id: str
    security_class_id: str
    type: CorporateActionType
    numerator: int
    denominator: int
    date: datetime.date


class RightsIssueIn(BaseModel):
    security_class_id: str
    ratio_num: int
    ratio_den: int = 1
    price_per_unit: Decimal = Decimal("0")
    record_date: datetime.date | None = None


class RightsIssueOut(ORMModel):
    id: str
    security_class_id: str
    ratio_num: int
    ratio_den: int
    price_per_unit: Decimal
    record_date: datetime.date
    status: RightsIssueStatus


class RightsSubscriptionIn(BaseModel):
    stakeholder_id: str
    quantity: int


# --- workflows ---
class StepDefOut(BaseModel):
    key: str
    title: str
    type: StepType
    assignee_role: str | None = None


class WorkflowDefinitionOut(BaseModel):
    key: str
    version: int
    title: str
    steps: list[StepDefOut]


class WorkflowStartIn(BaseModel):
    definition_key: str
    context: dict = {}


class StepCompleteIn(BaseModel):
    output: dict = {}


class StepOut(ORMModel):
    step_key: str
    title: str
    type: StepType
    order_index: int
    status: StepStatus
    assignee_role: str | None
    output: dict | None


class WorkflowRunOut(ORMModel):
    id: str
    entity_id: str
    definition_key: str
    definition_version: int
    title: str
    status: RunStatus
    context: dict
    steps: list[StepOut]


# --- documents ---
class DocumentTemplateOut(BaseModel):
    key: str
    name: str
    doc_type: str
    body: str  # $placeholder template text — drives the client-side live preview


class DocumentCreateIn(BaseModel):
    template_key: str
    title: str | None = None
    data: dict = {}
    subject_type: str | None = None
    subject_id: str | None = None


class RegenerateIn(BaseModel):
    data: dict = {}
    title: str | None = None


class DocumentOut(BaseModel):
    id: str
    entity_id: str
    type: str
    title: str
    status: DocumentStatus
    template_key: str | None
    current_version: int
    subject_type: str | None
    subject_id: str | None
    content: str | None


class DocumentVersionOut(ORMModel):
    version: int
    content: str
    created_by: str


class SignatureCreateIn(BaseModel):
    signatories: list[dict] = []
    provider: str = "aadhaar_esign"


class SignatureOut(ORMModel):
    id: str
    document_id: str
    provider: str
    status: SignatureStatus
    signatories: list
    completed_at: datetime.datetime | None


# --- data room ---
class DataRoomIn(BaseModel):
    name: str
    scope: str = "diligence"


class DataRoomItemIn(BaseModel):
    document_id: str
    folder: str = "General"
    order_index: int = 0


class GrantIn(BaseModel):
    email: EmailStr
    permissions: str = "view"
    expiry: datetime.date | None = None


class DataRoomItemOut(BaseModel):
    id: str
    document_id: str
    document_title: str | None
    folder: str
    order_index: int


class GrantOut(BaseModel):
    id: str
    email: str
    permissions: str
    expiry: datetime.date | None


class DataRoomOut(BaseModel):
    id: str
    entity_id: str
    name: str
    scope: str
    items: list[DataRoomItemOut]
    grants: list[GrantOut]


class EngagementOut(BaseModel):
    document_id: str | None
    actor: str
    views: int


# --- compliance ---
class ComplianceGenerateIn(BaseModel):
    financial_year_end: datetime.date


class ObligationStatusIn(BaseModel):
    status: ObligationStatus
    srn: str | None = None
    assignee: str | None = None


class ObligationOut(BaseModel):
    id: str
    form_code: str
    title: str
    category: str
    period_label: str
    due_date: datetime.date
    status: ObligationStatus
    assignee: str | None
    srn: str | None
    overdue: bool


# --- fund administration (AIF) ---
class FundIn(BaseModel):
    sebi_category: SebiCategory
    structure: str = "trust"
    currency: str = "INR"
    target_corpus: Decimal = Field(default=Decimal("0"), ge=0)
    # carry strictly below 100% — the catch-up formula divides by (1 − carry)
    carry_pct: Decimal = Field(default=Decimal("0.20"), ge=0, lt=1)
    hurdle_pct: Decimal = Field(default=Decimal("0.08"), ge=0, le=1)
    mgmt_fee_pct: Decimal = Field(default=Decimal("0.02"), ge=0, le=1)
    fee_basis: Literal["committed", "drawn"] = "committed"


class FundOut(ORMModel):
    id: str
    entity_id: str
    sebi_category: SebiCategory
    structure: str
    currency: str
    target_corpus: Decimal
    carry_pct: Decimal
    hurdle_pct: Decimal
    mgmt_fee_pct: Decimal
    fee_basis: str


class LPIn(BaseModel):
    name: str
    email: EmailStr | None = None
    commitment: Decimal = Field(default=Decimal("0"), ge=0)


class LPOut(ORMModel):
    id: str
    name: str
    email: str | None
    commitment: Decimal


class CapitalCallIn(BaseModel):
    pct: Decimal
    purpose: str | None = None
    due_date: datetime.date | None = None


class DrawdownNoticeOut(ORMModel):
    id: str
    lp_id: str
    amount: Decimal
    paid: bool


class CapitalCallOut(ORMModel):
    id: str
    call_no: int
    pct: Decimal
    purpose: str | None
    due_date: datetime.date | None
    notices: list[DrawdownNoticeOut] = []


class DistributionIn(BaseModel):
    gross_amount: Decimal
    kind: DistributionKind = DistributionKind.PROFIT
    date: datetime.date | None = None


class DistributionOut(ORMModel):
    id: str
    dist_no: int
    gross_amount: Decimal
    kind: DistributionKind
    carry_amount: Decimal
    roc_amount: Decimal
    pref_amount: Decimal
    catchup_amount: Decimal
    date: datetime.date | None


class PortfolioIn(BaseModel):
    company_name: str
    instrument: str = "equity"
    amount: Decimal = Decimal("0")
    ownership_pct: Decimal = Decimal("0")
    invested_on: datetime.date | None = None


class PortfolioOut(ORMModel):
    id: str
    company_name: str
    instrument: str
    amount: Decimal
    ownership_pct: Decimal
    invested_on: datetime.date | None
    current_value: Decimal | None
    marked_on: datetime.date | None


class PortfolioMarkIn(BaseModel):
    current_value: Decimal = Field(ge=0)
    marked_on: datetime.date | None = None


class DealIn(BaseModel):
    company_name: str
    sector: str | None = None
    stage: DealStage = DealStage.SOURCED
    amount: Decimal = Field(default=Decimal("0"), ge=0)
    notes: str | None = None


class DealStageIn(BaseModel):
    stage: DealStage


class DealInvestIn(BaseModel):
    ownership_pct: Decimal = Decimal("0")
    invested_on: datetime.date | None = None


class ScenarioIn(BaseModel):
    new_money: Decimal = Field(gt=0)
    pre_money: Decimal | None = Field(default=None, gt=0)
    price_per_share: Decimal | None = Field(default=None, gt=0)
    pool_top_up: int = Field(default=0, ge=0)


class ExerciseRequestIn(BaseModel):
    grant_id: str
    quantity: int = Field(gt=0)
    cashless: bool = False


class ExerciseRequestDecideIn(BaseModel):
    approve: bool
    security_class_id: str | None = None


class CapTableImportIn(BaseModel):
    csv: str = Field(max_length=2_000_000)  # ~2 MB is far beyond any real cap table
    apply: bool = False


class ConsentDecisionIn(BaseModel):
    approve: bool


class SecondaryRequestIn(BaseModel):
    entity_id: str
    security_class_id: str
    quantity: int = Field(gt=0)
    price_per_unit: Decimal = Field(gt=0)


class SecondaryDecideIn(BaseModel):
    approve: bool
    buyer_stakeholder_id: str | None = None


class DealOut(ORMModel):
    id: str
    fund_id: str
    company_name: str
    sector: str | None
    stage: DealStage
    amount: Decimal
    notes: str | None
    investment_id: str | None


# --- ESOP ---
class ESOPSchemeIn(BaseModel):
    name: str
    pool_size: int


class ESOPSchemeOut(ORMModel):
    id: str
    name: str
    pool_size: int


class EsopGrantIn(BaseModel):
    scheme_id: str
    stakeholder_id: str
    quantity: int
    exercise_price: Decimal = Decimal("0")
    grant_date: datetime.date
    cliff_months: int = 12
    total_months: int = 48
    grant_type: Literal["option", "rsu", "rsa"] = "option"
    security_class_id: str | None = None  # required for RSA (issued upfront)
    fmv: Decimal = Decimal("0")  # RSA perquisite basis; falls back to current FMV


class EsopGrantOut(BaseModel):
    id: str
    scheme_id: str
    stakeholder_id: str
    stakeholder_name: str | None
    grant_type: str
    quantity: int
    exercise_price: Decimal
    grant_date: datetime.date
    cliff_months: int
    total_months: int
    vested: int
    exercised: int
    exercisable: int
    unvested: int


class ExerciseIn(BaseModel):
    quantity: int
    security_class_id: str
    fmv_per_share: Decimal = Decimal("0")
    cashless: bool = False


class ExerciseOut(ORMModel):
    id: str
    grant_id: str
    quantity: int
    fmv_per_share: Decimal
    exercise_price: Decimal
    perquisite_value: Decimal
    issuance_id: str | None
    date: datetime.date
    net_shares: int | None
    cashless: bool


# --- founder reverse-vesting ---
class FounderVestingIn(BaseModel):
    stakeholder_id: str
    security_class_id: str
    total_shares: int
    cliff_months: int = 12
    total_months: int = 48
    start_date: datetime.date


class FounderVestingOut(BaseModel):
    id: str
    stakeholder_id: str
    security_class_id: str
    total_shares: int
    vested: int
    unvested: int
    cliff_months: int
    total_months: int
    start_date: datetime.date
    repurchased: bool


# --- data room Q&A ---
class QuestionIn(BaseModel):
    question: str


class AnswerIn(BaseModel):
    answer: str


class QuestionOut(ORMModel):
    id: str
    asker: str
    question: str
    answer: str | None
    answered_by: str | None


# --- valuations ---
class ValuationIn(BaseModel):
    method: ValuationMethod
    fmv_per_share: Decimal
    valuation_date: datetime.date
    valuer_name: str | None = None
    valid_until: datetime.date | None = None
    basis: str | None = None
    status: ValuationStatus = ValuationStatus.FINAL


class ValuationOut(ORMModel):
    id: str
    method: ValuationMethod
    fmv_per_share: Decimal
    valuation_date: datetime.date
    valuer_name: str | None
    valid_until: datetime.date | None
    basis: str | None
    status: ValuationStatus


class CurrentFmvOut(BaseModel):
    fmv_per_share: Decimal | None
    valuation_id: str | None
    valuation_date: datetime.date | None


# --- self-serve indicative valuation (FR-L-2) ---
class ScorecardIn(BaseModel):
    base_valuation: Decimal = Field(gt=0)  # benchmark pre-money for the region/stage
    # factor scores, 100 = at benchmark, >100 above, <100 below (see registry)
    scores: dict[str, Decimal] = Field(default_factory=dict)


class VCMethodIn(BaseModel):
    exit_value: Decimal = Field(gt=0)
    target_multiple: Decimal = Field(gt=0)
    planned_raise: Decimal = Field(default=Decimal("0"), ge=0)


class DCFProjectionRow(BaseModel):
    revenue: Decimal
    expenses: Decimal


class DCFIn(BaseModel):
    projections: list[DCFProjectionRow] = Field(min_length=1, max_length=15)
    discount_rate_pct: Decimal = Field(gt=0, le=100)
    terminal_growth_pct: Decimal = Field(default=Decimal("0"), ge=0, lt=100)


class ValuationEstimateIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    weights: dict[str, Decimal]  # method -> weight (normalised server-side)
    scorecard: ScorecardIn | None = None
    vc_method: VCMethodIn | None = None
    dcf: DCFIn | None = None
    save: bool = True


class ValuationEstimateOut(ORMModel):
    id: str
    label: str
    inputs: dict
    results: dict
    created_at: datetime.datetime


class SmartfillOut(BaseModel):
    base_annual_revenue: Decimal
    base_annual_expenses: Decimal
    assumed_growth_pct: Decimal
    months_of_data: int
    projections: list[dict]


# --- services marketplace ---
class ProviderIn(BaseModel):
    name: str
    category: ProviderCategory
    firm: str | None = None
    email: EmailStr | None = None
    profile: str | None = None


class ProviderOut(ORMModel):
    id: str
    name: str
    category: ProviderCategory
    firm: str | None
    email: str | None
    profile: str | None
    active: bool
    verified: bool


class ServiceEngagementIn(BaseModel):
    provider_id: str
    scope: str | None = None


class ServiceEngagementStatusIn(BaseModel):
    status: EngagementStatus
    deliverable_doc_id: str | None = None


class ServiceEngagementOut(BaseModel):
    id: str
    entity_id: str
    provider_id: str
    provider_name: str | None
    provider_category: str | None
    scope: str | None
    status: EngagementStatus
    deliverable_doc_id: str | None


# --- managed administration ---
class AdminSubscriptionIn(BaseModel):
    tier: SubscriptionTier
    provider_id: str | None = None


class TouchpointIn(BaseModel):
    date: datetime.date
    attendee: str | None = None
    summary: str | None = None


class TouchpointOut(ORMModel):
    id: str
    date: datetime.date
    attendee: str | None
    summary: str | None


class AuditEngagementIn(BaseModel):
    type: AuditType
    period_label: str


class AuditStatusIn(BaseModel):
    status: AuditStatus
    findings: str | None = None


class AuditEngagementOut(ORMModel):
    id: str
    type: AuditType
    period_label: str
    status: AuditStatus
    findings: str | None


class AdminSubscriptionOut(ORMModel):
    id: str
    entity_id: str
    tier: SubscriptionTier
    status: str
    provider_id: str | None
    touchpoints: list[TouchpointOut] = []
    audits: list[AuditEngagementOut] = []


# --- SPV ---
class SPVIn(BaseModel):
    sponsor: str
    target_company: str
    structure: str = "llp"
    portco_entity_id: str | None = None


class SPVOut(ORMModel):
    id: str
    entity_id: str
    sponsor: str
    target_company: str
    structure: str
    portco_entity_id: str | None
    carry_pct: Decimal
    min_ticket: Decimal


class SPVTermsIn(BaseModel):
    carry_pct: Decimal = Field(ge=0, lt=1)
    min_ticket: Decimal = Field(ge=0)


class CoInvestorIn(BaseModel):
    name: str
    email: EmailStr | None = None
    commitment: Decimal = Field(default=Decimal("0"), ge=0)


class CoInvestorOut(ORMModel):
    id: str
    name: str
    email: str | None
    commitment: Decimal
    contributed: Decimal
    paid: bool
    status: str


class SPVCommitIn(BaseModel):
    co_investor_id: str
    amount: Decimal = Field(gt=0)


# --- fundraising funnel (public opt-in link) ---
class FunnelLinkIn(BaseModel):
    data_room_id: str | None = None


class FunnelLinkOut(ORMModel):
    id: str
    entity_id: str
    round_id: str
    data_room_id: str | None
    token: str
    active: bool


class FunnelInterestIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    firm: str | None = Field(default=None, max_length=255)
    check_size: Decimal | None = Field(default=None, gt=0)
    notes: str | None = Field(default=None, max_length=2000)


class CharterAmendmentIn(BaseModel):
    kind: Literal["moa", "aoa"]
    description: str = Field(min_length=1, max_length=2000)


class TermSheetScanIn(BaseModel):
    text: str = Field(min_length=20, max_length=200_000)


class TeamOffboardIn(BaseModel):
    left_on: datetime.date | None = None


class SPVInvestIn(BaseModel):
    security_class_id: str
    quantity: int
    price_per_unit: Decimal = Decimal("0")


class SPVInvestmentOut(ORMModel):
    id: str
    portco_entity_id: str
    security_class_id: str
    stakeholder_id: str
    quantity: int
    price_per_unit: Decimal
    issuance_id: str | None
    date: datetime.date


# --- fundraising round ---
class RoundIn(BaseModel):
    name: str
    instrument: RoundInstrument = RoundInstrument.EQUITY
    pre_money: Decimal = Decimal("0")
    target_amount: Decimal = Decimal("0")
    price_per_share: Decimal = Decimal("0")
    security_class_id: str | None = None
    valuation_id: str | None = None


class RoundOut(ORMModel):
    id: str
    entity_id: str
    name: str
    instrument: RoundInstrument
    pre_money: Decimal
    target_amount: Decimal
    price_per_share: Decimal
    security_class_id: str | None
    valuation_id: str | None
    status: RoundStatus


class RoundCommitmentIn(BaseModel):
    investor_name: str
    investor_email: EmailStr | None = None
    investor_kind: InvestorKind = "institutional"
    amount: Decimal = Field(gt=0)
    shares: int | None = Field(default=None, gt=0)
    is_foreign: bool = False


class RoundCommitmentStatusIn(BaseModel):
    status: CommitmentStatus
    shares: int | None = None


class RoundCommitmentOut(ORMModel):
    id: str
    investor_name: str
    investor_email: str | None
    investor_kind: str
    amount: Decimal
    shares: int | None
    is_foreign: bool
    status: CommitmentStatus
    stakeholder_id: str | None


# --- governance ---
class MeetingIn(BaseModel):
    type: MeetingType
    title: str
    date: datetime.date
    location: str | None = None
    quorum: int | None = None


class MinutesIn(BaseModel):
    minutes: str
    status: MeetingStatus = MeetingStatus.HELD


class ResolutionOut(ORMModel):
    id: str
    meeting_id: str | None
    type: ResolutionType
    title: str
    text: str
    status: ResolutionStatus
    passed_date: datetime.date | None
    document_id: str | None


class AgendaItemIn(BaseModel):
    title: str
    order_index: int = 0


class AgendaItemOut(ORMModel):
    id: str
    order_index: int
    title: str


class MeetingOut(ORMModel):
    id: str
    entity_id: str
    type: MeetingType
    title: str
    date: datetime.date
    location: str | None
    quorum: int | None
    status: MeetingStatus
    minutes: str | None
    notice_document_id: str | None = None
    resolutions: list[ResolutionOut] = []
    agenda_items: list[AgendaItemOut] = []


class DirectorIn(BaseModel):
    name: str
    din: str | None = None
    designation: DirectorDesignation = DirectorDesignation.DIRECTOR
    appointed_on: datetime.date


class DirectorResignIn(BaseModel):
    resigned_on: datetime.date


class DirectorOut(ORMModel):
    id: str
    name: str
    din: str | None
    designation: DirectorDesignation
    appointed_on: datetime.date
    resigned_on: datetime.date | None
    status: str


class ResolutionIn(BaseModel):
    meeting_id: str | None = None
    type: ResolutionType
    title: str
    text: str


class ResolutionStatusIn(BaseModel):
    status: ResolutionStatus


# --- activity: audit log + notifications ---
class AuditEntryOut(ORMModel):
    id: str
    actor_email: str | None
    method: str
    path: str
    status_code: int
    created_at: datetime.datetime


class NotificationOut(ORMModel):
    id: str
    type: str
    title: str
    body: str | None
    read: bool
    created_at: datetime.datetime


# --- workspace: file cabinet + tax records ---
class FileOut(BaseModel):
    id: str
    title: str
    type: str
    status: str
    current_version: int
    subject_type: str | None
    created_at: datetime.datetime


class TaxRecordIn(BaseModel):
    type: TaxRecordType
    period_label: str
    reference: str | None = None
    amount: Decimal | None = None
    filed_on: datetime.date | None = None
    document_id: str | None = None


class TaxRecordOut(ORMModel):
    id: str
    type: TaxRecordType
    period_label: str
    reference: str | None
    amount: Decimal | None
    filed_on: datetime.date | None
    document_id: str | None


# --- team & HR-legal ---
class TeamMemberIn(BaseModel):
    name: str
    email: EmailStr | None = None
    title: str | None = None
    employment_type: EmploymentType = EmploymentType.EMPLOYEE
    joined_on: datetime.date | None = None


class TeamMemberOut(ORMModel):
    id: str
    name: str
    email: str | None
    title: str | None
    employment_type: EmploymentType
    joined_on: datetime.date | None
    left_on: datetime.date | None
    stakeholder_id: str | None
    status: str


class TeamMemberStatusIn(BaseModel):
    status: str
    left_on: datetime.date | None = None


class TeamDocIn(BaseModel):
    template_key: str


# --- commercial contracts (CLM) ---
class CounterpartyIn(BaseModel):
    name: str
    kind: CounterpartyKind
    contact_name: str | None = None
    contact_email: EmailStr | None = None


class CounterpartyOut(ORMModel):
    id: str
    name: str
    kind: CounterpartyKind
    contact_name: str | None
    contact_email: str | None


class ContractIn(BaseModel):
    counterparty_id: str
    title: str
    type: str = "msa"
    value: Decimal | None = None
    currency: str = "INR"
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    renewal_date: datetime.date | None = None
    auto_renew: bool = False


class ContractStatusIn(BaseModel):
    status: ContractStatus


class ContractDocIn(BaseModel):
    template_key: str = "msa"


# --- advisor (external professional) access ---
class AdvisorAccessIn(BaseModel):
    email: EmailStr
    firm_name: str = Field(min_length=1, max_length=255)
    # advisors get read-only (viewer) or acting (member) access; never owner/admin
    role: Literal["viewer", "member"] = "viewer"


class AdvisorAccessOut(ORMModel):
    id: str
    entity_id: str
    email: str
    firm_name: str
    role: Role


class AdvisorEntityOut(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    tenant_name: str
    firm_name: str
    role: Role


# --- investor portal ---
class InvestorAccessIn(BaseModel):
    email: EmailStr
    stakeholder_id: str | None = None


class InvestorAccessOut(ORMModel):
    id: str
    email: str
    stakeholder_id: str | None
    status: str


class InvestorUpdateIn(BaseModel):
    title: str
    body: str


class InvestorUpdateOut(ORMModel):
    id: str
    title: str
    body: str
    created_at: datetime.datetime


# --- investor CRM / fundraising pipeline ---
class ProspectIn(BaseModel):
    name: str
    firm: str | None = None
    email: EmailStr | None = None
    stage: PipelineStage = PipelineStage.CONTACTED
    check_size: Decimal | None = None
    notes: str | None = None
    round_id: str | None = None
    last_contact: datetime.date | None = None


class ProspectStageIn(BaseModel):
    stage: PipelineStage
    notes: str | None = None


class ProspectOut(ORMModel):
    id: str
    name: str
    firm: str | None
    email: str | None
    stage: PipelineStage
    check_size: Decimal | None
    notes: str | None
    round_id: str | None
    last_contact: datetime.date | None
    commitment_id: str | None


# --- DPIIT / Startup India ---
class RecognitionIn(BaseModel):
    status: RecognitionStatus = RecognitionStatus.APPLIED
    dpiit_number: str | None = None
    recognised_on: datetime.date | None = None
    valid_until: datetime.date | None = None


class RecognitionOut(ORMModel):
    id: str
    entity_id: str
    status: RecognitionStatus
    dpiit_number: str | None
    recognised_on: datetime.date | None
    valid_until: datetime.date | None


class BenefitIn(BaseModel):
    type: BenefitType


class BenefitStatusIn(BaseModel):
    status: BenefitStatus
    reference: str | None = None


class BenefitOut(ORMModel):
    id: str
    type: BenefitType
    status: BenefitStatus
    reference: str | None


# --- finance (runway / burn) ---
class SnapshotIn(BaseModel):
    period: datetime.date
    cash_balance: Decimal = Decimal("0")
    monthly_burn: Decimal = Decimal("0")
    revenue: Decimal = Decimal("0")


# --- statutory registers ---
class SBOIn(BaseModel):
    name: str
    pan: str | None = None
    percentage: Decimal = Decimal("0")
    nature: str | None = None


class SBOOut(ORMModel):
    id: str
    name: str
    pan: str | None
    percentage: Decimal
    nature: str | None


class ChargeIn(BaseModel):
    holder: str
    amount: Decimal = Decimal("0")
    charge_type: str = "hypothecation"
    created_on: datetime.date


class ChargeOut(ORMModel):
    id: str
    holder: str
    amount: Decimal
    charge_type: str
    created_on: datetime.date
    satisfied: bool


class RegistrationIn(BaseModel):
    kind: RegistrationKind
    state: str
    number: str | None = None
    status: str = "active"


class RegistrationOut(ORMModel):
    id: str
    kind: RegistrationKind
    state: str
    number: str | None
    status: str


# --- convertible instruments (SAFE / note) ---
class InstrumentIn(BaseModel):
    investor_name: str
    investor_email: EmailStr | None = None
    investor_kind: InvestorKind = "angel"
    instrument_type: InstrumentType = InstrumentType.SAFE
    principal: Decimal = Field(gt=0)
    valuation_cap: Decimal | None = Field(default=None, gt=0)
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    mfn: bool = False
    interest_pct: Decimal = Field(default=Decimal("0"), ge=0, le=1)
    issue_date: datetime.date


class InstrumentOut(ORMModel):
    id: str
    investor_name: str
    investor_kind: str
    instrument_type: InstrumentType
    principal: Decimal
    valuation_cap: Decimal | None
    discount_pct: Decimal
    interest_pct: Decimal
    issue_date: datetime.date
    status: InstrumentStatus
    converted_shares: int | None


class InstrumentConvertIn(BaseModel):
    round_price_per_share: Decimal
    security_class_id: str
    conversion_date: datetime.date | None = None


# --- demat / ISIN ---
class DematIn(BaseModel):
    security_class_id: str
    isin: str | None = None
    depository: str = "NSDL"
    status: str = "pending"


class DematOut(ORMModel):
    id: str
    security_class_id: str
    isin: str | None
    depository: str
    status: str


class ContractOut(BaseModel):
    id: str
    counterparty_id: str
    counterparty_name: str | None
    counterparty_kind: str | None
    title: str
    type: str
    value: str | None
    currency: str
    start_date: datetime.date | None
    end_date: datetime.date | None
    renewal_date: datetime.date | None
    auto_renew: bool
    status: ContractStatus
    document_id: str | None
    days_to_renewal: int | None
    renewal_overdue: bool
