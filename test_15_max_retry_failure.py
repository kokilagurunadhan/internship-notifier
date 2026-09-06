
# ============================================================
# TEST 15 — MAX RETRY FAILURE
#
# Verifies:
#
# Attempt 1 → PENDING → retry after 5 minutes
# Attempt 2 → PENDING → retry after 10 minutes
# Attempt 3 → PENDING → retry after 20 minutes
# Attempt 4 → PENDING → retry after 40 minutes
# Attempt 5 → FAILED → no more retries
#
# IMPORTANT:
# This test does NOT modify production retry logic.
# It only moves next_retry_at into the past between attempts
# so the test does not actually wait 5 + 10 + 20 + 40 minutes.
# ============================================================

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)

from app.services import notification_dispatcher


# ============================================================
# TEST DATA
# ============================================================

TEST_EMAIL = "test15_max_retry@example.com"
TEST_COMPANY = "Test15 Max Retry Company"

TEST_TITLE = "Software Engineering Intern"

TEST_URL = (
    "https://example.com/jobs/"
    "test-15-max-retry-20260818-001"
)


# ============================================================
# EMAIL ATTEMPT COUNTER
# ============================================================

email_attempt_count = 0


# ============================================================
# FAKE EMAIL SENDER
#
# IMPORTANT:
# The production dispatcher treats an exception as a failed
# email attempt.
#
# Therefore this fake sender MUST raise an exception.
# ============================================================


def fake_send_notification_email(
    user_email,
    internships,
    idempotency_key,
):
    global email_attempt_count

    # --------------------------------------------------------
    # Count ONLY Test 15's email attempts.
    #
    # The dispatcher may process other pending notifications
    # from the database. Those must NOT affect Test 15's count.
    # --------------------------------------------------------

    if user_email == TEST_EMAIL:

        email_attempt_count += 1

        print()
        print(
            f"📧 TEST 15 EMAIL ATTEMPT "
            f"{email_attempt_count}"
        )

        print(
            f"   User: {user_email}"
        )

        print(
            f"   Internships: "
            f"{len(internships)}"
        )

        print(
            f"   Idempotency key: "
            f"{idempotency_key}"
        )

    else:

        print()
        print(
            "📧 UNRELATED EMAIL ATTEMPT "
            f"(not counted): {user_email}"
        )

    # --------------------------------------------------------
    # Simulate permanent email-provider failure.
    # --------------------------------------------------------

    raise RuntimeError(
        "TEST 15: Simulated permanent "
        "email provider failure"
    )
# ============================================================
# MAIN TEST
# ============================================================

def test_15_max_retry_failure():

    asyncio.run(
        _run_test_15()
    )


# ============================================================
# ASYNC TEST IMPLEMENTATION
# ============================================================

