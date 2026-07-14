import datetime
import enum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class DocumentStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    SIGNED = "signed"


class SignatureStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    DECLINED = "declined"


class Document(Base, TimestampMixin):
    """A first-class document with a polymorphic subject link (HLD §6.4):
    subject_type/subject_id point at any domain object (round, workflow run,
    certificate ...). Content is versioned in DocumentVersion."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.GENERATED
    )
    template_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    subject_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subject_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        order_by="DocumentVersion.version",
        cascade="all, delete-orphan",
    )
    signatures: Mapped[list["SignatureRequest"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentVersion(Base, TimestampMixin):
    __tablename__ = "document_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(32))

    document: Mapped[Document] = relationship(back_populates="versions")


class SignatureRequest(Base, TimestampMixin):
    __tablename__ = "signature_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32), default="aadhaar_esign")
    status: Mapped[SignatureStatus] = mapped_column(
        Enum(SignatureStatus), default=SignatureStatus.PENDING
    )
    signatories: Mapped[list] = mapped_column(JSON, default=list)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    document: Mapped[Document] = relationship(back_populates="signatures")
