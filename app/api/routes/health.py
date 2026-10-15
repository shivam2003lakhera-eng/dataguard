from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.logging import get_logger

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
def health(db: DbSession):
    try:
        db.execute(text("select 1"))
    except Exception:
        logger.exception("Health check: database unavailable")
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable"})
    return {"status": "ok", "database": "ok"}