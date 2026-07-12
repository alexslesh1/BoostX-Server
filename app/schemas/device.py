"""Device request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceIn(BaseModel):
    """Device payload embedded in login, and used for /devices/register."""

    device_id: str = Field(..., min_length=1, max_length=255)
    device_name: str = Field(..., min_length=1, max_length=255)
    os: str = Field(..., min_length=1, max_length=128)


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_id: str
    device_name: str
    os: str
    last_seen: datetime
    created_at: datetime
