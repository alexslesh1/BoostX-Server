"""Relay session schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RelayServerOut(BaseModel):
    """One relay the client may connect to."""

    id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    region: str = Field(default="", max_length=64)
    # host:port of the relay's UDP listener.
    address: str = Field(..., min_length=3, max_length=255)
    # The relay's own public key (base64), so the client knows it is
    # talking to the real relay and not something in between.
    public_key: str = Field(..., min_length=40, max_length=64)


class RelaySessionIn(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=255)


class RelaySessionOut(BaseModel):
    """Everything the desktop client's engine needs to route traffic:
    where the relays are and a token they will accept. Never shown to the
    user."""

    token: str
    # Unix seconds; the client asks for a new session before this.
    expires_at: int
    servers: list[RelayServerOut]
