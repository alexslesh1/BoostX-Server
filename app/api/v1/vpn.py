"""Boost VPN — WireGuard client config endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.wireguard_service import WireguardService

router = APIRouter(prefix="/vpn", tags=["vpn"])


@router.get("/config", response_class=PlainTextResponse)
async def get_vpn_config(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> str:
    service = WireguardService(db)
    return await service.get_client_config(current_user.id)
