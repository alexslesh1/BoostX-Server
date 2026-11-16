"""Data-access layer for the User aggregate."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, username: str, email: str, password_hash: str) -> User:
        user = User(username=username, email=email.lower(), password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        return user

    async def set_password(self, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        await self.session.flush()

    async def set_email_verified(self, user: User, verified: bool = True) -> None:
        user.email_verified = verified
        await self.session.flush()

    async def update_email(self, user: User, new_email: str) -> None:
        user.email = new_email.lower()
        await self.session.flush()

    async def update_last_login(self, user: User) -> None:
        user.last_login = datetime.now(timezone.utc)
        await self.session.flush()

    async def update_profile(
        self, user: User, username: str | None = None, avatar_url: str | None = None
    ) -> User:
        if username is not None:
            user.username = username
        if avatar_url is not None:
            user.avatar_url = avatar_url
        await self.session.flush()
        return user
