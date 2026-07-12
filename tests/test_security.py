"""Unit tests for app.core.security: password hashing, JWT round-trip, codes."""
from __future__ import annotations

import uuid

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    generate_verification_code,
    hash_password,
    hash_refresh_token,
    hash_verification_code,
    verify_password,
    verify_verification_code,
)


def test_password_hash_and_verify_roundtrip() -> None:
    plain = "correct horse battery staple"
    hashed = hash_password(plain)

    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_password_hash_is_salted_and_unique() -> None:
    plain = "same-password"
    hash_a = hash_password(plain)
    hash_b = hash_password(plain)
    assert hash_a != hash_b
    assert verify_password(plain, hash_a)
    assert verify_password(plain, hash_b)


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token, expires_in = create_access_token(user_id)

    assert expires_in == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "exp" in payload and "iat" in payload


def test_access_token_rejects_tampering() -> None:
    user_id = uuid.uuid4()
    token, _ = create_access_token(user_id)

    # Flip a character in the middle of the signature segment. (Flipping only
    # the very last character is unreliable: base64url's trailing quantum can
    # have "don't-care" bits, so some substitutions decode to identical bytes
    # and leave the signature valid.)
    header, payload, signature = token.split(".")
    mid = len(signature) // 2
    flipped_char = "A" if signature[mid] != "A" else "B"
    tampered_signature = signature[:mid] + flipped_char + signature[mid + 1 :]
    tampered = f"{header}.{payload}.{tampered_signature}"

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(tampered)


def test_refresh_token_is_opaque_and_hashed() -> None:
    raw = generate_refresh_token()
    hashed = hash_refresh_token(raw)

    assert raw != hashed
    # Hashing must be deterministic so we can look tokens up by hash.
    assert hash_refresh_token(raw) == hashed


def test_verification_code_format_and_hash_roundtrip() -> None:
    code = generate_verification_code()
    assert len(code) == 6
    assert code.isdigit()

    code_hash = hash_verification_code(code)
    assert code_hash != code
    assert verify_verification_code(code, code_hash) is True
    assert verify_verification_code("000000" if code != "000000" else "111111", code_hash) is False
