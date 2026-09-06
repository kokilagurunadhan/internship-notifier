import asyncio

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)
from app.services.notification_dispatcher import (
    _mark_notifications_failed,
)


async def main():

    async with AsyncSessionLocal() as db:

        # --------------------------------------------------
        # FIND EXISTING RECORDS FOR FOREIGN KEYS
        # --------------------------------------------------

        subscription_result = await db.execute(
            select(Subscription).limit(1)
        )

        subscription = (
            subscription_result.scalar_one_or_none()
        )

        internship_result = await db.execute(
            select(Internship).limit(1)
        )

        internship = (
            internship_result.scalar_one_or_none()
        )

        if not subscription or not internship:
            print(
                "ERROR: Need at least one subscription "
                "and one internship in database."
            )
            return

        # --------------------------------------------------
        # CREATE TEMPORARY NOTIFICATION
        # --------------------------------------------------

        notification = Notification(
            subscription_id=subscription.id,
            user_email="retry_test@example.com",
            internship_id=internship.id,
            status=NotificationStatus.PENDING,
            retry_count=0,
        )

        db.add(notification)

        await db.commit()
        await db.refresh(notification)

        print("=" * 50)
        print("RETRY BEHAVIOR TEST")
        print("=" * 50)

        print("Notification ID :", notification.id)
        print("Starting retry  :", notification.retry_count)

        # --------------------------------------------------
        # SIMULATE 5 FAILURES
        # --------------------------------------------------

        for attempt in range(1, 6):

            notification.status = (
                NotificationStatus.PROCESSING
            )

            await db.commit()
            await db.refresh(notification)

            await _mark_notifications_failed(
                db,
                [notification],
                ValueError("TEST EMAIL FAILURE"),
            )

            await db.refresh(notification)

            print(
                f"Attempt {attempt}: "
                f"retry={notification.retry_count}, "
                f"status={notification.status}, "
                f"next_retry="
                f"{notification.next_retry_at}"
            )

        # --------------------------------------------------
        # VERIFY
        # --------------------------------------------------

        print()
        print("VERIFYING")
        print("-" * 50)

        if notification.retry_count == 5:
            print("PASS: retry count reached 5")
        else:
            print(
                "FAIL: retry count is",
                notification.retry_count,
            )

        if notification.status == NotificationStatus.FAILED:
            print("PASS: notification became FAILED")
        else:
            print(
                "FAIL: final status is",
                notification.status,
            )

        if notification.next_retry_at is None:
            print(
                "PASS: no retry scheduled after "
                "permanent failure"
            )
        else:
            print(
                "FAIL: retry still scheduled:",
                notification.next_retry_at,
            )

        # --------------------------------------------------
        # CLEANUP
        # --------------------------------------------------

        await db.execute(
            delete(Notification).where(
                Notification.id == notification.id
            )
        )

        await db.commit()

        print()
        print("PASS: temporary notification deleted")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())