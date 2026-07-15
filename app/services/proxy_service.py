"""Boost Discord — per-user SOCKS5 proxy credential provisioning.

Generates a unique 3proxy login/password per user at registration time and
keeps 3proxy's `users` auth file (format: `login:CL:password`, one per
line) in sync, so the desktop client can fetch its own credentials and
authenticate against the relay without the user ever seeing them.

File sync is best-effort: a failure to write the users file or reload
3proxy is logged but never raised, so a relay hiccup can't block
registration/login. It also self-heals — the file is fully rewritten from
the database each time, so a missed sync is corrected by the next one.
"""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decrypt_secret, encrypt_secret, generate_proxy_login, generate_proxy_password
from app.models.proxy_credential import ProxyCredential
from app.repositories.proxy_repository import ProxyCredentialRepository
from app.schemas.proxy import ProxyConnectionInfo

logger = get_logger(__name__)

_RELOAD_TIMEOUT_SECONDS = 10


class ProxyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProxyCredentialRepository(session)

    async def provision_for_user(self, user_id: uuid.UUID) -> ProxyCredential:
        """Insert a new credential row. DB-only — does not touch the 3proxy
        users file (caller is responsible for calling `sync_users_file()`
        once its own transaction has committed)."""
        login = generate_proxy_login(user_id)
        password_encrypted = encrypt_secret(generate_proxy_password())
        return await self.repo.create(user_id, login, password_encrypted)

    async def get_or_provision(self, user_id: uuid.UUID) -> ProxyCredential:
        """Self-healing lookup for accounts created before this feature
        existed, or if the registration-time provisioning was rolled back."""
        credential = await self.repo.get_by_user_id(user_id)
        if credential is not None:
            return credential
        credential = await self.provision_for_user(user_id)
        await self.session.commit()
        await self.sync_users_file()
        return credential

    async def get_connection_info(self, user_id: uuid.UUID) -> ProxyConnectionInfo:
        credential = await self.get_or_provision(user_id)
        return ProxyConnectionInfo(
            host=settings.PROXY_HOST,
            port=settings.PROXY_PORT,
            login=credential.proxy_login,
            password=decrypt_secret(credential.password_encrypted),
        )

    async def sync_users_file(self) -> None:
        """Rewrite 3proxy's users file from the full credential list and
        reload the service. No-op if PROXY_SYNC_3PROXY_FILE is disabled."""
        if not settings.PROXY_SYNC_3PROXY_FILE:
            return
        try:
            credentials = await self.repo.list_all()
            lines = [
                f"{c.proxy_login}:CL:{decrypt_secret(c.password_encrypted)}" for c in credentials
            ]
            content = "\n".join(lines) + "\n" if lines else ""
            await asyncio.to_thread(self._write_users_file, content)
            await asyncio.to_thread(self._reload_3proxy)
        except Exception:
            logger.exception("Failed to sync 3proxy users file — proxy credentials may be stale")

    @staticmethod
    def _write_users_file(content: str) -> None:
        target = Path(settings.PROXY_3PROXY_USERS_FILE)
        if not target.parent.is_dir():
            logger.error(f"3proxy users file directory does not exist: {target.parent}")
            return
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, prefix=".users-", suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp_path).replace(target)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @staticmethod
    def _reload_3proxy() -> None:
        command = settings.PROXY_3PROXY_RELOAD_COMMAND.strip()
        if not command:
            return
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=_RELOAD_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.error(
                f"3proxy reload command exited {result.returncode}: {result.stderr.strip()}"
            )
