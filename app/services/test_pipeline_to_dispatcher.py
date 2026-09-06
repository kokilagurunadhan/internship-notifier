
# ============================================================
# PIPELINE → DISPATCHER E2E TEST
# File: app/services/test_pipeline_to_dispatcher.py
# ============================================================

import asyncio

from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.models.notification import NotificationStatus

import app.services.pipeline_processor as pipeline
import app.services.notification_dispatcher as dispatcher
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_EMAIL = "e2e_controlled@example.com"
TEST_COMPANY = "controlledtest"
TEST_DOMAIN = "software"

TEST_URL = "https://controlled.test/e2e-001"


# ============================================================
# CONTROLLED SERPAPI
# ============================================================

def fake_search_jobs(company, domain=None):

    return [
        {
            "company": "controlledtest",
            "company_name": "ControlledTest",
            "title": "Software Engineering Intern",
            "location": "Bangalore, India",
            "description": """
            Software engineering internship.

            Work with Python, REST APIs, backend services,
            databases and software development.
            """,
            "via": "Controlled Test",
            "posting_age_days": 1,
            "source": "Controlled Test",
            "url": TEST_URL,
        }
    ]


# ============================================================
# CONTROLLED EMAIL PROVIDER
# ============================================================

EMAIL_CALLS = []
def fake_send_notification_email(
    recipient,
    internships,
    idempotency_key=None,
):
    EMAIL_CALLS.append(
        {
            "recipient": recipient,
            "jobs": internships,
            "idempotency_key": idempotency_key,
        }
    )
    return {
        "success": True,
        "recipient": recipient,
        "idempotency_key": idempotency_key,
    }


# ============================================================
# CLEANUP
# ============================================================

async def cleanup_test_records():

    async with AsyncSessionLocal() as db:

        notifications = (
            await db.execute(
                select(Notification)
                .where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )
        )

        notification_ids = [
            n.id
            for n in notifications.scalars().all()
        ]

        if notification_ids:

            await db.execute(
                delete(Notification)
                .where(
                    Notification.id.in_(
                        notification_ids
                    )
                )
            )

        await db.execute(
            delete(Internship)
            .where(
                Internship.url == TEST_URL
            )
        )

        await db.execute(
            delete(Subscription)
            .where(
                Subscription.user_email == TEST_EMAIL
            )
        )

        await db.commit()


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    print("=" * 58)
    print("PIPELINE → DISPATCHER E2E TEST")
    print("=" * 58)

    # --------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------

    await cleanup_test_records()

    # --------------------------------------------------------
    # CREATE SUBSCRIPTION
    # --------------------------------------------------------

    async with AsyncSessionLocal() as db:

        subscription = Subscription(
        user_email=TEST_EMAIL,
            company=TEST_COMPANY,
            domain=TEST_DOMAIN,
            is_active=True,
        )

        db.add(subscription)

        await db.commit()
        await db.refresh(subscription)

    # --------------------------------------------------------
    # INSTALL CONTROLLED SERVICES
    # --------------------------------------------------------

    original_search = pipeline.search_jobs
    original_email = dispatcher.send_notification_email

    pipeline.search_jobs = fake_search_jobs
    dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    try:

        # ====================================================
        # STEP 1 — REAL PIPELINE
        # ====================================================

        pipeline_result = (
            await pipeline.process_subscription(subscription=subscription)
        )

        async with AsyncSessionLocal() as db:

            notification_result = await db.execute(
                select(Notification)
                .where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )

            notifications = (
                notification_result.scalars().all()
            )

        pending_notifications = [
            n
            for n in notifications
            if n.status
            == NotificationStatus.PENDING
        ]

        print(
            "Pipeline created notification :",
            "PASS"
            if len(pending_notifications) == 1
            else "FAIL",
        )

        if len(pending_notifications) != 1:
            raise AssertionError(
                "Expected exactly 1 PENDING notification"
            )

        # ====================================================
        # STEP 2 — REAL DISPATCHER
        # ====================================================

        EMAIL_CALLS.clear()

        dispatched = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print(
            "Dispatcher processed notification :",
            "PASS"
            if dispatched == 1
            else "FAIL",
        )

        # ====================================================
        # STEP 3 — EMAIL VERIFICATION
        # ====================================================

        email_pass = (
            len(EMAIL_CALLS) == 1
            and EMAIL_CALLS[0]["recipient"]
            == TEST_EMAIL
            and len(EMAIL_CALLS[0]["jobs"]) == 1
            and bool(
                EMAIL_CALLS[0]["idempotency_key"]
            )
        )

        print(
            "Email sent :",
            "PASS"
            if email_pass
            else "FAIL",
        )

        if not email_pass:
            raise AssertionError(
                "Controlled email verification failed"
            )

        # ====================================================
        # STEP 4 — DATABASE VERIFICATION
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )

            notification = (
                result.scalars().first()
            )

        sent_pass = (
            notification is not None
            and notification.status
            == NotificationStatus.SENT
            and notification.sent_at is not None
            and notification.processing_started_at
            is None
            and notification.next_retry_at is None
        )

        print(
            "Notification SENT :",
            "PASS"
            if sent_pass
            else "FAIL",
        )

        if not sent_pass:
            raise AssertionError(
                "Notification was not correctly marked SENT"
            )

        # ====================================================
        # STEP 5 — SECOND DISPATCH
        # ====================================================

        EMAIL_CALLS.clear()

        second_dispatch = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        duplicate_pass = (
            second_dispatch == 0
            and len(EMAIL_CALLS) == 0
        )

        print(
            "Second dispatch no duplicate :",
            "PASS"
            if duplicate_pass
            else "FAIL",
        )

        if not duplicate_pass:
            raise AssertionError(
                "Second dispatcher run created duplicate email"
            )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 58)
        print("🎉 PIPELINE → DISPATCHER E2E TEST PASSED")
        print("=" * 58)

    finally:

        # ----------------------------------------------------
        # RESTORE REAL SERVICES
        # ----------------------------------------------------

        pipeline.search_jobs = original_search
        dispatcher.send_notification_email = (
            original_email
        )

        await cleanup_test_records()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())

