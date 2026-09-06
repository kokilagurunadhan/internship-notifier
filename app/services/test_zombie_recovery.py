import asyncio

from datetime import timedelta

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)
from app.services.notification_dispatcher import (
    _recover_zombie_notifications,
    _utc_now,
)


async def main():

    async with AsyncSessionLocal() as db:

        # --------------------------------------------------
        # FIND EXISTING FOREIGN KEY RECORDS
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
                "and one internship."
            )
            return

        # --------------------------------------------------
        # CREATE FAKE ZOMBIE
        # --------------------------------------------------

        notification = Notification(
            subscription_id=subscription.id,
            user_email="zombie_test@example.com",
            internship_id=internship.id,
            status=NotificationStatus.PROCESSING,
            retry_count=0,
            processing_started_at=(
                _utc_now()
                - timedelta(minutes=20)
            ),
        )

        db.add(notification)

        await db.commit()
        await db.refresh(notification)

        notification_id = notification.id

        print("=" * 50)
        print("ZOMBIE RECOVERY TEST")
        print("=" * 50)

        print(
            "Notification ID       :",
            notification_id,
        )

        print(
            "Initial status        :",
            notification.status,
        )

        print(
            "Initial retry count   :",
            notification.retry_count,
        )

        print(
            "Processing started at :",
            notification.processing_started_at,
        )

        # --------------------------------------------------
        # RUN REAL ZOMBIE RECOVERY
        # --------------------------------------------------

        recovered_ids = (
            await _recover_zombie_notifications(
                db,
                timeout_minutes=15,
                max_retries=5,
                batch_size=50,
            )
        )

        await db.refresh(notification)

        print()
        print("RECOVERY RESULT")
        print("-" * 50)

        print(
            "Recovered IDs :",
            recovered_ids,
        )

        print(
            "Final status  :",
            notification.status,
        )

        print(
            "Retry count   :",
            notification.retry_count,
        )

        print(
            "Processing at :",
            notification.processing_started_at,
        )

        print(
            "Next retry    :",
            notification.next_retry_at,
        )

        print(
            "Error message :",
            notification.error_message,
        )

        # --------------------------------------------------
        # VERIFY
        # --------------------------------------------------

        print()
        print("VERIFYING")
        print("-" * 50)

        if notification_id in recovered_ids:
            print(
                "PASS: zombie notification was recovered"
            )
        else:
            print(
                "FAIL: notification was not recovered"
            )

        if (
            notification.status
            == NotificationStatus.PENDING
        ):
            print(
                "PASS: status changed PROCESSING -> PENDING"
            )
        else:
            print(
                "FAIL: status is",
                notification.status,
            )

        if notification.retry_count == 1:
            print(
                "PASS: retry count incremented to 1"
            )
        else:
            print(
                "FAIL: retry count is",
                notification.retry_count,
            )

        if notification.processing_started_at is None:
            print(
                "PASS: processing lease cleared"
            )
        else:
            print(
                "FAIL: processing lease still exists"
            )

        if notification.next_retry_at is not None:
            print(
                "PASS: retry scheduled immediately"
            )
        else:
            print(
                "FAIL: next retry was not scheduled"
            )

        if (
            notification.error_message
            == "Notification recovered after "
               "worker processing timeout."
        ):
            print(
                "PASS: recovery error message recorded"
            )
        else:
            print(
                "FAIL: unexpected error message:",
                notification.error_message,
            )

        # --------------------------------------------------
        # CLEANUP
        # --------------------------------------------------

        await db.execute(
            delete(Notification).where(
                Notification.id == notification_id
            )
        )

        await db.commit()

        print()
        print(
            "PASS: temporary zombie notification deleted"
        )

        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())