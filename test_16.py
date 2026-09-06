import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)

from app.services import pipeline_processor
from app.services import notification_dispatcher
from app.services.scheduler import check_for_new_internships


# ================================================================
# TEST 16 CONSTANTS
# ================================================================

USER_A = "test16_scheduler_user_a@example.com"
USER_B = "test16_scheduler_user_b@example.com"
INACTIVE_USER = "test16_scheduler_inactive@example.com"

COMPANY_A = "test16 scheduler company a"
COMPANY_B = "test16 scheduler company b"
COMPANY_INACTIVE = "test16 scheduler inactive company"

URL_A = "https://test16.example.com/internship-a"
URL_B = "https://test16.example.com/internship-b"
URL_INACTIVE = "https://test16.example.com/internship-inactive"


# ================================================================
# EMAIL CAPTURE
# ================================================================

email_calls = []


# ================================================================
# FAKE SERPAPI SEARCH
#
# IMPORTANT:
# Current pipeline performs GROUPED search by:
#
#     company + domain
#
# The fake search MUST return jobs for our two active companies.
#
# It must also contain posting_age_days because a NEW URL must
# satisfy the <=45 day source-posting rule.
# ================================================================

def fake_search_jobs(company, domain):
    print()
    print("=" * 70)
    print("🧪 TEST 16 — FAKE SEARCH")
    print(f"🏢 Company: {company}")
    print(f"🎯 Domain: {domain}")
    print("=" * 70)

    normalized_company = company.strip().lower()

    # ------------------------------------------------------------
    # ACTIVE USER A
    # ------------------------------------------------------------

    if normalized_company == COMPANY_A.lower():

        return [
            {
                "title": "Software Engineering Intern",
                "company": COMPANY_A,
                "location": "Remote",
                "url": URL_A,
                "description": (
                    "Software engineering internship for students. "
                    "Work with Python, backend APIs, databases and "
                    "software development."
                ),
                "source": "test16",
                "via": "Test 16",
                "posting_age_days": 10,
            }
        ]

    # ------------------------------------------------------------
    # ACTIVE USER B
    # ------------------------------------------------------------

    if normalized_company == COMPANY_B.lower():

        return [
            {
                "title": "Backend Engineering Intern",
                "company": COMPANY_B,
                "location": "Remote",
                "url": URL_B,
                "description": (
                    "Backend software engineering internship. "
                    "Work with Python, REST APIs, databases and "
                    "backend development."
                ),
                "source": "test16",
                "via": "Test 16",
                "posting_age_days": 10,
            }
        ]

    # ------------------------------------------------------------
    # INACTIVE COMPANY
    #
    # If this is ever searched, the test must fail because the
    # inactive subscription should never reach the search stage.
    # ------------------------------------------------------------

    if normalized_company == COMPANY_INACTIVE.lower():

        raise AssertionError(
            "❌ Inactive subscription was incorrectly sent to search"
        )

    # ------------------------------------------------------------
    # OTHER DATABASE SUBSCRIPTIONS
    #
    # Your database currently contains other active test data.
    # They are allowed to reach the pipeline, but this test does
    # not want to generate jobs for them.
    # ------------------------------------------------------------

    return []


# ================================================================
# FAKE EMAIL SENDER
#
# Current dispatcher passes internship DATA AS DICTIONARIES.
#
# DO NOT use:
#     internship.id
#
# Use:
#     internship["id"]
# ================================================================

def fake_send_notification_email(
    recipient_email,
    internships,
    idempotency_key,
):
    print()
    print("=" * 70)
    print("📨 TEST 16 — FAKE EMAIL")
    print(f"👤 Recipient: {recipient_email}")
    print(f"📦 Internship count: {len(internships)}")
    print(f"🔑 Idempotency key: {idempotency_key}")
    print("=" * 70)

    email_calls.append(
        {
            "recipient_email": recipient_email,
            "internships": internships,
            "idempotency_key": idempotency_key,
        }
    )

    # Production sender returns a non-None value on success.
    return {
        "success": True
    }


# ================================================================
# MAIN TEST
# ================================================================

