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
    _claim_pending_notifications,
    _utc_now,
)


async def main():

    async with AsyncSessionLocal() as db:

        # ---------------------------------------------
        # FIND VALID FOREIGN KEY RECORDS
        # ---------------------------------------------

        subscription_result = await db.execute(
            select(Subscription).limit(1)
        )
        subscription = subscription_result.scalar_one_or_none()

        internship_result = await db.execute(
            select(Internship).limit(1)
        )
        internship = internship_result.scalar_one_or_none()

        if not subscription or not internship:
            print("ERROR: Need subscription + internship.")
            return

        # ---------------------------------------------
        # CREATE ONE READY PENDING NOTIFICATION
        # ---------------------------------------------

        notification = Notification(
            subscription_id=subscription.id,
            user_email="claim_test@example.com",
            internship_id=internship.id,
            status=NotificationStatus.PENDING,
            retry_count=0,
            next_retry_at=None,
        )

        db.add(notification)

        await db.commit()
        await db.refresh(notification)

        notification_id = notification.id

        print("=" * 50)
        print("DISPATCHER CLAIM TEST")
        print("=" * 50)

        print("Notification ID :", notification_id)
        print("Initial status  :", notification.status)

        # ---------------------------------------------
        # FIRST CLAIM
        # ---------------------------------------------

        first_claim = await _claim_pending_notifications(
            db,
            batch_size=1,
        )

        await db.refresh(notification)

        print()
        print("FIRST CLAIM")
        print("-" * 50)

        print("Claimed IDs :", first_claim)
        print("Status     :", notification.status)

        # ---------------------------------------------
        # SECOND CLAIM
        # ---------------------------------------------

        second_claim = await _claim_pending_notifications(
            db,
            batch_size=1,
        )

        await db.refresh(notification)

        print()
        print("SECOND CLAIM")
        print("-" * 50)

        print("Claimed IDs :", second_claim)
        print("Status     :", notification.status)

        # ---------------------------------------------
        # VERIFY
        # ---------------------------------------------

        print()
        print("VERIFYING")
        print("-" * 50)

        if notification_id in first_claim:
            print(
                "PASS: first claim successfully claimed notification"
            )
        else:
            print(
                "FAIL: first claim did not claim notification"
            )

        if (
            notification.status
            == NotificationStatus.PROCESSING
        ):
            print(
                "PASS: notification changed PENDING -> PROCESSING"
            )
        else:
            print(
                "FAIL: notification status is",
                notification.status,
            )

        if not second_claim:
            print(
                "PASS: second claim could not claim same notification"
            )
        else:
            print(
                "FAIL: duplicate claim occurred:",
                second_claim,
            )

        if notification.processing_started_at is not None:
            print(
                "PASS: processing lease timestamp created"
            )
        else:
            print(
                "FAIL: processing lease timestamp missing"
            )

        if notification.next_retry_at is None:
            print(
                "PASS: retry timestamp cleared during claim"
            )
        else:
            print(
                "FAIL: next_retry_at still exists"
            )

        # ---------------------------------------------
        # CLEANUP
        # ---------------------------------------------

        await db.execute(
            delete(Notification).where(
                Notification.id == notification_id
            )
        )

        await db.commit()

        print()
        print(
            "PASS: temporary notification deleted"
        )

        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())