"""Boost VPN — per-user WireGuard peer provisioning and split-tunnel
.conf generation.

Generates a unique WireGuard keypair + VPN-subnet IP per user at
registration time and keeps the server's wg0.conf peer list in sync.
Complements the SOCKS5 proxy_credentials/3proxy system — not a
replacement; both stay available. The client is expected to only route
specific per-app traffic (Discord, Telegram, ...) through this tunnel via
its own split-tunneling, which has no bearing on the server side: from
here it's just a peer with AllowedIPs 0.0.0.0/0.

File sync is best-effort, same pattern as ProxyService.sync_users_file:
a failure to write wg0.conf or reload WireGuard is logged but never
raised, and the full peer list is rewritten from the database each time
so a missed sync self-heals on the next one.
"""
from __future__ import annotations

import asyncio
import ipaddress
import subprocess
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decrypt_secret, encrypt_secret, generate_wireguard_keypair
from app.models.wireguard_peer import WireguardPeer
from app.repositories.wireguard_repository import WireguardRepository

logger = get_logger(__name__)

_RELOAD_TIMEOUT_SECONDS = 10
_MANAGED_BEGIN = "# BEGIN BOOSTX MANAGED PEERS — do not edit this block by hand"
_MANAGED_END = "# END BOOSTX MANAGED PEERS"


class WireguardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WireguardRepository(session)

    async def provision_for_user(self, user_id: uuid.UUID) -> WireguardPeer:
        """Insert a new peer row. DB-only — does not touch wg0.conf (caller
        is responsible for calling `sync_config_file()` once its own
        transaction has committed)."""
        private_key, public_key = generate_wireguard_keypair()
        assigned_ip = await self._next_free_ip()
        return await self.repo.create(user_id, public_key, encrypt_secret(private_key), assigned_ip)

    async def get_or_provision(self, user_id: uuid.UUID) -> WireguardPeer:
        """Self-healing lookup for accounts created before this feature
        existed, or if registration-time provisioning was rolled back."""
        peer = await self.repo.get_by_user_id(user_id)
        if peer is not None:
            return peer
        peer = await self.provision_for_user(user_id)
        await self.session.commit()
        await self.sync_config_file()
        return peer

    async def get_client_config(self, user_id: uuid.UUID) -> str:
        peer = await self.get_or_provision(user_id)
        private_key = decrypt_secret(peer.private_key_encrypted)
        return (
            "[Interface]\n"
            f"PrivateKey = {private_key}\n"
            f"Address = {peer.assigned_ip}/32\n"
            f"DNS = {settings.WIREGUARD_DNS}\n"
            "\n"
            "[Peer]\n"
            f"PublicKey = {settings.WIREGUARD_SERVER_PUBLIC_KEY}\n"
            f"Endpoint = {settings.WIREGUARD_SERVER_HOST}:{settings.WIREGUARD_SERVER_PORT}\n"
            "AllowedIPs = 0.0.0.0/0\n"
            "PersistentKeepalive = 25\n"
        )

    async def sync_config_file(self) -> None:
        if not settings.WIREGUARD_SYNC_CONFIG_FILE:
            return
        try:
            peers = await self.repo.list_all()
            peer_blocks = self._render_peer_blocks(peers)
            await asyncio.to_thread(self._write_config_file, peer_blocks)
            await asyncio.to_thread(self._reload_wireguard)
        except Exception:
            logger.exception("Failed to sync wg0.conf — WireGuard peers may be stale")

    async def _next_free_ip(self) -> str:
        used_ips = await self.repo.list_assigned_ips()
        network = ipaddress.ip_network(settings.WIREGUARD_SUBNET_CIDR, strict=False)
        server_ip = ipaddress.ip_address(settings.WIREGUARD_SERVER_VPN_IP)
        for host in network.hosts():
            if host == server_ip:
                continue
            if str(host) not in used_ips:
                return str(host)
        raise RuntimeError(
            f"WireGuard subnet {settings.WIREGUARD_SUBNET_CIDR} is exhausted — no free IP left"
        )

    @staticmethod
    def _render_peer_blocks(peers: list[WireguardPeer]) -> str:
        lines = [_MANAGED_BEGIN]
        for peer in peers:
            lines.append("")
            lines.append("[Peer]")
            lines.append(f"PublicKey = {peer.public_key}")
            lines.append(f"AllowedIPs = {peer.assigned_ip}/32")
        lines.append("")
        lines.append(_MANAGED_END)
        return "\n".join(lines)

    @staticmethod
    def _write_config_file(peer_blocks: str) -> None:
        target = Path(settings.WIREGUARD_CONFIG_FILE)
        if not target.is_file():
            logger.error(f"WireGuard config file does not exist: {target}")
            return
        original = target.read_text(encoding="utf-8")
        if _MANAGED_BEGIN in original and _MANAGED_END in original:
            before = original.split(_MANAGED_BEGIN, 1)[0].rstrip("\n")
            after = original.split(_MANAGED_END, 1)[1].lstrip("\n")
            new_content = before + "\n\n" + peer_blocks + "\n" + (("\n" + after) if after else "\n")
        else:
            new_content = original.rstrip("\n") + "\n\n" + peer_blocks + "\n"

        fd, tmp_path = tempfile.mkstemp(dir=target.parent, prefix=".wg0-", suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(new_content)
            Path(tmp_path).replace(target)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    @staticmethod
    def _reload_wireguard() -> None:
        command = settings.WIREGUARD_RELOAD_COMMAND.strip()
        if not command:
            return
        # Run through a real shell rather than argv-splitting: the default
        # command uses bash process substitution (`<(...)`), which has no
        # meaning outside a shell.
        result = subprocess.run(
            ["bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=_RELOAD_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            logger.error(
                f"WireGuard reload command exited {result.returncode}: {result.stderr.strip()}"
            )
