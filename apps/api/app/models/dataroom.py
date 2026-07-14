import datetime

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class DataRoom(Base, TimestampMixin):
    """A scoped virtual data room for an entity (FR-I-1). Items link existing
    Documents; access grants and engagement logs support diligence."""

    __tablename__ = "data_rooms"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    scope: Mapped[str] = mapped_column(String(64), default="diligence")
    created_by: Mapped[str] = mapped_column(String(32))

    items: Mapped[list["DataRoomItem"]] = relationship(
        back_populates="data_room", cascade="all, delete-orphan", order_by="DataRoomItem.order_index"
    )
    grants: Mapped[list["DataRoomAccessGrant"]] = relationship(
        back_populates="data_room", cascade="all, delete-orphan"
    )


class DataRoomItem(Base, TimestampMixin):
    __tablename__ = "data_room_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    data_room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    folder: Mapped[str] = mapped_column(String(120), default="General")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    data_room: Mapped[DataRoom] = relationship(back_populates="items")


class DataRoomAccessGrant(Base, TimestampMixin):
    __tablename__ = "data_room_access_grants"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    data_room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), index=True)
    email: Mapped[str] = mapped_column(String(255))
    permissions: Mapped[str] = mapped_column(String(32), default="view")
    expiry: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    data_room: Mapped[DataRoom] = relationship(back_populates="grants")


class DataRoomQuestion(Base, TimestampMixin):
    """Diligence Q&A thread item within a data room (FR-I-4)."""

    __tablename__ = "data_room_questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    data_room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), index=True)
    asker: Mapped[str] = mapped_column(String(255))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class EngagementLog(Base, TimestampMixin):
    """Who viewed what, when (FR-I-3) — investor-engagement signal."""

    __tablename__ = "data_room_engagement"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    data_room_id: Mapped[str] = mapped_column(ForeignKey("data_rooms.id"), index=True)
    document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(32), default="view")
