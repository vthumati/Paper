import enum
from decimal import Decimal

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class RoundInstrument(str, enum.Enum):
    EQUITY = "equity"
    CCPS = "ccps"
    SAFE = "safe"
    CONVERTIBLE_NOTE = "convertible_note"


class RoundStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    CLOSED = "closed"


class CommitmentStatus(str, enum.Enum):
    SOFT = "soft"
    SIGNED = "signed"
    FUNDED = "funded"


class Round(Base, TimestampMixin):
    """A priced fundraising round (FR-E). On close, funded commitments are
    issued into the cap-table ledger and a FEMA filing is flagged if any
    investor is non-resident."""

    __tablename__ = "rounds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    instrument: Mapped[RoundInstrument] = mapped_column(
        Enum(RoundInstrument), default=RoundInstrument.EQUITY
    )
    pre_money: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    price_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    security_class_id: Mapped[str | None] = mapped_column(
        ForeignKey("security_classes.id"), nullable=True
    )
    valuation_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[RoundStatus] = mapped_column(Enum(RoundStatus), default=RoundStatus.DRAFT)
    created_by: Mapped[str] = mapped_column(String(32))

    commitments: Mapped[list["Commitment"]] = relationship(
        back_populates="round", cascade="all, delete-orphan"
    )


class Commitment(Base, TimestampMixin):
    __tablename__ = "round_commitments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id"), index=True)
    investor_name: Mapped[str] = mapped_column(String(255))
    investor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # friend_family / angel / institutional — F&F cheques are first-class (FR-E)
    investor_kind: Mapped[str] = mapped_column(String(16), default="institutional")
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_foreign: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(CommitmentStatus), default=CommitmentStatus.SOFT
    )
    stakeholder_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    round: Mapped[Round] = relationship(back_populates="commitments")
