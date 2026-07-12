"""Device business logic, including MAX_DEVICES_PER_USER enforcement."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.exceptions import ForbiddenException, NotFoundException
from app.models.device import Device
from app.repositories.device_repository import DeviceRepository
from app.schemas.device import DeviceIn
from app.services.token_service import TokenService


class DeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.device_repo = DeviceRepository(session)
        self.token_service = TokenService(session)

    async def list_devices(self, user_id: uuid.UUID) -> list[Device]:
        return await self.device_repo.list_for_user(user_id)

    async def register_device(self, user_id: uuid.UUID, device: DeviceIn) -> Device:
        existing = await self.device_repo.get_by_device_id(user_id, device.device_id)

        if existing is None and settings.MAX_DEVICES_PER_USER > 0:
            current_count = await self.device_repo.count_for_user(user_id)
            if current_count >= settings.MAX_DEVICES_PER_USER:
                raise ForbiddenException(
                    f"Maximum of {settings.MAX_DEVICES_PER_USER} devices already registered "
                    "for this account. Remove an existing device before adding a new one."
                )

        device_obj = await self.device_repo.upsert(
            user_id, device.device_id, device.device_name, device.os
        )
        await self.session.commit()
        return device_obj

    async def delete_device(self, user_id: uuid.UUID, device_id: str) -> None:
        device = await self.device_repo.get_by_device_id(user_id, device_id)
        if device is None:
            raise NotFoundException("Device not found")

        await self.device_repo.delete(device)
        await self.token_service.revoke_all_for_device(user_id, device_id)
        await self.session.commit()
