"""Subscription endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.subscription import SubscriptionOut
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/me", response_model=SubscriptionOut)
async def get_my_subscription(
    db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
) -> SubscriptionOut:
    service = SubscriptionService(db)
    subscription = await service.get_for_user(current_user.id)
    return SubscriptionOut(
        plan=subscription.plan,
        status=subscription.status,
        current_period_end=subscription.current_period_end,
        started_at=subscription.created_at,
    )
