"""Subscription response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.subscription import SubscriptionPlan, SubscriptionStatus


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: SubscriptionPlan
    status: SubscriptionStatus
    current_period_end: datetime | None = None
    started_at: datetime
