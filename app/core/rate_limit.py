"""Rate limiting configuration, backed by slowapi.

Storage backend is configuration-driven via RATE_LIMIT_STORAGE_URI:
- empty (default): in-memory storage, fine for a single-process deployment.
- a Redis URI (e.g. redis://localhost:6379/0): swaps to Redis-backed storage
  so limits are shared across multiple worker processes/instances.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Sensible default: 5 requests/minute per client IP for sensitive auth endpoints.
DEFAULT_AUTH_RATE_LIMIT = "5/minute"

_storage_uri = settings.RATE_LIMIT_STORAGE_URI.strip() or "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    default_limits=[],
)
