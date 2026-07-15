"""Data-access layer for the WireguardPeer aggregate."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wireguard_peer import WireguardPeer


class WireguardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> WireguardPeer | None:
        result = await self.session.execute(
            select(WireguardPeer).where(WireguardPeer.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, user_id: uuid.UUID, public_key: str, private_key_encrypted: str, assigned_ip: str
    ) -> WireguardPeer:
        peer = WireguardPeer(
            user_id=user_id,
            public_key=public_key,
            private_key_encrypted=private_key_encrypted,
            assigned_ip=assigned_ip,
        )
        self.session.add(peer)
        await self.session.flush()
        return peer

    async def list_all(self) -> list[WireguardPeer]:
        result = await self.session.execute(select(WireguardPeer))
        return list(result.scalars().all())

    async def list_assigned_ips(self) -> set[str]:
        result = await self.session.execute(select(WireguardPeer.assigned_ip))
        return set(result.scalars().all())
