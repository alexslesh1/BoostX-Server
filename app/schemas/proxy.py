"""Boost Discord proxy connection schema."""
from __future__ import annotations

from pydantic import BaseModel


class ProxyConnectionInfo(BaseModel):
    """SOCKS5 relay connection info for the current user. Never displayed
    to the user — the desktop client uses this to configure its local
    proxy bridge automatically."""

    host: str
    port: int
    login: str
    password: str
