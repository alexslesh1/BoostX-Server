"""Shared/common Pydantic schemas."""
from __future__ import annotations

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    detail: str
