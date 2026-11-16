"""Subscription business logic."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.models.subscription import Subscription
from app.repositories.subscription_repository import SubscriptionRepository


class SubscriptionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.subscription_repo = SubscriptionRepository(session)

    async def get_for_user(self, user_id: uuid.UUID) -> Subscription:
        subscription = await self.subscription_repo.get_by_user_id(user_id)
        if subscription is None:
            # Should never happen — a subscription is created at registration —
            # but guard defensively rather than 500ing.
            raise NotFoundException("Subscription not found")
        return subscription
