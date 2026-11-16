"""Boost Discord proxy credential endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.proxy import ProxyConnectionInfo
from app.services.proxy_service import ProxyService

router = APIRouter(prefix="/proxy", tags=["proxy"])


@router.get("/credentials", response_model=ProxyConnectionInfo)
async def get_proxy_credentials(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProxyConnectionInfo:
    service = ProxyService(db)
    return await service.get_connection_info(current_user.id)
