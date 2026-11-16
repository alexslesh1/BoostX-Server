"""Access/refresh token issuance, validation, and rotation logic.

Rotation policy: every successful /auth/refresh call revokes the presented
refresh token and issues a brand new one (rotation chain tracked via
`replaced_by_id`). Presenting an already-revoked token is treated as a
compromise signal — ALL of that user's active refresh tokens are revoked
and 401 is returned.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.exceptions import UnauthorizedException
from app.models.refresh_token import RefreshToken
from app.repositories.token_repository import TokenRepository


class TokenService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.token_repo = TokenRepository(session)

    async def issue_tokens(
        self,
        user_id: uuid.UUID,
        device_id: str | None = None,
        remember_me: bool = False,
    ) -> tuple[str, str, int]:
        """Issue a fresh access + refresh token pair. Returns (access, refresh_raw, expires_in)."""
        access_token, expires_in = create_access_token(user_id)
        raw_refresh = generate_refresh_token()
        token_hash = hash_refresh_token(raw_refresh)
        expires_at = refresh_token_expiry(remember_me)
        await self.token_repo.create(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at, device_id=device_id
        )
        return access_token, raw_refresh, expires_in

    async def rotate_refresh_token(self, raw_refresh_token: str) -> tuple[str, str, int]:
        """Validate + rotate a refresh token. Returns (new_access, new_refresh_raw, expires_in)."""
        token_hash = hash_refresh_token(raw_refresh_token)
        token: RefreshToken | None = await self.token_repo.get_by_hash(token_hash)

        if token is None:
            raise UnauthorizedException("Invalid refresh token")

        if token.revoked:
            # Reuse of a rotated-out token indicates possible theft/compromise.
            # Commit immediately: we're about to raise, and an uncommitted
            # flush would otherwise be rolled back when the session closes,
            # silently undoing the revocation we rely on for safety.
            await self.token_repo.revoke_all_for_user(token.user_id)
            await self.session.commit()
            raise UnauthorizedException("Refresh token reuse detected; all sessions revoked")

        if token.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedException("Refresh token expired")

        new_access, expires_in = create_access_token(token.user_id)
        new_raw = generate_refresh_token()
        new_hash = hash_refresh_token(new_raw)
        new_expires_at = refresh_token_expiry(remember_me=False)

        new_token = await self.token_repo.create(
            user_id=token.user_id,
            token_hash=new_hash,
            expires_at=new_expires_at,
            device_id=token.device_id,
        )
        await self.token_repo.revoke(token, replaced_by_id=new_token.id)

        return new_access, new_raw, expires_in

    async def revoke_refresh_token(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        token = await self.token_repo.get_by_hash(token_hash)
        if token is not None and not token.revoked:
            await self.token_repo.revoke(token)

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.token_repo.revoke_all_for_user(user_id)

    async def revoke_all_for_device(self, user_id: uuid.UUID, device_id: str) -> None:
        await self.token_repo.revoke_all_for_device(user_id, device_id)