async def main():

    global email_calls

    email_calls = []

    # ============================================================
    # SAVE ORIGINAL FUNCTIONS
    # ============================================================

    original_search_jobs = pipeline_processor.search_jobs

    original_email_sender = (
        notification_dispatcher.send_notification_email
    )

    # ============================================================
    # PATCH EXTERNAL DEPENDENCIES
    # ============================================================

    pipeline_processor.search_jobs = fake_search_jobs

    notification_dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    try:

        # ========================================================
        # CLEAN PREVIOUS TEST 16 DATA
        # ========================================================

        print()
        print("=" * 70)
        print("🧹 CLEANING PREVIOUS TEST 16 DATA")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            # ----------------------------------------------------
            # Find old subscriptions
            # ----------------------------------------------------

            result = await db.execute(
                select(Subscription).where(
                    Subscription.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                            INACTIVE_USER,
                        ]
                    )
                )
            )

            old_subscriptions = result.scalars().all()

            old_subscription_ids = [
                subscription.id
                for subscription in old_subscriptions
            ]

            # ----------------------------------------------------
            # Find old internships
            # ----------------------------------------------------

            result = await db.execute(
                select(Internship).where(
                    Internship.url.in_(
                        [
                            URL_A,
                            URL_B,
                            URL_INACTIVE,
                        ]
                    )
                )
            )

            old_internships = result.scalars().all()

            old_internship_ids = [
                internship.id
                for internship in old_internships
            ]

            # ----------------------------------------------------
            # Delete notifications
            # ----------------------------------------------------

            if old_subscription_ids:

                await db.execute(
                    delete(Notification).where(
                        Notification.subscription_id.in_(
                            old_subscription_ids
                        )
                    )
                )

            if old_internship_ids:

                await db.execute(
                    delete(Notification).where(
                        Notification.internship_id.in_(
                            old_internship_ids
                        )
                    )
                )

            # ----------------------------------------------------
            # Delete internships
            # ----------------------------------------------------

            if old_internship_ids:

                await db.execute(
                    delete(Internship).where(
                        Internship.id.in_(
                            old_internship_ids
                        )
                    )
                )

            # ----------------------------------------------------
            # Delete subscriptions
            # ----------------------------------------------------

            if old_subscription_ids:

                await db.execute(
                    delete(Subscription).where(
                        Subscription.id.in_(
                            old_subscription_ids
                        )
                    )
                )

            await db.commit()

            print("✅ Previous Test 16 data cleaned")

        # ========================================================
        # CREATE TEST SUBSCRIPTIONS
        # ========================================================

        async with AsyncSessionLocal() as db:

            # ----------------------------------------------------
            # USER A
            # ----------------------------------------------------

            print()
            print("=" * 70)
            print("👤 TEST 16 — CREATE ACTIVE USER A")
            print("=" * 70)

            subscription_a = Subscription(
                user_email=USER_A,
                company=COMPANY_A,
                domain="software",
                is_active=True,
            )

            db.add(subscription_a)

            # ----------------------------------------------------
            # USER B
            # ----------------------------------------------------

            print()
            print("=" * 70)
            print("👤 TEST 16 — CREATE ACTIVE USER B")
            print("=" * 70)

            subscription_b = Subscription(
                user_email=USER_B,
                company=COMPANY_B,
                domain="backend",
                is_active=True,
            )

            db.add(subscription_b)

            # ----------------------------------------------------
            # INACTIVE USER
            # ----------------------------------------------------

            print()
            print("=" * 70)
            print("🚫 TEST 16 — CREATE INACTIVE USER")
            print("=" * 70)

            inactive_subscription = Subscription(
                user_email=INACTIVE_USER,
                company=COMPANY_INACTIVE,
                domain="software",
                is_active=False,
            )

            db.add(inactive_subscription)

            await db.commit()

            await db.refresh(subscription_a)
            await db.refresh(subscription_b)
            await db.refresh(inactive_subscription)

            print(
                f"🆔 Subscription A: {subscription_a.id}"
            )

            print(
                f"🆔 Subscription B: {subscription_b.id}"
            )

            print(
                f"🆔 Inactive Subscription: "
                f"{inactive_subscription.id}"
            )

            print("📌 Active: False")

            # ====================================================
            # VERIFY SUBSCRIPTIONS
            # ====================================================

            print()
            print("=" * 70)
            print("🔎 VERIFY SUBSCRIPTIONS")
            print("=" * 70)

            result = await db.execute(
                select(Subscription).where(
                    Subscription.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                        ]
                    ),
                    Subscription.is_active.is_(True),
                )
            )

            active_subscriptions = result.scalars().all()

            assert len(active_subscriptions) == 2, (
                "❌ Expected exactly 2 active Test 16 subscriptions"
            )

            print(
                "✅ Exactly 2 active Test 16 subscriptions"
            )

            assert inactive_subscription.is_active is False

            print(
                "✅ Inactive subscription correctly disabled"
            )

            # ====================================================
            # VERIFY CLEAN TEST STATE
            # ====================================================

            print()
            print("=" * 70)
            print("🧹 VERIFY CLEAN TEST STATE")
            print("=" * 70)

            result = await db.execute(
                select(Internship).where(
                    Internship.url.in_(
                        [
                            URL_A,
                            URL_B,
                            URL_INACTIVE,
                        ]
                    )
                )
            )

            old_test16_rows = result.scalars().all()

            assert len(old_test16_rows) == 0, (
                "❌ Old Test 16 internship data still exists"
            )

            print(
                "✅ No old Test 16 internships remain"
            )

        # ========================================================
        # RUN REAL SCHEDULER
        # ========================================================

        print()
        print("=" * 70)
        print("🧪 TEST 16 — RUN SCHEDULER CYCLE")
        print("=" * 70)

        scheduler_result = (
            await check_for_new_internships()
        )

        # Current scheduler intentionally returns None.
        assert scheduler_result is None

        print(
            "✅ Scheduler cycle returned None"
        )

        # ========================================================
        # VERIFY PIPELINE CREATED INTERNSHIPS
        # ========================================================

        async with AsyncSessionLocal() as db:

            print()
            print("=" * 70)
            print("🧪 VERIFY PIPELINE INTERNSHIPS")
            print("=" * 70)

            # ----------------------------------------------------
            # USER A INTERNSHIP
            # ----------------------------------------------------

            result = await db.execute(
                select(Internship).where(
                    Internship.url == URL_A
                )
            )

            internship_a = (
                result.scalar_one_or_none()
            )

            assert internship_a is not None, (
                "❌ User A internship was not created"
            )

            print(
                f"✅ User A internship created "
                f"(ID={internship_a.id})"
            )

            # ----------------------------------------------------
            # USER B INTERNSHIP
            # ----------------------------------------------------

            result = await db.execute(
                select(Internship).where(
                    Internship.url == URL_B
                )
            )

            internship_b = (
                result.scalar_one_or_none()
            )

            assert internship_b is not None, (
                "❌ User B internship was not created"
            )

            print(
                f"✅ User B internship created "
                f"(ID={internship_b.id})"
            )

            # ----------------------------------------------------
            # INACTIVE INTERNSHIP MUST NOT EXIST
            # ----------------------------------------------------

            result = await db.execute(
                select(Internship).where(
                    Internship.url == URL_INACTIVE
                )
            )

            inactive_internship = (
                result.scalar_one_or_none()
            )

            assert inactive_internship is None, (
                "❌ Inactive subscription produced an internship"
            )

            print(
                "✅ Inactive subscription produced no internship"
            )

            # ====================================================
            # VERIFY NOTIFICATIONS
            # ====================================================

            print()
            print("=" * 70)
            print("🔔 VERIFY PENDING NOTIFICATIONS")
            print("=" * 70)

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                            INACTIVE_USER,
                        ]
                    )
                )
            )

            notifications = result.scalars().all()

            # Exactly one notification per active user.
            assert len(notifications) == 2, (
                f"❌ Expected 2 notifications, "
                f"found {len(notifications)}"
            )

            print(
                "✅ Exactly 2 notifications created"
            )

            for notification in notifications:

                assert (
                    notification.status
                    == NotificationStatus.PENDING
                ), (
                    f"❌ Notification {notification.id} "
                    f"is not PENDING"
                )

                assert notification.sent_at is None

                assert (
                    notification.user_email
                    in [USER_A, USER_B]
                )

                print(
                    f"✅ Notification {notification.id} "
                    f"→ {notification.user_email} "
                    f"→ PENDING"
                )

            # ----------------------------------------------------
            # INACTIVE USER MUST HAVE NO NOTIFICATION
            # ----------------------------------------------------

            inactive_notifications = [
                notification
                for notification in notifications
                if notification.user_email
                == INACTIVE_USER
            ]

            assert len(inactive_notifications) == 0

            print(
                "✅ Inactive user received no notification"
            )

        # ========================================================
        # IMPORTANT ARCHITECTURE CHECK
        #
        # Scheduler/pipeline MUST NOT SEND EMAIL.
        # ========================================================

        assert len(email_calls) == 0, (
            "❌ Scheduler/pipeline sent email directly"
        )

        print()
        print(
            "✅ Scheduler created PENDING notifications "
            "without sending email"
        )

        # ========================================================
        # RUN NOTIFICATION DISPATCHER
        # ========================================================

        print()
        print("=" * 70)
        print("📨 TEST 16 — RUN NOTIFICATION DISPATCHER")
        print("=" * 70)

        dispatch_result = (
            await notification_dispatcher
            .dispatch_pending_notifications_batch()
        )

        print(
            f"📨 Dispatcher returned: {dispatch_result}"
        )

        # One digest for User A + one digest for User B.
        assert dispatch_result == 2, (
            f"❌ Expected dispatcher to send 2 digests, "
            f"got {dispatch_result}"
        )

        assert len(email_calls) == 2, (
            f"❌ Expected exactly 2 email calls, "
            f"got {len(email_calls)}"
        )

        print(
            "✅ Exactly 2 grouped digest emails sent"
        )

        # ========================================================
        # VERIFY EMAIL FOR USER A
        # ========================================================

        user_a_emails = [
            call
            for call in email_calls
            if call["recipient_email"] == USER_A
        ]

        assert len(user_a_emails) == 1, (
            "❌ User A did not receive exactly one digest"
        )

        user_a_email = user_a_emails[0]

        assert len(
            user_a_email["internships"]
        ) == 1, (
            "❌ User A digest should contain exactly 1 internship"
        )

        user_a_job = (
            user_a_email["internships"][0]
        )

        assert user_a_job["url"] == URL_A

        assert (
            user_a_job["company"].lower()
            == COMPANY_A.lower()
        )

        print(
            "✅ User A → exactly one digest"
        )

        print(
            "✅ User A → correct internship"
        )

        # --------------------------------------------------------
        # User A must NOT receive User B job.
        # --------------------------------------------------------

        assert all(
            job["url"] != URL_B
            for job in user_a_email["internships"]
        )

        print(
            "✅ User A → no User B internship"
        )

        # ========================================================
        # VERIFY EMAIL FOR USER B
        # ========================================================

        user_b_emails = [
            call
            for call in email_calls
            if call["recipient_email"] == USER_B
        ]

        assert len(user_b_emails) == 1, (
            "❌ User B did not receive exactly one digest"
        )

        user_b_email = user_b_emails[0]

        assert len(
            user_b_email["internships"]
        ) == 1, (
            "❌ User B digest should contain exactly 1 internship"
        )

        user_b_job = (
            user_b_email["internships"][0]
        )

        assert user_b_job["url"] == URL_B

        assert (
            user_b_job["company"].lower()
            == COMPANY_B.lower()
        )

        print(
            "✅ User B → exactly one digest"
        )

        print(
            "✅ User B → correct internship"
        )

        # --------------------------------------------------------
        # User B must NOT receive User A job.
        # --------------------------------------------------------

        assert all(
            job["url"] != URL_A
            for job in user_b_email["internships"]
        )

        print(
            "✅ User B → no User A internship"
        )

        # ========================================================
        # VERIFY DATABASE DELIVERY STATE
        # ========================================================

        async with AsyncSessionLocal() as db:

            print()
            print("=" * 70)
            print("🔎 VERIFY FINAL NOTIFICATION STATE")
            print("=" * 70)

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                        ]
                    )
                )
            )

            final_notifications = (
                result.scalars().all()
            )

            assert len(final_notifications) == 2

            for notification in final_notifications:

                assert (
                    notification.status
                    == NotificationStatus.SENT
                ), (
                    f"❌ Notification {notification.id} "
                    f"is not SENT"
                )

                assert notification.sent_at is not None

                assert (
                    notification.processing_started_at
                    is None
                )

                assert notification.next_retry_at is None

                assert notification.error_message is None

                assert notification.retry_count == 0

                assert (
                    notification.idempotency_key
                    is not None
                )

                print(
                    f"✅ Notification {notification.id} "
                    f"→ SENT"
                )

                print(
                    f"   🔑 {notification.idempotency_key}"
                )

            # ----------------------------------------------------
            # Idempotency keys must differ between users.
            # ----------------------------------------------------

            keys = [
                notification.idempotency_key
                for notification
                in final_notifications
            ]

            assert len(set(keys)) == 2, (
                "❌ User digests should have different "
                "idempotency keys"
            )

            print(
                "✅ Different users → different idempotency keys"
            )

        # ========================================================
        # SECOND DISPATCHER RUN
        #
        # There are no PENDING notifications anymore.
        # Therefore no duplicate email must be sent.
        # ========================================================

        print()
        print("=" * 70)
        print("🔁 TEST 16 — SECOND DISPATCHER RUN")
        print("=" * 70)

        second_dispatch_result = (
            await notification_dispatcher
            .dispatch_pending_notifications_batch()
        )

        print(
            f"📨 Second dispatcher returned: "
            f"{second_dispatch_result}"
        )

        assert second_dispatch_result == 0, (
            "❌ Second dispatcher should send 0 digests"
        )

        assert len(email_calls) == 2, (
            "❌ Duplicate email was sent"
        )

        print(
            "✅ Second dispatch sent no duplicate emails"
        )

        # ========================================================
        # FINAL SUCCESS
        # ========================================================

        print()
        print("=" * 70)
        print("🎉 TEST 16 PASSED")
        print("=" * 70)

    finally:

        # ========================================================
        # RESTORE ORIGINAL FUNCTIONS
        # ========================================================

        pipeline_processor.search_jobs = (
            original_search_jobs
        )

        notification_dispatcher.send_notification_email = (
            original_email_sender
        )

        print()
        print(
            "🔄 Test 16 patched functions restored"
        )


# ================================================================
# PYTEST ENTRY POINT
# ================================================================

def test_scheduler_full_processing_cycle():

    asyncio.run(main())