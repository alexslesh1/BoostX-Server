"""Data-access layer for the VerificationCode aggregate."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_code import VerificationCode, VerificationPurpose


class VerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        purpose: VerificationPurpose,
        code_hash: str,
        expires_at: datetime,
        target_email: str | None = None,
    ) -> VerificationCode:
        code = VerificationCode(
            user_id=user_id,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
            target_email=target_email,
        )
        self.session.add(code)
        await self.session.flush()
        return code

    async def get_latest_active(
        self, user_id: uuid.UUID, purpose: VerificationPurpose
    ) -> VerificationCode | None:
        """Latest, unconsumed code for a user/purpose (regardless of expiry — caller checks expiry)."""
        result = await self.session.execute(
            select(VerificationCode)
            .where(
                VerificationCode.user_id == user_id,
                VerificationCode.purpose == purpose,
                VerificationCode.consumed.is_(False),
            )
            .order_by(VerificationCode.created_at.desc())
        )
        return result.scalars().first()

    async def invalidate_active(self, user_id: uuid.UUID, purpose: VerificationPurpose) -> None:
        """Consume any outstanding codes for this user/purpose (e.g. before issuing a new one)."""
        await self.session.execute(
            update(VerificationCode)
            .where(
                VerificationCode.user_id == user_id,
                VerificationCode.purpose == purpose,
                VerificationCode.consumed.is_(False),
            )
            .values(consumed=True)
        )
        await self.session.flush()

    async def consume(self, code: VerificationCode) -> None:
        code.consumed = True
        await self.session.flush()
