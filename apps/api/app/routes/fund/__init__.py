from fastapi import APIRouter

from . import accounting, ddq, deals, monitoring, profile, prospects

router = APIRouter()
router.include_router(profile.router)
router.include_router(prospects.router)
router.include_router(accounting.router)
router.include_router(deals.router)
router.include_router(monitoring.router)
router.include_router(ddq.router)
