import datetime
import enum
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class SecurityKind(str, enum.Enum):
    EQUITY = "equity"
    CCPS = "ccps"
    CCD = "ccd"
    OPTION_POOL = "option_pool"
    SAFE = "safe"
    WARRANT = "warrant"


class StakeholderType(str, enum.Enum):
    FOUNDER = "founder"
    INVESTOR = "investor"
    EMPLOYEE = "employee"
    ENTITY = "entity"


class SecurityClass(Base, TimestampMixin):
    __tablename__ = "security_classes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[SecurityKind] = mapped_column(Enum(SecurityKind))
    par_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    # Liquidation-preference terms (preferred classes). pref_multiple 0 = common.
    pref_multiple: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    participating: Mapped[bool] = mapped_column(Boolean, default=False)
    seniority: Mapped[int] = mapped_column(Integer, default=0)
    # Anti-dilution protection (FR-C): none / broad_based / full_ratchet.
    # orig_issue_price is the initial conversion price the adjustment starts from.
    anti_dilution: Mapped[str] = mapped_column(String(16), default="none")
    orig_issue_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)


class Stakeholder(Base, TimestampMixin):
    __tablename__ = "stakeholders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[StakeholderType] = mapped_column(Enum(StakeholderType))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # FEMA/FC-GPR reporting: residency drives foreign-investment filing.
    residency: Mapped[str] = mapped_column(String(16), default="resident")  # resident | non_resident
    nationality: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)


class IssuanceTransaction(Base, TimestampMixin):
    """Append-only cap-table ledger event (ADR-2). The live cap table is a
    projection computed from these rows, never a mutable balance."""

    __tablename__ = "issuance_transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    issue_date: Mapped[datetime.date] = mapped_column(Date)
    certificate_no: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TransferTransaction(Base, TimestampMixin):
    """Secondary transfer of shares between stakeholders (SH-4, FR-C-7)."""

    __tablename__ = "transfer_transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    from_stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    to_stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    transfer_date: Mapped[datetime.date] = mapped_column(Date)
    stamp_duty: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))


class ConversionEvent(Base, TimestampMixin):
    """Conversion of one security class into another for a stakeholder
    (e.g. CCPS/SAFE -> equity, FR-C-3)."""

    __tablename__ = "conversion_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    from_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    to_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    from_quantity: Mapped[int] = mapped_column(Integer)
    to_quantity: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime.date] = mapped_column(Date)


class BuybackTransaction(Base, TimestampMixin):
    """Company buy-back / cancellation of shares (FR-C-7)."""

    __tablename__ = "buyback_transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    date: Mapped[datetime.date] = mapped_column(Date)


class CorporateActionType(str, enum.Enum):
    SPLIT = "split"
    BONUS = "bonus"


class RightsIssueStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class RightsIssue(Base, TimestampMixin):
    """A rights issue: existing holders of a class may subscribe to new shares
    pro-rata (ratio_num : ratio_den) at a set price; take-ups are issued on
    close (FR-C-7)."""

    __tablename__ = "rights_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    ratio_num: Mapped[int] = mapped_column(Integer)
    ratio_den: Mapped[int] = mapped_column(Integer, default=1)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    record_date: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[RightsIssueStatus] = mapped_column(
        Enum(RightsIssueStatus), default=RightsIssueStatus.OPEN
    )


class RightsSubscription(Base, TimestampMixin):
    __tablename__ = "rights_subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    rights_issue_id: Mapped[str] = mapped_column(ForeignKey("rights_issues.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    quantity: Mapped[int] = mapped_column(Integer)


class CorporateAction(Base, TimestampMixin):
    """A class-wide corporate action (FR-C-7): stock split or bonus issue.
    Expressed as numerator:denominator. Split 1:10 -> numerator=10,
    denominator=1 (each share becomes 10). Bonus 1:1 -> numerator=1,
    denominator=1 (one bonus share per share held)."""

    __tablename__ = "corporate_actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    type: Mapped[CorporateActionType] = mapped_column(Enum(CorporateActionType))
    numerator: Mapped[int] = mapped_column(Integer)
    denominator: Mapped[int] = mapped_column(Integer, default=1)
    date: Mapped[datetime.date] = mapped_column(Date)
