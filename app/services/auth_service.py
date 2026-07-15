"""Authentication business logic — registration, login, verification codes,
password reset/change, and email change. Orchestrates the repositories.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_verification_code,
    hash_password,
    hash_verification_code,
    verify_password,
    verify_verification_code,
    verification_code_expiry,
)
from app.exceptions import BadRequestException, ConflictException, UnauthorizedException
from app.models.subscription import Subscription
from app.models.user import User
from app.models.verification_code import VerificationCode, VerificationPurpose
from app.repositories.device_repository import DeviceRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.verification_repository import VerificationRepository
from app.schemas.device import DeviceIn
from app.services.email_service import email_service
from app.services.proxy_service import ProxyService
from app.services.token_service import TokenService
from app.services.wireguard_service import WireguardService


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        self.device_repo = DeviceRepository(session)
        self.verification_repo = VerificationRepository(session)
        self.token_service = TokenService(session)
        self.proxy_service = ProxyService(session)
        self.wireguard_service = WireguardService(session)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register(self, username: str, email: str, password: str) -> uuid.UUID:
        if await self.user_repo.get_by_email(email) is not None:
            raise ConflictException("Email already registered")
        if await self.user_repo.get_by_username(username) is not None:
            raise ConflictException("Username already taken")

        password_hash = hash_password(password)
        user = await self.user_repo.create(username, email, password_hash)
        await self.subscription_repo.create_default(user.id)
        await self.proxy_service.provision_for_user(user.id)
        await self.wireguard_service.provision_for_user(user.id)
        await self._issue_and_send_code(user, VerificationPurpose.EMAIL_VERIFY)

        await self.session.commit()
        # Credentials/peers are only useful once committed — sync the
        # 3proxy users file and wg0.conf after the transaction succeeds,
        # not before. A sync failure here is logged and self-heals on the
        # next sync, never blocks registration.
        await self.proxy_service.sync_users_file()
        await self.wireguard_service.sync_config_file()
        return user.id

    # ------------------------------------------------------------------
    # Login / logout / refresh
    # ------------------------------------------------------------------
    async def login(
        self, email: str, password: str, remember_me: bool, device: DeviceIn
    ) -> tuple[str, str, int, User, Subscription | None]:
        user = await self.user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedException("Invalid email or password")

        await self.device_repo.upsert(user.id, device.device_id, device.device_name, device.os)
        await self.user_repo.update_last_login(user)

        access_token, refresh_token, expires_in = await self.token_service.issue_tokens(
            user.id, device_id=device.device_id, remember_me=remember_me
        )
        subscription = await self.subscription_repo.get_by_user_id(user.id)

        await self.session.commit()
        return access_token, refresh_token, expires_in, user, subscription

    async def logout(self, raw_refresh_token: str) -> None:
        await self.token_service.revoke_refresh_token(raw_refresh_token)
        await self.session.commit()

    async def refresh(self, raw_refresh_token: str) -> tuple[str, str, int]:
        result = await self.token_service.rotate_refresh_token(raw_refresh_token)
        await self.session.commit()
        return result

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------
    async def verify_email(self, email: str, code: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if user is None:
            raise BadRequestException("Invalid or expired code")

        vcode = await self.verification_repo.get_latest_active(
            user.id, VerificationPurpose.EMAIL_VERIFY
        )
        self._assert_code_valid(vcode, code)
        await self.verification_repo.consume(vcode)  # type: ignore[arg-type]
        await self.user_repo.set_email_verified(user, True)
        await self.session.commit()

    async def resend_verification(self, email: str) -> None:
        """Always succeeds from the caller's perspective (anti-enumeration)."""
        user = await self.user_repo.get_by_email(email)
        if user is not None and not user.email_verified:
            await self._issue_and_send_code(user, VerificationPurpose.EMAIL_VERIFY)
            await self.session.commit()

    # ------------------------------------------------------------------
    # Password reset (unauthenticated)
    # ------------------------------------------------------------------
    async def request_password_reset(self, email: str) -> None:
        """Always succeeds from the caller's perspective (anti-enumeration)."""
        user = await self.user_repo.get_by_email(email)
        if user is not None:
            await self._issue_and_send_code(user, VerificationPurpose.PASSWORD_RESET)
            await self.session.commit()

    async def confirm_password_reset(self, email: str, code: str, new_password: str) -> None:
        user = await self.user_repo.get_by_email(email)
        if user is None:
            raise BadRequestException("Invalid or expired code")

        vcode = await self.verification_repo.get_latest_active(
            user.id, VerificationPurpose.PASSWORD_RESET
        )
        self._assert_code_valid(vcode, code)
        await self.verification_repo.consume(vcode)  # type: ignore[arg-type]
        await self.user_repo.set_password(user, hash_password(new_password))
        await self.token_service.revoke_all_for_user(user.id)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Change password (authenticated)
    # ------------------------------------------------------------------
    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedException("Current password is incorrect")
        await self.user_repo.set_password(user, hash_password(new_password))
        await self.session.commit()

    # ------------------------------------------------------------------
    # Change email (authenticated)
    # ------------------------------------------------------------------
    async def request_email_change(self, user: User, new_email: str) -> None:
        existing = await self.user_repo.get_by_email(new_email)
        if existing is not None:
            raise ConflictException("Email already in use")
        await self._issue_and_send_code(
            user, VerificationPurpose.EMAIL_CHANGE, target_email=new_email.lower()
        )
        await self.session.commit()

    async def confirm_email_change(self, user: User, code: str) -> None:
        vcode = await self.verification_repo.get_latest_active(
            user.id, VerificationPurpose.EMAIL_CHANGE
        )
        self._assert_code_valid(vcode, code)
        if vcode is None or vcode.target_email is None:  # pragma: no cover - guarded above
            raise BadRequestException("Invalid or expired code")
        await self.verification_repo.consume(vcode)
        await self.user_repo.update_email(user, vcode.target_email)
        await self.session.commit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _issue_and_send_code(
        self,
        user: User,
        purpose: VerificationPurpose,
        target_email: str | None = None,
    ) -> None:
        await self.verification_repo.invalidate_active(user.id, purpose)
        code = generate_verification_code()
        code_hash = hash_verification_code(code)
        expires_at = verification_code_expiry()
        await self.verification_repo.create(user.id, purpose, code_hash, expires_at, target_email)

        destination = target_email or user.email
        if purpose == VerificationPurpose.EMAIL_VERIFY:
            await email_service.send_verification_code(destination, code)
        elif purpose == VerificationPurpose.PASSWORD_RESET:
            await email_service.send_password_reset_code(destination, code)
        elif purpose == VerificationPurpose.EMAIL_CHANGE:
            await email_service.send_email_change_code(destination, code)

    @staticmethod
    def _assert_code_valid(vcode: VerificationCode | None, code: str) -> None:
        if vcode is None:
            raise BadRequestException("Invalid or expired code")
        if vcode.expires_at < datetime.now(timezone.utc):
            raise BadRequestException("Invalid or expired code")
        if not verify_verification_code(code, vcode.code_hash):
            raise BadRequestException("Invalid or expired code")
