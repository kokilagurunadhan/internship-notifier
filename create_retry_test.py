
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification


async def main():

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # Get your existing Microsoft subscription
        # ----------------------------------------------------

        result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_email
                == "kokilasudha9363@gmail.com",
                Subscription.company.ilike("microsoft"),
                Subscription.is_active.is_(True),
            )
            .limit(1)
        )

        subscription = result.scalar_one_or_none()

        if not subscription:
            print("❌ Microsoft subscription not found.")
            return

        # ----------------------------------------------------
        # Create NEW test internship
        # ----------------------------------------------------

        now = datetime.now(timezone.utc)

        internship = Internship(
            company="Microsoft",
            title="Dispatcher Retry Test Internship 2",
            location="Remote",
            url="https://example.com/dispatcher-retry-test-3",
            description=(
                "Test internship used to verify "
                "notification dispatcher retry handling."
            ),
            source="TEST",
            via="TEST",
            relevance_score=80.0,
            passed_filter=True,
            status="RELEVANT",
            email_sent=False,
            created_at=now,
            last_seen_at=now,
        )

        db.add(internship)

        await db.flush()

        # ----------------------------------------------------
        # Create PENDING notification
        # ----------------------------------------------------

        notification = Notification(
            subscription_id=subscription.id,
            user_email=subscription.user_email,
            internship_id=internship.id,
            status="PENDING",
            relevance_score=80.0,
            retry_count=0,
            created_at=now,
            updated_at=now,
            next_retry_at=None,
            error_message=None,
        )

        db.add(notification)

        await db.commit()

        print()
        print("=" * 60)
        print("✅ RETRY TEST DATA CREATED")
        print("=" * 60)
        print(f"Internship ID   : {internship.id}")
        print(f"Notification ID : {notification.id}")
        print(f"Email           : {subscription.user_email}")
        print(f"Status          : {notification.status}")
        print(f"Score           : {notification.relevance_score}")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
