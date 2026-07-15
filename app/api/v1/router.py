"""Aggregates all v1 sub-routers under a single APIRouter mounted at /api/v1."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, devices, health, launcher, payments, proxy, subscriptions, users, vpn

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(subscriptions.router)
api_router.include_router(devices.router)
api_router.include_router(payments.router)
api_router.include_router(launcher.router)
api_router.include_router(proxy.router)
api_router.include_router(vpn.router)
