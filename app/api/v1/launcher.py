"""Future remote-synced launcher catalog — stub only.

This router is a placeholder for a LATER feature: serving a remote-synced
boost/game catalog to the desktop client, replacing the client's local
static catalog file so boosts/games can be updated without a client release.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.exceptions import NotImplementedException

router = APIRouter(prefix="/launcher", tags=["launcher"])


@router.get("/catalog")
async def get_catalog() -> None:
    """Remote boost/game catalog (not implemented yet).

    Once wired up, this endpoint will return the current catalog of
    boosts/games (id, name, description, icon, requirements, etc.) so the
    desktop client can sync instead of relying on its bundled static
    catalog. For now it always returns 501.
    """
    raise NotImplementedException("Not implemented yet")
