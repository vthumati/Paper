
from fastapi import APIRouter, Depends

from ..deps import EntityCtx, entity_ctx
from ..schemas import TermSheetScanIn
from ..services import termsheet as svc

router = APIRouter(tags=["termsheet"])


@router.post("/entities/{entity_id}/termsheet/scan")
def scan_term_sheet(body: TermSheetScanIn, ctx: EntityCtx = Depends(entity_ctx)):
    """Pure computation over pasted text — nothing is stored (paste-and-scan,
    like the scenario modeler)."""
    return svc.scan(body.text)
