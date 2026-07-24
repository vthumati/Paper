import datetime
import enum
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class ESOPScheme(Base, TimestampMixin):
    """An option pool / incentive scheme for an entity (FR-D-1)."""

    __tablename__ = "esop_schemes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    pool_size: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(32))

    grants: Mapped[list["Grant"]] = relationship(back_populates="scheme", cascade="all, delete-orphan")


class Grant(Base, TimestampMixin):
    """An equity-incentive grant to a stakeholder with a time-based vesting
    schedule (cliff then monthly to total). FR-D-2.

    `grant_type` distinguishes the three award shapes that share this vesting
    model but settle and tax differently:
      - option: vest -> exercise (pay strike); perquisite (FMV-strike) at exercise
      - rsu:    vest -> settle (no strike); perquisite = FMV at settlement
      - rsa:    shares issued upfront at grant; perquisite (FMV-price) at grant;
                the unvested portion is subject to repurchase on early exit
    """

    __tablename__ = "esop_grants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("esop_schemes.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    grant_type: Mapped[str] = mapped_column(String(8), default="option")
    quantity: Mapped[int] = mapped_column(Integer)
    exercise_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    grant_date: Mapped[datetime.date] = mapped_column(Date)
    cliff_months: Mapped[int] = mapped_column(Integer, default=12)
    total_months: Mapped[int] = mapped_column(Integer, default=48)

    scheme: Mapped[ESOPScheme] = relationship(back_populates="grants")


class ExerciseWindow(Base, TimestampMixin):
    """A defined period during which vested options may be exercised (FR-D-4).
    Opt-in: when an entity has any windows, exercise requests are gated to an
    open one; with no windows defined, exercise stays unrestricted."""

    __tablename__ = "exercise_windows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    opens_on: Mapped[datetime.date] = mapped_column(Date)
    closes_on: Mapped[datetime.date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(String(32))


class ExerciseRequestStatus(str, enum.Enum):
    OPEN = "open"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExerciseRequest(Base, TimestampMixin):
    """An employee's self-serve exercise request from the portal (FR-D/K):
    validated against vested options, decided by the company — approval runs
    the real exercise into the cap-table ledger."""

    __tablename__ = "exercise_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    grant_id: Mapped[str] = mapped_column(ForeignKey("esop_grants.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    cashless: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[ExerciseRequestStatus] = mapped_column(
        Enum(ExerciseRequestStatus), default=ExerciseRequestStatus.OPEN
    )
    exercise_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class ForfeitureEvent(Base, TimestampMixin):
    """An auditable option-forfeiture / true-up event (FR-D/R-4): when an
    employee leaves, each affected grant is frozen at what had vested and the
    unvested balance lapses back to the scheme pool. One row per affected grant
    records how many options lapsed and how many vested options were retained."""

    __tablename__ = "esop_forfeitures"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    grant_id: Mapped[str] = mapped_column(ForeignKey("esop_grants.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    lapsed_quantity: Mapped[int] = mapped_column(Integer)
    vested_retained: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32), default="offboarding")
    date: Mapped[datetime.date] = mapped_column(Date)


class ExerciseTransaction(Base, TimestampMixin):
    """An exercise event. Creates a cap-table IssuanceTransaction and records
    the perquisite value (FMV − exercise price) for tax (FR-D-3)."""

    __tablename__ = "esop_exercises"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    grant_id: Mapped[str] = mapped_column(ForeignKey("esop_grants.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    fmv_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    exercise_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    perquisite_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    issuance_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    # cashless exercise: `quantity` is gross options exercised; `net_shares` is
    # the shares actually issued after withholding to cover the strike.
    net_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cashless: Mapped[bool] = mapped_column(Boolean, default=False)
