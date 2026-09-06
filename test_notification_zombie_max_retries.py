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
    MAX_RETRIES,
)


TEST_EMAIL = "kokilasudha9363@gmail.com"
TEST_COMPANY = "microsoft"


def utc_now():
    return datetime.now(timezone.utc)


async def main():

    print()
    print("=" * 60)
    print("ZOMBIE MAX RETRIES TEST")
    print("=" * 60)

    notification_id = None
    internship_id = None
    subscription_id = None

    try:

        # ========================================================
        # FIND OR CREATE TEST SUBSCRIPTION
        # ========================================================

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

            # ====================================================
            # CREATE TEST INTERNSHIP
            # ====================================================

            internship = Internship(
                company=TEST_COMPANY,
                title="Zombie Max Retry Test",
                location="Remote",
                url=(
                    "https://example.com/"
                    "zombie-max-retry-"
                    + str(utc_now().timestamp())
                ),
                description="Zombie max retry test.",
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

            # ====================================================
            # CREATE ZOMBIE AT MAX-1 RETRIES
            # ====================================================

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

                # IMPORTANT:
                # Recovery increments retry_count by 1.
                # MAX_RETRIES - 1 -> MAX_RETRIES
                retry_count=MAX_RETRIES - 1,

                next_retry_at=None,
                error_message=None,
            )

            db.add(notification)

            await db.commit()
            await db.refresh(notification)

            notification_id = notification.id

            print()
            print(
                f"Notification ID: "
                f"{notification_id}"
            )

            print(
                f"Initial status: "
                f"{notification.status}"
            )

            print(
                f"Initial retry: "
                f"{notification.retry_count}"
            )

            print(
                f"MAX_RETRIES: "
                f"{MAX_RETRIES}"
            )

            print(
                "Processing started at:"
                f" {notification.processing_started_at}"
            )

            # ====================================================
            # RUN REAL ZOMBIE RECOVERY
            # ====================================================

            print()
            print("=" * 60)
            print("RUNNING ZOMBIE RECOVERY")
            print("=" * 60)

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

        # ========================================================
        # READ AFTER RECOVERY
        # ========================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id == notification_id
                )
                .limit(1)
            )

            notification = result.scalar_one_or_none()

            if not notification:

                print()
                print(
                    "❌ Notification not found."
                )

                return

            print()
            print("=" * 60)
            print("RESULT")
            print("=" * 60)

            print(
                f"Status: "
                f"{notification.status}"
            )

            print(
                f"Retry: "
                f"{notification.retry_count}"
            )

            print(
                f"NextRetryAt: "
                f"{notification.next_retry_at}"
            )

            print(
                "ProcessingStartedAt: "
                f"{notification.processing_started_at}"
            )

            print(
                f"Error: "
                f"{notification.error_message}"
            )

            # ====================================================
            # EXPECTATIONS
            # ====================================================

            status_pass = (
                notification.status
                == NotificationStatus.FAILED
            )

            retry_pass = (
                notification.retry_count
                == MAX_RETRIES
            )

            next_retry_pass = (
                notification.next_retry_at is None
            )

            processing_pass = (
                notification.processing_started_at
                is None
            )

            error_pass = (
                notification.error_message is not None
                and
                "permanently failed"
                in notification.error_message.lower()
            )

            # ====================================================
            # VERIFICATION
            # ====================================================

            print()
            print("=" * 60)
            print("VERIFICATION")
            print("=" * 60)

            print(
                "Status FAILED       : "
                f"{'PASS' if status_pass else 'FAIL'}"
            )

            print(
                f"Retry = {MAX_RETRIES}          : "
                f"{'PASS' if retry_pass else 'FAIL'}"
            )

            print(
                "Next retry = None   : "
                f"{'PASS' if next_retry_pass else 'FAIL'}"
            )

            print(
                "Processing cleared  : "
                f"{'PASS' if processing_pass else 'FAIL'}"
            )

            print(
                "Permanent error saved: "
                f"{'PASS' if error_pass else 'FAIL'}"
            )

            all_pass = (
                status_pass
                and retry_pass
                and next_retry_pass
                and processing_pass
                and error_pass
            )

            if all_pass:

                print()
                print("=" * 60)
                print("ZOMBIE MAX RETRIES TEST PASSED")
                print("=" * 60)

            else:

                print()
                print("=" * 60)
                print("ZOMBIE MAX RETRIES TEST FAILED")
                print("=" * 60)

    except Exception as error:

        print()
        print("=" * 60)
        print("❌ TEST ERROR")
        print("=" * 60)

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise

    finally:

        # ========================================================
        # CLEANUP
        # ========================================================

        async with AsyncSessionLocal() as db:

            # ----------------------------------------------------
            # Delete notification
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # Delete internship
            # ----------------------------------------------------

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

            # ----------------------------------------------------
            # Delete subscription ONLY if this test created it
            # ----------------------------------------------------

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