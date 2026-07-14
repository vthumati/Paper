from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    DocCtx,
    EntityCtx,
    PageCtx,
    SignatureCtx,
    doc_ctx,
    entity_ctx,
    get_current_user,
    page,
    require_write,
    signature_ctx,
)
from ..documents.templates import REGISTRY
from ..models.document import Document, DocumentVersion
from ..models.identity import User
from ..schemas import (
    DocumentCreateIn,
    DocumentOut,
    DocumentTemplateOut,
    DocumentVersionOut,
    RegenerateIn,
    SignatureCreateIn,
    SignatureOut,
)
from ..services import document as docsvc
from ..services.pdf import render_pdf

router = APIRouter(tags=["documents"])


def document_pdf_response(db: Session, doc: Document) -> Response:
    body = docsvc.current_content(db, doc) or ""
    meta = f"{doc.type} - version {doc.current_version} - status {doc.status.value}"
    safe_name = "".join(c if c.isalnum() or c in " -_" else "-" for c in doc.title)[:80]
    return Response(
        content=render_pdf(doc.title, meta, body),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'},
    )


@router.get("/document-templates", response_model=list[DocumentTemplateOut])
def list_templates(_: User = Depends(get_current_user)):
    return [
        DocumentTemplateOut(key=t.key, name=t.name, doc_type=t.doc_type)
        for t in REGISTRY.values()
    ]


@router.post("/entities/{entity_id}/documents", response_model=DocumentOut, status_code=201)
def create_document(
    body: DocumentCreateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = docsvc.create_document(
        db,
        entity_id=ctx.entity.id,
        template_key=body.template_key,
        data=body.data,
        user_id=user.id,
        title=body.title,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
    )
    return docsvc.document_view(db, doc)


@router.get("/entities/{entity_id}/documents", response_model=list[DocumentOut])
def list_documents(
    p: PageCtx = Depends(page),
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    docs = (
        db.query(Document)
        .filter_by(entity_id=ctx.entity.id)
        .order_by(Document.created_at.desc())
        .offset(p.offset)
        .limit(p.limit)
        .all()
    )
    return [docsvc.document_view(db, d) for d in docs]


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(ctx: DocCtx = Depends(doc_ctx), db: Session = Depends(get_db)):
    return docsvc.document_view(db, ctx.document)


@router.get("/documents/{document_id}/pdf")
def download_document_pdf(ctx: DocCtx = Depends(doc_ctx), db: Session = Depends(get_db)):
    return document_pdf_response(db, ctx.document)


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionOut])
def list_versions(ctx: DocCtx = Depends(doc_ctx), db: Session = Depends(get_db)):
    return (
        db.query(DocumentVersion)
        .filter_by(document_id=ctx.document.id)
        .order_by(DocumentVersion.version)
        .all()
    )


@router.post("/documents/{document_id}/regenerate", response_model=DocumentOut)
def regenerate(
    body: RegenerateIn,
    ctx: DocCtx = Depends(doc_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = docsvc.regenerate(db, ctx.document, body.data, user.id, body.title)
    return docsvc.document_view(db, doc)


@router.post("/documents/{document_id}/signatures", response_model=SignatureOut, status_code=201)
def request_signature(
    body: SignatureCreateIn,
    ctx: DocCtx = Depends(doc_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return docsvc.create_signature(db, ctx.document, body.signatories, body.provider, user.id)


@router.post("/signatures/{signature_id}/complete", response_model=SignatureOut)
def complete_signature(
    ctx: SignatureCtx = Depends(signature_ctx), db: Session = Depends(get_db)
):
    # Represents processing the verified e-sign provider callback (HLD §9.4).
    require_write(ctx.role)
    return docsvc.complete_signature(db, ctx.signature)
