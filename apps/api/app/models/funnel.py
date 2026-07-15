from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class FundraisingLink(Base, TimestampMixin):
    """A public opt-in link for a round (FR-E-8): prospective investors open
    the link, register interest, and (optionally) receive data-room access —
    the top of the fundraising funnel. The token is the only credential."""

    __tablename__ = "fundraising_links"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    round_id: Mapped[str] = mapped_column(ForeignKey("rounds.id"), unique=True, index=True)
    data_room_id: Mapped[str | None] = mapped_column(ForeignKey("data_rooms.id"), nullable=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=gen_id)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(32))
