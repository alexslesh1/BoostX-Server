"""Auth request/response schemas."""
from __future__ import annotations

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.device import DeviceIn
from app.schemas.subscription import SubscriptionOut
from app.schemas.user import UserProfile


# --- Register ---
class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    message: str
    user_id: uuid.UUID


# --- Login ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    remember_me: bool = False
    device: DeviceIn


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile
    subscription: SubscriptionOut


# --- Logout ---
class LogoutRequest(BaseModel):
    refresh_token: str


# --- Refresh ---
class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# --- Email verification ---
class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


# --- Password reset ---
class PasswordResetRequestSchema(BaseModel):
    email: EmailStr


class PasswordResetConfirmSchema(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=128)


# --- Change password (authenticated) ---
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


# --- Change email (authenticated) ---
class ChangeEmailRequest(BaseModel):
    new_email: EmailStr


class ChangeEmailConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)
