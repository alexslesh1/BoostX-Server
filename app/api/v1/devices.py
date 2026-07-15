"""Device management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.device import DeviceIn, DeviceOut
from app.services.device_service import DeviceService

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> list[DeviceOut]:
    service = DeviceService(db)
    devices = await service.list_devices(current_user.id)
    return [DeviceOut.model_validate(d) for d in devices]


@router.post("/register", response_model=DeviceOut)
async def register_device(
    body: DeviceIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeviceOut:
    service = DeviceService(db)
    device = await service.register_device(current_user.id, body)
    return DeviceOut.model_validate(device)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_device(
    device_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = DeviceService(db)
    await service.delete_device(current_user.id, device_id)
