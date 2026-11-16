"""Smoke test: the FastAPI app builds and exposes the expected routes."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_app_builds() -> None:
    assert app.title == "Nexora Server"


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_payments_webhook_stub_returns_501() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/payments/webhook/lava")
    assert response.status_code == 501
    assert response.json() == {"detail": "Not implemented yet"}


def test_launcher_catalog_stub_returns_501() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/launcher/catalog")
    assert response.status_code == 501
    assert response.json() == {"detail": "Not implemented yet"}


def test_users_me_requires_auth() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
