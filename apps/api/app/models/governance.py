import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class MeetingType(str, enum.Enum):
    BOARD = "board"
    AGM = "agm"
    EGM = "egm"


class MeetingStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    HELD = "held"
    CANCELLED = "cancelled"


class ResolutionType(str, enum.Enum):
    BOARD = "board"
    ORDINARY = "ordinary"
    SPECIAL = "special"
    CIRCULAR = "circular"


class ResolutionStatus(str, enum.Enum):
    DRAFT = "draft"
    PASSED = "passed"
    FAILED = "failed"


class DirectorDesignation(str, enum.Enum):
    DIRECTOR = "director"
    MANAGING_DIRECTOR = "managing_director"
    WHOLE_TIME_DIRECTOR = "whole_time_director"
    INDEPENDENT_DIRECTOR = "independent_director"
    NOMINEE_DIRECTOR = "nominee_director"
    COMPANY_SECRETARY = "company_secretary"
    CFO = "cfo"


class DirectorOfficer(Base, TimestampMixin):
    """Director / KMP register entry (FR-G-4; statutory Register of Directors).
    DIN = Director Identification Number."""

    __tablename__ = "directors_officers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    din: Mapped[str | None] = mapped_column(String(16), nullable=True)
    designation: Mapped[DirectorDesignation] = mapped_column(Enum(DirectorDesignation))
    appointed_on: Mapped[datetime.date] = mapped_column(Date)
    resigned_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


class Meeting(Base, TimestampMixin):
    """Board / shareholder meeting with notice, quorum and minutes (FR-G)."""

    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    type: Mapped[MeetingType] = mapped_column(Enum(MeetingType))
    title: Mapped[str] = mapped_column(String(255))
    date: Mapped[datetime.date] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quorum: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(Enum(MeetingStatus), default=MeetingStatus.SCHEDULED)
    minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notice_document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    resolutions: Mapped[list["Resolution"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    agenda_items: Mapped[list["AgendaItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", order_by="AgendaItem.order_index"
    )


class AgendaItem(Base, TimestampMixin):
    __tablename__ = "agenda_items"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meetings.id"), index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(String(255))

    meeting: Mapped[Meeting] = relationship(back_populates="agenda_items")


class Resolution(Base, TimestampMixin):
    """A board/shareholder/circular resolution; can generate + link a document."""

    __tablename__ = "resolutions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    meeting_id: Mapped[str | None] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    type: Mapped[ResolutionType] = mapped_column(Enum(ResolutionType))
    title: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[ResolutionStatus] = mapped_column(
        Enum(ResolutionStatus), default=ResolutionStatus.DRAFT
    )
    passed_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    meeting: Mapped[Meeting | None] = relationship(back_populates="resolutions")
