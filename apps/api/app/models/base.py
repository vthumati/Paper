from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..clock import now_ist


def gen_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    # Python-side default: IST (the platform clock, see app/clock.py) with
    # microsecond precision so ledger events created in the same second still
    # order deterministically (server_default kept only as a raw-SQL fallback).
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=now_ist, server_default=func.now(), onupdate=now_ist
    )
