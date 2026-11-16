"""Relay sessions — tells a signed-in device which relays exist and signs
the token that lets it use them.

Relays are stateless: they verify the token's signature with a shared
secret and never call back here. Adding a server is therefore only a
matter of running nexora-relay on it and listing it in RELAY_SERVERS.
"""
from __future__ import annotations

import base64
import binascii
import json
import time
import uuid

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import sign_relay_token
from app.exceptions import AppException, ForbiddenException
from app.repositories.device_repository import DeviceRepository
from app.schemas.relay import RelayServerOut, RelaySessionOut

logger = get_logger(__name__)

_MIN_SECRET_BYTES = 16  # the relay refuses anything shorter
_servers_adapter = TypeAdapter(list[RelayServerOut])


class RelayUnavailableException(AppException):
    status_code = 503
    detail = "Routing servers are not available right now"


def load_relay_servers() -> list[RelayServerOut]:
    """Parses RELAY_SERVERS. A malformed value is an operator mistake, not
    something a client can fix, so it is logged and treated as "none"."""
    try:
        return _servers_adapter.validate_python(json.loads(settings.RELAY_SERVERS or "[]"))
    except (ValueError, ValidationError) as exc:
        logger.error(f"RELAY_SERVERS is not a valid relay list: {exc}")
        return []


def load_relay_token_secret() -> bytes | None:
    raw = settings.RELAY_TOKEN_SECRET.strip()
    if not raw:
        return None
    try:
        secret = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        logger.error("RELAY_TOKEN_SECRET is not valid base64")
        return None
    if len(secret) < _MIN_SECRET_BYTES:
        logger.error("RELAY_TOKEN_SECRET is too short")
        return None
    return secret


class RelayService:
    def __init__(self, session: AsyncSession) -> None:
        self.device_repo = DeviceRepository(session)

    async def open_session(self, user_id: uuid.UUID, device_id: str) -> RelaySessionOut:
        # Only a device the account still has registered gets a token, so
        # removing a device in Account also cuts it off from the relays
        # (as soon as its current token runs out).
        if await self.device_repo.get_by_device_id(user_id, device_id) is None:
            raise ForbiddenException("This device is not registered for the account")

        secret = load_relay_token_secret()
        servers = load_relay_servers()
        if secret is None or not servers:
            raise RelayUnavailableException()

        expires_at = int(time.time()) + settings.RELAY_TOKEN_TTL_SECONDS
        return RelaySessionOut(
            token=sign_relay_token(secret, user_id, device_id, expires_at),
            expires_at=expires_at,
            servers=servers,
        )
