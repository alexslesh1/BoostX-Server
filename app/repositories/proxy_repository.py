"""Data-access layer for the ProxyCredential aggregate."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy_credential import ProxyCredential


class ProxyCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_id(self, user_id: uuid.UUID) -> ProxyCredential | None:
        result = await self.session.execute(
            select(ProxyCredential).where(ProxyCredential.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, user_id: uuid.UUID, proxy_login: str, password_encrypted: str
    ) -> ProxyCredential:
        credential = ProxyCredential(
            user_id=user_id, proxy_login=proxy_login, password_encrypted=password_encrypted
        )
        self.session.add(credential)
        await self.session.flush()
        return credential

    async def list_all(self) -> list[ProxyCredential]:
        result = await self.session.execute(select(ProxyCredential))
        return list(result.scalars().all())
