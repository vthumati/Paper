"""Import all model modules so SQLAlchemy registers them on Base.metadata."""
from .base import Base
from . import (  # noqa: F401
    identity,
    entity,
    captable,
    workflow,
    document,
    dataroom,
    compliance,
    fund,
    esop,
    valuation,
    marketplace,
    managed,
    spv,
    round,
    governance,
    audit,
    notification,
    tax,
    team,
    clm,
    portal,
    crm,
    startup,
    finance,
    registers,
    instruments,
    founders,
)

__all__ = ["Base"]
