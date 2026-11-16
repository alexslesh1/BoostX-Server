"""Creates (or resets) a ready-to-use test account: email already
verified, active paid subscription, fresh password printed once.

    docker compose exec app python -m app.scripts.create_test_account
    docker compose exec app python -m app.scripts.create_test_account \\
        --email tester@example.com --plan lifetime

Running it again for the same email resets the password and the
subscription; nothing else about the account changes.
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.subscription import SubscriptionPlan, SubscriptionStatus
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.user_repository import UserRepository


async def create_or_reset(email: str, username: str, plan: SubscriptionPlan, days: int, password: str) -> bool:
    """Returns True if the account was created, False if it was reset."""
    async with AsyncSessionLocal() as session:
        users = UserRepository(session)
        subscriptions = SubscriptionRepository(session)

        user = await users.get_by_email(email)
        created = user is None
        if created:
            if await users.get_by_username(username) is not None:
                raise SystemExit(f"username {username!r} is taken by another account; pass --username")
            user = await users.create(username, email, hash_password(password))
        else:
            await users.set_password(user, hash_password(password))
        await users.set_email_verified(user, True)
        user.is_active = True

        subscription = await subscriptions.get_by_user_id(user.id)
        if subscription is None:
            subscription = await subscriptions.create_default(user.id)
        subscription.plan = plan
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.current_period_end = (
            None if plan == SubscriptionPlan.LIFETIME else datetime.now(timezone.utc) + timedelta(days=days)
        )
        await session.commit()
        return created


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", default="tester@example.com")
    parser.add_argument("--username", default="tester")
    parser.add_argument("--plan", choices=["pro", "lifetime"], default="pro")
    parser.add_argument("--days", type=int, default=30, help="length of a pro subscription")
    args = parser.parse_args()

    password = secrets.token_urlsafe(9)
    created = asyncio.run(
        create_or_reset(args.email.lower(), args.username, SubscriptionPlan(args.plan), args.days, password)
    )
    period = "no end" if args.plan == "lifetime" else f"{args.days} days"
    print(f"{'Created' if created else 'Reset'} test account")
    print(f"  email:        {args.email.lower()}")
    print(f"  password:     {password}")
    print(f"  subscription: {args.plan}, active, {period}")


if __name__ == "__main__":
    main()
