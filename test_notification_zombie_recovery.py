import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification, NotificationStatus
from app.services.notification_dispatcher import (
    _recover_zombie_notifications,
    PROCESSING_TIMEOUT_MINUTES,
)


TEST_EMAIL = "kokilasudha9363@gmail.com"
TEST_COMPANY = "microsoft"


def utc_now():
    return datetime.now(timezone.utc)


async def main():

    print()
    print("=" * 70)
    print("NOTIFICATION ZOMBIE RECOVERY TEST")
    print("=" * 70)

    notification_id = None
    internship_id = None
    subscription_id = None

    try:

        # ============================================================
        # FIND OR CREATE TEST SUBSCRIPTION
        # ============================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Subscription)
                .where(
                    Subscription.user_email == TEST_EMAIL,
                    Subscription.company == TEST_COMPANY,
                )
                .limit(1)
            )

            subscription = result.scalar_one_or_none()

            if subscription:

                print()
                print(
                    f"Subscription found: "
                    f"{subscription.user_email}"
                )

                print(
                    f"Subscription ID: "
                    f"{subscription.id}"
                )

                print(
                    f"Company: "
                    f"{subscription.company}"
                )

                print(
                    f"Domain: "
                    f"{subscription.domain}"
                )

            else:

                print()
                print(
                    "⚠️ Test subscription not found."
                )

                print(
                    "📦 Creating test subscription..."
                )

                subscription = Subscription(
                    user_email=TEST_EMAIL,
                    company=TEST_COMPANY,
                    domain="software",
                    is_active=True,
                    created_at=utc_now(),
                )

                db.add(subscription)

                await db.flush()

                subscription_id = subscription.id

                print(
                    f"✅ Test subscription created: "
                    f"ID={subscription.id}"
                )

            # ========================================================
            # CREATE TEST INTERNSHIP
            # ========================================================

            internship = Internship(
                company=TEST_COMPANY,
                title="Zombie Recovery Test Internship",
                location="Remote",
                url=(
                    "https://example.com/"
                    "zombie-recovery-test-"
                    + str(utc_now().timestamp())
                ),
                description=(
                    "Test internship for notification "
                    "zombie recovery."
                ),
                source="TEST",
                via="TEST",
                relevance_score=80.0,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
                created_at=utc_now(),
                last_seen_at=utc_now(),
            )

            db.add(internship)

            await db.flush()

            internship_id = internship.id

            print()
            print(
                f"Test internship created: "
                f"ID={internship_id}"
            )

            # ========================================================
            # CREATE ZOMBIE NOTIFICATION
            # ========================================================

            old_processing_time = (
                utc_now()
                - timedelta(
                    minutes=PROCESSING_TIMEOUT_MINUTES + 10
                )
            )

            notification = Notification(
                subscription_id=subscription.id,
                user_email=subscription.user_email,
                internship_id=internship.id,
                status=NotificationStatus.PROCESSING,
                relevance_score=80.0,
                created_at=utc_now(),
                updated_at=utc_now(),
                sent_at=None,
                processing_started_at=old_processing_time,
                idempotency_key=None,
                retry_count=0,
                next_retry_at=None,
                error_message=None,
            )

            db.add(notification)

            await db.commit()

            await db.refresh(notification)

            notification_id = notification.id

            print()
            print(
                f"Zombie notification created: "
                f"ID={notification_id}"
            )

            print(
                f"Initial status: "
                f"{notification.status}"
            )

            print(
                f"Initial retry count: "
                f"{notification.retry_count}"
            )

            print(
                "Processing started at:"
                f" {notification.processing_started_at}"
            )

            print(
                f"Recovery timeout: "
                f"{PROCESSING_TIMEOUT_MINUTES} minute(s)"
            )

            # ========================================================
            # BEFORE RECOVERY
            # ========================================================

            print()
            print("=" * 70)
            print("BEFORE ZOMBIE RECOVERY")
            print("=" * 70)

            print(
                f"Notification ID: "
                f"{notification.id}"
            )

            print(
                f"Status: "
                f"{notification.status}"
            )

            print(
                f"Retry: "
                f"{notification.retry_count}"
            )

            print(
                "ProcessingStartedAt:"
                f" {notification.processing_started_at}"
            )

            print(
                f"NextRetryAt: "
                f"{notification.next_retry_at}"
            )

            # ========================================================
            # RUN REAL RECOVERY FUNCTION
            # ========================================================

            print()
            print("=" * 70)
            print("RUNNING ZOMBIE RECOVERY")
            print("=" * 70)

            recovered_ids = (
                await _recover_zombie_notifications(
                    db
                )
            )

            print()
            print(
                f"Recovered IDs: "
                f"{recovered_ids}"
            )

        # ============================================================
        # READ AFTER RECOVERY
        # ============================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id == notification_id
                )
                .limit(1)
            )

            recovered = result.scalar_one_or_none()

            if not recovered:

                print()
                print(
                    "❌ Notification disappeared "
                    "from database."
                )

                return

            print()
            print("=" * 70)
            print("AFTER ZOMBIE RECOVERY")
            print("=" * 70)

            print(
                f"ID: "
                f"{recovered.id}"
            )

            print(
                f"Status: "
                f"{recovered.status}"
            )

            print(
                f"Retry: "
                f"{recovered.retry_count}"
            )

            print(
                "ProcessingStartedAt:"
                f" {recovered.processing_started_at}"
            )

            print(
                f"NextRetryAt: "
                f"{recovered.next_retry_at}"
            )

            print(
                f"Error: "
                f"{recovered.error_message}"
            )

            # ========================================================
            # VERIFICATION
            # ========================================================

            print()
            print("=" * 70)
            print("VERIFICATION")
            print("=" * 70)

            status_pass = (
                recovered.status
                == NotificationStatus.PENDING
            )

            retry_pass = (
                recovered.retry_count == 1
            )

            processing_pass = (
                recovered.processing_started_at is None
            )

            next_retry_pass = (
                recovered.next_retry_at is not None
            )

            recovered_id_pass = (
                recovered.id in recovered_ids
            )

            print(
                "Status PENDING       : "
                f"{'PASS' if status_pass else 'FAIL'}"
            )

            print(
                "Retry = 1            : "
                f"{'PASS' if retry_pass else 'FAIL'}"
            )

            print(
                "Processing cleared   : "
                f"{'PASS' if processing_pass else 'FAIL'}"
            )

            print(
                "Next retry set       : "
                f"{'PASS' if next_retry_pass else 'FAIL'}"
            )

            print(
                "ID returned by recovery: "
                f"{'PASS' if recovered_id_pass else 'FAIL'}"
            )

            all_pass = (
                status_pass
                and retry_pass
                and processing_pass
                and next_retry_pass
                and recovered_id_pass
            )

            print()

            if all_pass:

                print("=" * 70)
                print("ZOMBIE RECOVERY TEST PASSED")
                print("=" * 70)

            else:

                print("=" * 70)
                print("ZOMBIE RECOVERY TEST FAILED")
                print("=" * 70)

    except Exception as error:

        print()
        print("=" * 70)
        print("❌ TEST ERROR")
        print("=" * 70)

        print(
            f"{type(error).__name__}: {error}"
        )

        raise

    finally:

        # ============================================================
        # CLEANUP
        # ============================================================

        async with AsyncSessionLocal() as db:

            if notification_id is not None:

                result = await db.execute(
                    select(Notification)
                    .where(
                        Notification.id == notification_id
                    )
                )

                notification = (
                    result.scalar_one_or_none()
                )

                if notification:

                    await db.delete(notification)

            if internship_id is not None:

                result = await db.execute(
                    select(Internship)
                    .where(
                        Internship.id == internship_id
                    )
                )

                internship = (
                    result.scalar_one_or_none()
                )

                if internship:

                    await db.delete(internship)

            if subscription_id is not None:

                result = await db.execute(
                    select(Subscription)
                    .where(
                        Subscription.id == subscription_id
                    )
                )

                subscription = (
                    result.scalar_one_or_none()
                )

                if subscription:

                    await db.delete(subscription)

            await db.commit()

        print()
        print("Test records cleaned up.")
        print()


if __name__ == "__main__":

    asyncio.run(main())