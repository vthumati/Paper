import enum

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class TenantType(str, enum.Enum):
    COMPANY = "company"
    FUND = "fund"
    FIRM = "firm"


class Role(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


WRITE_ROLES = {Role.OWNER, Role.ADMIN, Role.MEMBER}


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Proof-of-ownership gate for email-matched cross-tenant access (SEC H-1).
    # Set at signup: true when verification is not required (dev), otherwise
    # flipped by /auth/verify-email once the emailed token is presented.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    email_verification_token: Mapped[str | None] = mapped_column(String(64), default=None)
    # Bumped on logout / forced sign-out; embedded in the JWT as "tv" and checked
    # on every request, so outstanding tokens are revoked (stateless revocation).
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[TenantType] = mapped_column(Enum(TenantType))

    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.MEMBER)

    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship(back_populates="memberships")


class AdvisorAccess(Base, TimestampMixin):
    """Scoped, cross-tenant access for an external professional (law firm / CA
    / CS) to a single client entity, matched to a user by email — no tenant
    membership required (mirrors the InvestorAccess trust boundary). The
    granted role feeds entity authorization: `viewer` is read-only, `member`
    can act (e.g. a law firm managing filings)."""

    __tablename__ = "advisor_access"
    __table_args__ = (UniqueConstraint("entity_id", "email", name="uq_advisor_entity_email"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    firm_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.VIEWER)
    invited_by: Mapped[str] = mapped_column(String(32))
