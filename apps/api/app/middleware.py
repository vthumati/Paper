"""Platform middleware: immutable audit trail (NFR-4)."""
from fastapi import FastAPI, Request

from .db import SessionLocal
from .models.audit import AuditLogEntry
from .models.identity import User
from .security import decode_token

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def install_audit_middleware(app: FastAPI) -> None:
    """Record every mutating request (actor, path, result) in the audit log.
    Best-effort: an audit failure must never fail the request."""

    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        response = await call_next(request)
        if request.method in _MUTATING:
            try:
                auth_header = request.headers.get("authorization") or ""
                sub = (
                    decode_token(auth_header[7:])
                    if auth_header[:7].lower() == "bearer "
                    else None
                )
                db = SessionLocal()
                try:
                    email = None
                    if sub:
                        u = db.get(User, sub)
                        email = u.email if u else None
                    db.add(
                        AuditLogEntry(
                            actor_user_id=sub,
                            actor_email=email,
                            method=request.method,
                            path=request.url.path,
                            status_code=response.status_code,
                        )
                    )
                    db.commit()
                finally:
                    db.close()
            except Exception:
                pass
        return response
