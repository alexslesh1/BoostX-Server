"""User profile business logic."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictException
from app.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def update_profile(
        self, user: User, username: str | None = None, avatar_url: str | None = None
    ) -> User:
        if username is not None and username != user.username:
            existing = await self.user_repo.get_by_username(username)
            if existing is not None:
                raise ConflictException("Username already taken")

        updated = await self.user_repo.update_profile(user, username=username, avatar_url=avatar_url)
        await self.session.commit()
        return updated
