"""Authentication endpoints.

Note: this module intentionally does NOT use `from __future__ import
annotations`. Several routes here are wrapped by slowapi's `@limiter.limit`
decorator, which resolves parameter annotations using the wrapper
function's own `__globals__` (not this module's). Under postponed
evaluation of annotations, that resolution fails silently and FastAPI
falls back to treating the Pydantic body model as a query parameter.
Keeping annotations "live" (evaluated at class/def time) sidesteps this.
"""
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.rate_limit import DEFAULT_AUTH_RATE_LIMIT, limiter
from app.models.user import User
from app.schemas.auth import (
    ChangeEmailConfirmRequest,
    ChangeEmailRequest,
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    PasswordResetConfirmSchema,
    PasswordResetRequestSchema,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.subscription import SubscriptionOut
from app.schemas.user import UserProfile
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(DEFAULT_AUTH_RATE_LIMIT)
async def register(
    request: Request, body: RegisterRequest, db: AsyncSession = Depends(get_db)
) -> RegisterResponse:
    service = AuthService(db)
    user_id = await service.register(body.username, body.email, body.password)
    return RegisterResponse(message="Registration successful. Check your email for a verification code.", user_id=user_id)


@router.post("/login", response_model=LoginResponse)
@limiter.limit(DEFAULT_AUTH_RATE_LIMIT)
async def login(
    request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    service = AuthService(db)
    access_token, refresh_token, expires_in, user, subscription = await service.login(
        body.email, body.password, body.remember_me, body.device
    )
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        user=UserProfile.model_validate(user),
        subscription=SubscriptionOut(
            plan=subscription.plan,
            status=subscription.status,
            current_period_end=subscription.current_period_end,
            started_at=subscription.created_at,
        ),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    service = AuthService(db)
    await service.logout(body.refresh_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> RefreshResponse:
    service = AuthService(db)
    access_token, refresh_token, expires_in = await service.refresh(body.refresh_token)
    return RefreshResponse(access_token=access_token, refresh_token=refresh_token, expires_in=expires_in)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)) -> MessageResponse:
    service = AuthService(db)
    await service.verify_email(body.email, body.code)
    return MessageResponse(message="Email verified successfully.")


@router.post("/resend-verification", response_model=MessageResponse)
@limiter.limit(DEFAULT_AUTH_RATE_LIMIT)
async def resend_verification(
    request: Request, body: ResendVerificationRequest, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    service = AuthService(db)
    await service.resend_verification(body.email)
    return MessageResponse(message="If an account with that email exists, a verification code has been sent.")


@router.post("/password-reset/request", response_model=MessageResponse)
@limiter.limit(DEFAULT_AUTH_RATE_LIMIT)
async def password_reset_request(
    request: Request, body: PasswordResetRequestSchema, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    service = AuthService(db)
    await service.request_password_reset(body.email)
    return MessageResponse(message="If an account with that email exists, a password reset code has been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(
    body: PasswordResetConfirmSchema, db: AsyncSession = Depends(get_db)
) -> MessageResponse:
    service = AuthService(db)
    await service.confirm_password_reset(body.email, body.code, body.new_password)
    return MessageResponse(message="Password reset successfully. Please log in again.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    service = AuthService(db)
    await service.change_password(current_user, body.current_password, body.new_password)
    return MessageResponse(message="Password changed successfully.")


@router.post("/change-email/request", response_model=MessageResponse)
@limiter.limit(DEFAULT_AUTH_RATE_LIMIT)
async def change_email_request(
    request: Request,
    body: ChangeEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    service = AuthService(db)
    await service.request_email_change(current_user, body.new_email)
    return MessageResponse(message="A confirmation code has been sent to your new email address.")


@router.post("/change-email/confirm", response_model=MessageResponse)
async def change_email_confirm(
    body: ChangeEmailConfirmRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    service = AuthService(db)
    await service.confirm_email_change(current_user, body.code)
    return MessageResponse(message="Email address updated successfully.")
