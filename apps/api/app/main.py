from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import DEFAULT_JWT_SECRET, settings
from .db import engine
from .middleware import install_audit_middleware
from .models import Base
from .routes import (
    activity,
    alerts,
    auth,
    captable,
    clm,
    compliance,
    crm,
    dataroom,
    diligence,
    documents,
    entities,
    esop,
    finance,
    funnel,
    incorporation,
    founders,
    fund,
    governance,
    instruments,
    managed,
    marketplace,
    portal,
    registers,
    rights,
    round,
    spv,
    startup,
    team,
    tenants,
    termsheet,
    valuation,
    workflows,
    workspace,
)

ROUTE_MODULES = [
    activity, auth, tenants, entities, captable, workflows, documents,
    dataroom, compliance, fund, esop, valuation, marketplace, managed,
    spv, round, governance, workspace, team, clm, portal, rights, crm,
    startup, finance, registers, alerts, instruments, founders,
    incorporation, diligence, funnel, termsheet,
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Refuse to boot outside dev/test with the shipped JWT secret.
    if settings.environment not in ("dev", "test") and settings.jwt_secret == DEFAULT_JWT_SECRET:
        raise RuntimeError("PAPER_JWT_SECRET must be set in non-dev environments")
    if settings.auto_create_tables:
        # Dev convenience; prod runs `alembic upgrade head` instead (NFR-12).
        Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# Dev: allow the Vite frontend origin. Tighten via PAPER_CORS_ORIGINS in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_audit_middleware(app)

for module in ROUTE_MODULES:
    app.include_router(module.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name}
