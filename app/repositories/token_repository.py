"""Data-access layer for the RefreshToken aggregate."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class TokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
        device_id: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            device_id=device_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken, replaced_by_id: uuid.UUID | None = None) -> None:
        token.revoked = True
        if replaced_by_id is not None:
            token.replaced_by_id = replaced_by_id
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self.session.flush()

    async def revoke_all_for_device(self, user_id: uuid.UUID, device_id: str) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.device_id == device_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        )
        await self.session.flush()
