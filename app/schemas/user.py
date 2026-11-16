"""User profile request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """Public user profile. NEVER include password_hash here."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    avatar_url: str | None = None
    email_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: datetime | None = None


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=1024)
