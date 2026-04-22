import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    checks: dict[str, str] = {"status": "ok", "db": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Health check DB failed: %s", exc)
        checks["db"] = "error"
        checks["status"] = "degraded"

    try:
        await redis_client.ping()
    except Exception as exc:
        logger.warning("Health check Redis failed: %s", exc)
        checks["redis"] = "error"
        checks["status"] = "degraded"

    status_code = 200 if checks["status"] == "ok" else 503
    return JSONResponse(content=checks, status_code=status_code)
