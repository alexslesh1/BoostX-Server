"""Health-check endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger(__name__)


@router.get("")
async def health() -> dict:
    """Liveness check — no DB hit, no auth."""
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/db")
async def health_db(response: Response, db: AsyncSession = Depends(get_db)) -> dict:
    """Readiness check — performs a real SELECT 1 against the database."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception:
        logger.exception("Database health check failed")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "error"}