async def _run_test_15():

    global email_attempt_count

    email_attempt_count = 0

    # --------------------------------------------------------
    # Save original email sender
    # --------------------------------------------------------

    original_email_sender = (
        notification_dispatcher.send_notification_email
    )

    # --------------------------------------------------------
    # Replace production email sender with test sender
    # --------------------------------------------------------

    notification_dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    async with AsyncSessionLocal() as db:

        try:

            # =================================================
            # CLEAN PREVIOUS TEST 15 DATA
            # =================================================

            print()
            print("=" * 70)
            print("🧹 CLEANING PREVIOUS TEST 15 DATA")
            print("=" * 70)

            # -------------------------------------------------
            # Find previous subscription
            # -------------------------------------------------

            subscription_result = await db.execute(
                select(Subscription).where(
                    Subscription.user_email == TEST_EMAIL,
                    Subscription.company == TEST_COMPANY,
                )
            )

            old_subscriptions = (
                subscription_result.scalars().all()
            )

            # -------------------------------------------------
            # Delete notifications belonging to test
            # -------------------------------------------------

            if old_subscriptions:

                subscription_ids = [
                    subscription.id
                    for subscription in old_subscriptions
                ]

                await db.execute(
                    delete(Notification).where(
                        Notification.subscription_id.in_(
                            subscription_ids
                        )
                    )
                )

                # ---------------------------------------------
                # Delete subscriptions
                # ---------------------------------------------

                await db.execute(
                    delete(Subscription).where(
                        Subscription.id.in_(
                            subscription_ids
                        )
                    )
                )

            # -------------------------------------------------
            # Delete previous internship
            # -------------------------------------------------

            await db.execute(
                delete(Internship).where(
                    Internship.url == TEST_URL
                )
            )

            await db.commit()

            print(
                "✅ Previous Test 15 data cleaned"
            )

            # =================================================
            # CREATE SUBSCRIPTION
            # =================================================

            subscription = Subscription(
                user_email=TEST_EMAIL,
                company=TEST_COMPANY,
                domain="software",
                is_active=True,
            )

            db.add(subscription)

            await db.flush()

            print()
            print(
                f"👤 Subscription created: "
                f"{subscription.id}"
            )

            # =================================================
            # CREATE INTERNSHIP
            # =================================================

            internship = Internship(
                company=TEST_COMPANY,
                title=TEST_TITLE,
                location="Remote",
                url=TEST_URL,
                description=(
                    "Software engineering internship "
                    "for students."
                ),
                source="SerpAPI",
                via="Test",
                relevance_score=80,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            db.add(internship)

            await db.flush()

            print(
                f"💼 Internship created: "
                f"{internship.id}"
            )

            # =================================================
            # CREATE NOTIFICATION
            # =================================================

            notification = Notification(
                subscription_id=subscription.id,
                user_email=TEST_EMAIL,
                internship_id=internship.id,
                status=NotificationStatus.PENDING,
                relevance_score=80,
                retry_count=0,
                next_retry_at=None,
                error_message=None,
                sent_at=None,
                processing_started_at=None,
                idempotency_key=None,
            )

            db.add(notification)

            await db.commit()

            print(
                f"🔔 Notification created: "
                f"{notification.id}"
            )

            notification_id = notification.id
            internship_id = internship.id
            subscription_id = subscription.id

            # =================================================
            # RUN 5 FAILED ATTEMPTS
            # =================================================

            for attempt in range(1, 6):

                print()
                print("=" * 70)
                print(
                    f"🔁 TEST 15 — ATTEMPT "
                    f"{attempt} / 5"
                )
                print("=" * 70)

                # ------------------------------------------------
                # For attempts 2–5:
                #
                # Production would wait until next_retry_at.
                #
                # The test moves next_retry_at into the past
                # so we can test immediately.
                # ------------------------------------------------

                if attempt > 1:

                    async with AsyncSessionLocal() as retry_db:

                        retry_result = await retry_db.execute(
                            select(Notification).where(
                                Notification.id
                                == notification_id
                            )
                        )

                        retry_notification = (
                            retry_result.scalar_one()
                        )

                        retry_notification.next_retry_at = (
                            datetime.now(timezone.utc)
                            - timedelta(minutes=1)
                        )

                        await retry_db.commit()

                    print(
                        "⏩ TEST ONLY: "
                        "next_retry_at moved into the past"
                    )

                # ------------------------------------------------
                # Run dispatcher
                # ------------------------------------------------

                successful_digests = (
                    await notification_dispatcher
                    .dispatch_pending_notifications_batch()
                )

                print(
                    f"📊 Successful digests: "
                    f"{successful_digests}"
                )

                # ------------------------------------------------
                # Reload notification using a fresh session
                # ------------------------------------------------

                async with AsyncSessionLocal() as verify_db:

                    result = await verify_db.execute(
                        select(Notification).where(
                            Notification.id
                            == notification_id
                        )
                    )

                    current_notification = (
                        result.scalar_one()
                    )

                    print(
                        f"📌 Status: "
                        f"{current_notification.status}"
                    )

                    print(
                        f"🔢 Retry count: "
                        f"{current_notification.retry_count}"
                    )

                    print(
                        f"⏰ Next retry: "
                        f"{current_notification.next_retry_at}"
                    )

                    # =================================================
                    # ATTEMPTS 1–4
                    # =================================================

                    if attempt < 5:

                        assert (
                            current_notification.status
                            == NotificationStatus.PENDING
                        ), (
                            f"Attempt {attempt}: "
                            f"Expected PENDING, got "
                            f"{current_notification.status}"
                        )

                        assert (
                            current_notification.retry_count
                            == attempt
                        ), (
                            f"Attempt {attempt}: "
                            f"Expected retry_count "
                            f"{attempt}, got "
                            f"{current_notification.retry_count}"
                        )

                        assert (
                            current_notification.next_retry_at
                            is not None
                        ), (
                            f"Attempt {attempt}: "
                            "next_retry_at should exist"
                        )

                        print(
                            f"✅ Attempt {attempt}: "
                            f"PENDING with retry scheduled"
                        )

                    # =================================================
                    # ATTEMPT 5
                    # =================================================

                    else:

                        assert (
                            current_notification.status
                            == NotificationStatus.FAILED
                        ), (
                            "Attempt 5: Expected FAILED, "
                            f"got {current_notification.status}"
                        )

                        assert (
                            current_notification.retry_count
                            == 5
                        ), (
                            "Attempt 5: Expected "
                            "retry_count=5, got "
                            f"{current_notification.retry_count}"
                        )

                        assert (
                            current_notification.next_retry_at
                            is None
                        ), (
                            "Attempt 5: "
                            "next_retry_at must be None"
                        )

                        assert (
                            current_notification.error_message
                            is not None
                        ), (
                            "Attempt 5: "
                            "error_message should exist"
                        )

                        print(
                            "✅ Attempt 5: "
                            "FAILED permanently"
                        )

            # =================================================
            # FINAL VERIFICATION
            # =================================================

            print()
            print("=" * 70)
            print("🔍 FINAL TEST 15 VERIFICATION")
            print("=" * 70)

            async with AsyncSessionLocal() as verify_db:

                # ------------------------------------------------
                # Notification
                # ------------------------------------------------

                notification_result = await verify_db.execute(
                    select(Notification).where(
                        Notification.id
                        == notification_id
                    )
                )

                final_notification = (
                    notification_result.scalar_one()
                )

                # ------------------------------------------------
                # Internship
                # ------------------------------------------------

                internship_result = await verify_db.execute(
                    select(Internship).where(
                        Internship.id
                        == internship_id
                    )
                )

                final_internship = (
                    internship_result.scalar_one()
                )

                # ------------------------------------------------
                # Subscription
                # ------------------------------------------------

                subscription_result = await verify_db.execute(
                    select(Subscription).where(
                        Subscription.id
                        == subscription_id
                    )
                )

                final_subscription = (
                    subscription_result.scalar_one()
                )

                # =================================================
                # ASSERT FINAL NOTIFICATION
                # =================================================

                assert (
                    final_notification.status
                    == NotificationStatus.FAILED
                )

                assert (
                    final_notification.retry_count
                    == 5
                )

                assert (
                    final_notification.next_retry_at
                    is None
                )

                assert (
                    final_notification.sent_at
                    is None
                )

                assert (
                    final_notification.error_message
                    is not None
                )

                # =================================================
                # ASSERT EMAIL ATTEMPTS
                # =================================================

                assert (
                    email_attempt_count == 5
                ), (
                    "Expected exactly 5 email attempts, "
                    f"got {email_attempt_count}"
                )

                # =================================================
                # INTERNSHIP MUST NOT BE MARKED SENT
                # =================================================

                assert (
                    final_internship.email_sent
                    is False
                )

                # =================================================
                # SUBSCRIPTION STILL ACTIVE
                # =================================================

                assert (
                    final_subscription.is_active
                    is True
                )

                # =================================================
                # VERIFY EXACTLY ONE NOTIFICATION
                # =================================================

                notification_count_result = (
                    await verify_db.execute(
                        select(Notification).where(
                            Notification.user_email
                            == TEST_EMAIL,
                            Notification.internship_id
                            == internship_id,
                        )
                    )
                )

                notifications = (
                    notification_count_result
                    .scalars()
                    .all()
                )

                assert len(notifications) == 1

            # =================================================
            # IMPORTANT:
            # A FAILED notification must NOT be retried again.
            # =================================================

            print()
            print(
                "🚫 TESTING NO SIXTH ATTEMPT"
            )

            await notification_dispatcher \
                .dispatch_pending_notifications_batch()

            assert (
                email_attempt_count == 5
            ), (
                "FAILED notification was retried "
                "after reaching MAX_RETRIES"
            )

            print(
                "✅ No sixth email attempt occurred"
            )

            # =================================================
            # SUCCESS
            # =================================================

            print()
            print("=" * 70)
            print("🎉 TEST 15 PASSED")
            print("=" * 70)

            print(
                "✅ Attempt 1 → PENDING → retry scheduled"
            )

            print(
                "✅ Attempt 2 → PENDING → retry scheduled"
            )

            print(
                "✅ Attempt 3 → PENDING → retry scheduled"
            )

            print(
                "✅ Attempt 4 → PENDING → retry scheduled"
            )

            print(
                "✅ Attempt 5 → FAILED"
            )

            print(
                "✅ No sixth attempt"
            )

            print(
                "✅ Production retry logic preserved"
            )

        finally:

            # =================================================
            # RESTORE REAL EMAIL SENDER
            # =================================================

            notification_dispatcher.send_notification_email = (
                original_email_sender
            )

            await db.rollback()

