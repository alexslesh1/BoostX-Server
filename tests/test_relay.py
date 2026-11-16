"""Relay sessions: token format and the /relay/session endpoint."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import sign_relay_token
from app.db.base import Base
from app.main import app
from app.repositories.device_repository import DeviceRepository

SECRET = bytes(range(32))
USER_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")
SERVERS = [
    {
        "id": "fra1",
        "name": "Frankfurt",
        "region": "EU",
        "address": "203.0.113.10:4700",
        "public_key": "UCKWD3U9TujTSy5dm0B1iKzYgnkD6E/EvwFrZMLYHBI=",
    },
    {
        "id": "sto1",
        "name": "Stockholm",
        "address": "203.0.113.20:4700",
        "public_key": "UCKWD3U9TujTSy5dm0B1iKzYgnkD6E/EvwFrZMLYHBI=",
    },
]


def _unpad_b64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _verify(token: str, secret: bytes) -> dict:
    """What a relay does: check the signature over the first part, then
    read the claims from it."""
    encoded, signature = token.split(".")
    expected = hmac.new(secret, encoded.encode("ascii"), hashlib.sha256).digest()
    assert hmac.compare_digest(_unpad_b64url(signature), expected), "signature does not verify"
    return json.loads(_unpad_b64url(encoded))


def test_relay_token_carries_user_device_and_expiry_and_verifies() -> None:
    token = sign_relay_token(SECRET, USER_ID, "device-1", 1_900_000_000)

    assert "=" not in token, "relays expect unpadded base64url"
    assert _verify(token, SECRET) == {"uid": str(USER_ID), "dev": "device-1", "exp": 1_900_000_000}


def test_relay_token_matches_the_vector_pinned_in_the_relay_tests() -> None:
    # The same string is checked by nexora-core/proto (TestTokenFromBackend),
    # so a change to either side's format fails a test on that side.
    assert sign_relay_token(SECRET, USER_ID, "device-1", 4_102_444_800) == (
        "eyJ1aWQiOiIxMTExMTExMS0yMjIyLTMzMzMtNDQ0NC01NTU1NTU1NTU1NTUiLCJkZXYiOiJkZXZpY2UtMSIsImV4cCI6NDEwMjQ0NDgwMH0"
        "." + _EXPECTED_VECTOR_SIGNATURE
    )


_EXPECTED_VECTOR_SIGNATURE = "WULqx2cKjNC_Z75fRrCvSkJgo0J2iNRUWKR27huKZkA"


def test_relay_token_signed_with_another_secret_does_not_verify() -> None:
    token = sign_relay_token(b"x" * 32, USER_ID, "device-1", 1_900_000_000)
    with pytest.raises(AssertionError):
        _verify(token, SECRET)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    registered = {"device-1"}

    async def fake_get_by_device_id(self, user_id: uuid.UUID, device_id: str):
        if user_id == USER_ID and device_id in registered:
            return SimpleNamespace(device_id=device_id)
        return None

    async def fake_db():
        yield None

    monkeypatch.setattr(DeviceRepository, "get_by_device_id", fake_get_by_device_id)
    monkeypatch.setattr(settings, "RELAY_SERVERS", json.dumps(SERVERS))
    monkeypatch.setattr(settings, "RELAY_TOKEN_SECRET", base64.b64encode(SECRET).decode())
    monkeypatch.setattr(settings, "RELAY_TOKEN_TTL_SECONDS", 3600)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_ID)
    app.dependency_overrides[get_db] = fake_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_session_requires_auth() -> None:
    response = TestClient(app).post("/api/v1/relay/session", json={"device_id": "device-1"})
    assert response.status_code == 401


def test_session_returns_servers_and_a_token_relays_accept(client: TestClient) -> None:
    before = int(time.time())
    response = client.post("/api/v1/relay/session", json={"device_id": "device-1"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert [s["id"] for s in body["servers"]] == ["fra1", "sto1"]
    assert body["servers"][0]["address"] == "203.0.113.10:4700"
    assert body["servers"][1]["region"] == ""

    claims = _verify(body["token"], SECRET)
    assert claims["uid"] == str(USER_ID)
    assert claims["dev"] == "device-1"
    assert claims["exp"] == body["expires_at"]
    assert before + 3600 <= body["expires_at"] <= int(time.time()) + 3600


def test_session_refused_for_a_device_the_account_does_not_have(client: TestClient) -> None:
    response = client.post("/api/v1/relay/session", json={"device_id": "removed-device"})
    assert response.status_code == 403
    assert "token" not in response.text


def test_session_needs_a_device_id(client: TestClient) -> None:
    assert client.post("/api/v1/relay/session", json={}).status_code == 422
    assert client.post("/api/v1/relay/session", json={"device_id": ""}).status_code == 422


@pytest.mark.parametrize(
    ("setting", "value"),
    [
        ("RELAY_TOKEN_SECRET", ""),
        ("RELAY_TOKEN_SECRET", "not base64 !!"),
        ("RELAY_TOKEN_SECRET", base64.b64encode(b"short").decode()),
        ("RELAY_SERVERS", "[]"),
        ("RELAY_SERVERS", "{broken"),
        ("RELAY_SERVERS", json.dumps([{"id": "x", "name": "no address or key"}])),
    ],
)
def test_session_unavailable_until_relays_are_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, setting: str, value: str
) -> None:
    monkeypatch.setattr(settings, setting, value)
    response = client.post("/api/v1/relay/session", json={"device_id": "device-1"})
    assert response.status_code == 503
    assert "token" not in response.text


def test_wireguard_is_gone() -> None:
    assert TestClient(app).get("/api/v1/vpn/config").status_code == 404
    assert "wireguard_peers" not in Base.metadata.tables
    assert not [name for name in type(settings).model_fields if "WIREGUARD" in name]
