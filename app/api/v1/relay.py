"""Relay session endpoint — the list of relays plus a token for them."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.relay import RelaySessionIn, RelaySessionOut
from app.services.relay_service import RelayService

router = APIRouter(prefix="/relay", tags=["relay"])


@router.post("/session", response_model=RelaySessionOut)
async def open_relay_session(
    body: RelaySessionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RelaySessionOut:
    return await RelayService(db).open_session(current_user.id, body.device_id)
