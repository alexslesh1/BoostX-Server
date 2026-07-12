"""Shared FastAPI dependencies: DB session, current-user resolution."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db as _get_db
from app.exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User
from app.repositories.user_repository import UserRepository

# Re-exported so routers only need to import from app.api.deps.
get_db = _get_db

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedException("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise UnauthorizedException("Invalid or expired token")

    raw_user_id = payload.get("sub")
    try:
        user_id = uuid.UUID(str(raw_user_id))
    except (ValueError, TypeError):
        raise UnauthorizedException("Invalid or expired token")

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedException("Invalid or expired token")

    return user


async def get_current_verified_user(user: User = Depends(get_current_user)) -> User:
    if not user.email_verified:
        raise ForbiddenException("Email verification required")
    return user
