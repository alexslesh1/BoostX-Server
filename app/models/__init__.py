"""SQLAlchemy ORM models. Import all models here so that `Base.metadata`
(used by Alembic autogenerate and `create_all` in tests) is aware of every
table.
"""
from app.models.device import Device
from app.models.proxy_credential import ProxyCredential
from app.models.refresh_token import RefreshToken
from app.models.subscription import Subscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User
from app.models.verification_code import VerificationCode, VerificationPurpose

__all__ = [
    "Device",
    "ProxyCredential",
    "RefreshToken",
    "Subscription",
    "SubscriptionPlan",
    "SubscriptionStatus",
    "User",
    "VerificationCode",
    "VerificationPurpose",
]
