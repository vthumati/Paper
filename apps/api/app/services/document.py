"""Document module service (FR-F): generation from templates, append-only
versioning, and a simulated e-sign flow (create request -> provider callback
-> document signed), mirroring HLD §9.4."""
import hmac
import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..clock import now_ist
from ..documents.templates import REGISTRY, render
from ..models.document import (
    Document,
    DocumentStatus,
    DocumentVersion,
    SignatureRequest,
    SignatureStatus,
)


def _template_or_404(template_key: str):
    t = REGISTRY.get(template_key)
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown template '{template_key}'")
    return t


def create_document(
    db: Session,
    entity_id: str,
    template_key: str,
    data: dict,
    user_id: str,
    title: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
) -> Document:
    t = _template_or_404(template_key)
    doc = Document(
        entity_id=entity_id,
        type=t.doc_type,
        title=title or t.name,
        status=DocumentStatus.GENERATED,
        template_key=template_key,
        current_version=1,
        subject_type=subject_type,
        subject_id=subject_id,
        created_by=user_id,
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentVersion(
            document_id=doc.id, version=1, content=render(template_key, data), created_by=user_id
        )
    )
    db.commit()
    db.refresh(doc)
    return doc


def regenerate(db: Session, doc: Document, data: dict, user_id: str, title: str | None = None) -> Document:
    if not doc.template_key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Document has no template to regenerate from")
    if doc.status == DocumentStatus.SIGNED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot regenerate a signed document")
    new_version = doc.current_version + 1
    db.add(
        DocumentVersion(
            document_id=doc.id,
            version=new_version,
            content=render(doc.template_key, data),
            created_by=user_id,
        )
    )
    doc.current_version = new_version
    doc.status = DocumentStatus.GENERATED
    if title:
        doc.title = title
    db.commit()
    db.refresh(doc)
    return doc


def current_content(db: Session, doc: Document) -> str | None:
    v = (
        db.query(DocumentVersion)
        .filter_by(document_id=doc.id, version=doc.current_version)
        .first()
    )
    return v.content if v else None


def document_view(db: Session, doc: Document) -> dict:
    return {
        "id": doc.id,
        "entity_id": doc.entity_id,
        "type": doc.type,
        "title": doc.title,
        "status": doc.status,
        "template_key": doc.template_key,
        "current_version": doc.current_version,
        "subject_type": doc.subject_type,
        "subject_id": doc.subject_id,
        "content": current_content(db, doc),
    }


def create_signature(
    db: Session, doc: Document, signatories: list, provider: str, user_id: str
) -> SignatureRequest:
    sig = SignatureRequest(
        document_id=doc.id,
        provider=provider or "aadhaar_esign",
        status=SignatureStatus.PENDING,
        signatories=signatories or [],
        completion_token=secrets.token_urlsafe(24),
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)
    # MVP shim: a real provider (Digio/Aadhaar eSign) would deliver this to the
    # signer and POST it back on completion; here it is logged and returned once
    # on creation so the completion step can present it.
    print(f"[e-sign] completion token for signature {sig.id}: {sig.completion_token}")
    return sig


def complete_signature(db: Session, sig: SignatureRequest, token: str) -> SignatureRequest:
    """Complete the signature — the verified-provider-callback step. Requires the
    completion token issued at request time (not merely workspace write access),
    so a doc cannot be flipped to 'signed' outside the signer/provider flow."""
    if sig.status == SignatureStatus.COMPLETED:
        return sig
    if not sig.completion_token or not hmac.compare_digest(token or "", sig.completion_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid signature-completion token")
    sig.status = SignatureStatus.COMPLETED
    sig.completed_at = now_ist()
    doc = db.get(Document, sig.document_id)
    if doc:
        doc.status = DocumentStatus.SIGNED
    db.commit()
    db.refresh(sig)
    return sig
