"""WireguardPeer ORM model (1:1 with User).

Each user gets a unique WireGuard keypair and a VPN-subnet IP, generated
at registration time, so the desktop client can fetch a ready-to-use
.conf via GET /api/v1/vpn/config without the user ever handling keys
directly. Complements the SOCKS5 proxy_credentials system — not a
replacement for it.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class WireguardPeer(Base):
    __tablename__ = "wireguard_peers"
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    public_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # Symmetrically encrypted (Fernet, same mechanism as
    # proxy_credentials.password_encrypted) — not hashed, the server must
    # recover the plaintext to hand it back in the client's .conf.
    private_key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    assigned_ip: Mapped[str] = mapped_column(String(15), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="wireguard_peer")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WireguardPeer user_id={self.user_id} assigned_ip={self.assigned_ip!r}>"
