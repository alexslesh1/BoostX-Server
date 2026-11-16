"""ProxyCredential ORM model (1:1 with User).

Each user gets a unique SOCKS5 login/password pair, generated at
registration time, used to authenticate against the shared 3proxy
relay so the desktop client can offer one-click "Boost Discord" without
ever showing the user a proxy credential.
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


class ProxyCredential(Base):
    __tablename__ = "proxy_credentials"
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
    proxy_login: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    # Symmetrically encrypted (Fernet), not hashed — the server must be able to
    # recover the plaintext to hand it to the authenticated client and to
    # rewrite 3proxy's users file. See app.core.security.encrypt_secret.
    password_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="proxy_credential")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProxyCredential user_id={self.user_id} login={self.proxy_login!r}>"
