import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification, NotificationStatus

TEST_EMAILS = [
    "test@example.com",
    "claim-test@example.com",
    "notification-race-test@example.com",
    "kokilasudha9363@gmail.com",
]

async def main():

    async with AsyncSessionLocal() as db:

        print("\n=== TEST SUBSCRIPTIONS ===\n")

        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_email.in_(TEST_EMAILS))
            .order_by(Subscription.id)
        )

        subscriptions = result.scalars().all()

        for s in subscriptions:
            print(
                f"id={s.id} | "
                f"user={s.user_email} | "
                f"company={s.company} | "
                f"domain={s.domain} | "
                f"active={s.is_active}"
            )

        print("\n=== TEST NOTIFICATIONS ===\n")

        result = await db.execute(
            select(Notification)
            .where(Notification.user_email.in_(TEST_EMAILS))
            .order_by(Notification.id)
        )

        notifications = result.scalars().all()

        for n in notifications:
            print(
                f"id={n.id} | "
                f"user={n.user_email} | "
                f"internship={n.internship_id} | "
                f"status={n.status} | "
                f"retry={n.retry_count}"
            )

asyncio.run(main())
