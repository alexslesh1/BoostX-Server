"""Password hashing, JWT encode/decode, and verification-code helpers.

Passwords are hashed with the `bcrypt` package directly (never plaintext,
never logged). JWTs are signed with PyJWT. Six-digit verification codes are
generated with `secrets` and stored only as a SHA-256 hash.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

import bcrypt
import jwt
from cryptography.fernet import Fernet

from app.core.config import settings


# --------------------------------------------------------------------------
# Password hashing
# --------------------------------------------------------------------------
def hash_password(plain_password: str) -> str:
    """Hash a plaintext password with bcrypt. Returns a utf-8 string."""
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------
# JWT (access tokens)
# --------------------------------------------------------------------------
class TokenType(str, Enum):
    ACCESS = "access"


def create_access_token(user_id: uuid.UUID | str) -> tuple[str, int]:
    """Create a short-lived access JWT. Returns (token, expires_in_seconds)."""
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": TokenType.ACCESS.value,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access JWT. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(
        token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
    )
    if payload.get("type") != TokenType.ACCESS.value:
        raise jwt.InvalidTokenError("Invalid token type")
    return payload


# --------------------------------------------------------------------------
# Refresh tokens (opaque, stored hashed)
# --------------------------------------------------------------------------
def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(raw_token: str) -> str:
    """Hash a refresh token for storage (SHA-256 hex digest)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_token_expiry(remember_me: bool = False) -> datetime:
    days = (
        settings.REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER_ME
        if remember_me
        else settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return datetime.now(timezone.utc) + timedelta(days=days)


# --------------------------------------------------------------------------
# Six-digit verification codes
# --------------------------------------------------------------------------
def generate_verification_code() -> str:
    """Generate a zero-padded 6-digit numeric code using `secrets`."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_code(code: str) -> str:
    """Hash a verification code for storage (SHA-256 hex digest)."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def verify_verification_code(code: str, code_hash: str) -> bool:
    return secrets.compare_digest(hash_verification_code(code), code_hash)


def verification_code_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.VERIFICATION_CODE_EXPIRE_MINUTES
    )


# --------------------------------------------------------------------------
# Proxy credentials (Boost Discord) — reversibly encrypted, not hashed,
# because the server must recover the plaintext to authenticate the client
# and to write 3proxy's users file.
# --------------------------------------------------------------------------
def _fernet() -> Fernet:
    return Fernet(settings.PROXY_CREDENTIALS_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_secret(plain_text: str) -> str:
    return _fernet().encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")


def generate_proxy_login(user_id: uuid.UUID) -> str:
    """A short, unique, colon-free login safe for 3proxy's `login:CL:password` file."""
    return f"bx{user_id.hex[:12]}"


def generate_proxy_password() -> str:
    """A colon-free, URL-safe secret (3proxy's users file is colon-delimited)."""
    return secrets.token_urlsafe(18)
