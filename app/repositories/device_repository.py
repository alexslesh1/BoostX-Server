"""Data-access layer for the Device aggregate."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


class DeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_device_id(self, user_id: uuid.UUID, device_id: str) -> Device | None:
        result = await self.session.execute(
            select(Device).where(Device.user_id == user_id, Device.device_id == device_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[Device]:
        result = await self.session.execute(
            select(Device).where(Device.user_id == user_id).order_by(Device.last_seen.desc())
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Device).where(Device.user_id == user_id)
        )
        return int(result.scalar_one())

    async def upsert(
        self, user_id: uuid.UUID, device_id: str, device_name: str, os: str
    ) -> Device:
        device = await self.get_by_device_id(user_id, device_id)
        now = datetime.now(timezone.utc)
        if device is None:
            device = Device(
                user_id=user_id,
                device_id=device_id,
                device_name=device_name,
                os=os,
                last_seen=now,
            )
            self.session.add(device)
        else:
            device.device_name = device_name
            device.os = os
            device.last_seen = now
        await self.session.flush()
        return device

    async def delete(self, device: Device) -> None:
        await self.session.delete(device)
        await self.session.flush()
