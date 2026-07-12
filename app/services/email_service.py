"""Email sending service.

Supports two backends, selected via EMAIL_BACKEND:
- "smtp": sends real email asynchronously via aiosmtplib.
- "console": logs the message instead of sending (local dev without SMTP creds).
"""
from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailService:
    async def send(self, to_email: str, subject: str, body: str) -> None:
        if settings.EMAIL_BACKEND == "console":
            logger.info("[console-email] to=%s subject=%r body=%r", to_email, subject, body)
            return
        await self._send_smtp(to_email, subject, body)

    async def _send_smtp(self, to_email: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        await aiosmtplib.send(
            message,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_USE_TLS,
        )

    async def send_verification_code(self, to_email: str, code: str) -> None:
        await self.send(
            to_email,
            subject="Your BoostX verification code",
            body=f"Your BoostX verification code is: {code}\n\nThis code expires in "
            f"{settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes. "
            "If you did not request this, you can safely ignore this email.",
        )

    async def send_password_reset_code(self, to_email: str, code: str) -> None:
        await self.send(
            to_email,
            subject="Reset your BoostX password",
            body=f"Your BoostX password reset code is: {code}\n\nThis code expires in "
            f"{settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes. "
            "If you did not request this, you can safely ignore this email.",
        )

    async def send_email_change_code(self, to_email: str, code: str) -> None:
        await self.send(
            to_email,
            subject="Confirm your new BoostX email address",
            body=f"Your BoostX email change confirmation code is: {code}\n\nThis code expires "
            f"in {settings.VERIFICATION_CODE_EXPIRE_MINUTES} minutes. "
            "If you did not request this, you can safely ignore this email.",
        )


email_service = EmailService()
