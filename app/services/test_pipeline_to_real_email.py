# ============================================================
# PIPELINE → REAL EMAIL E2E TEST
# File: app/services/test_pipeline_to_real_email.py
# ============================================================

import asyncio

from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)

import app.services.pipeline_processor as pipeline
import app.services.notification_dispatcher as dispatcher


# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_EMAIL = "kokilasudha9363@gmail.com"

TEST_COMPANY = "controlledtest"

TEST_DOMAIN = "software"

TEST_URL = (
    "https://controlled.test/"
    "real-email-e2e-001"
)


# ============================================================
# CONTROLLED SEARCH
# ============================================================

def fake_search_jobs(
    company,
    domain=None,
):

    return [
        {
            "company": "controlledtest",

            "company_name": "ControlledTest",

            "title": "Software Engineering Intern",

            "location": "Bangalore, India",

            "description": """
            Software engineering internship.

            Work with Python, REST APIs,
            backend services, databases,
            and software development.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": TEST_URL,
        }
    ]


# ============================================================
# CLEANUP
# ============================================================

async def cleanup_test_records():

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # Notifications
        # ----------------------------------------------------

        result = await db.execute(
            select(Notification).where(
                Notification.user_email
                == TEST_EMAIL
            )
        )

        notifications = (
            result.scalars().all()
        )

        notification_ids = [
            notification.id
            for notification
            in notifications
        ]

        if notification_ids:

            await db.execute(
                delete(Notification).where(
                    Notification.id.in_(
                        notification_ids
                    )
                )
            )

        # ----------------------------------------------------
        # Internship
        # ----------------------------------------------------

        await db.execute(
            delete(Internship).where(
                Internship.url
                == TEST_URL
            )
        )

        # ----------------------------------------------------
        # Subscription
        # ----------------------------------------------------

        await db.execute(
            delete(Subscription).where(
                Subscription.user_email
                == TEST_EMAIL
            )
        )

        await db.commit()


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    print("=" * 70)

    print(
        "PIPELINE → REAL RESEND EMAIL E2E TEST"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # CLEANUP
    # --------------------------------------------------------

    await cleanup_test_records()

    # --------------------------------------------------------
    # CREATE TEST SUBSCRIPTION
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

        await db.refresh(
            subscription
        )

    # --------------------------------------------------------
    # SAVE ORIGINAL SEARCH
    # --------------------------------------------------------

    original_search = (
        pipeline.search_jobs
    )

    # --------------------------------------------------------
    # CONTROL SEARCH ONLY
    # --------------------------------------------------------

    pipeline.search_jobs = (
        fake_search_jobs
    )

    try:

        # ====================================================
        # STEP 1 — REAL PIPELINE
        # ====================================================

        print()
        print(
            "STEP 1: REAL PIPELINE"
        )

        print("-" * 70)

        result = await (
            pipeline.process_subscription(
                subscription=subscription
            )
        )

        print(
            "PASS: pipeline completed"
        )

        # ====================================================
        # STEP 2 — VERIFY PENDING
        # ====================================================

        print()
        print(
            "STEP 2: PENDING NOTIFICATION"
        )

        print("-" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )

            notifications = (
                result.scalars().all()
            )

        pending = [
            notification
            for notification
            in notifications
            if notification.status
            == NotificationStatus.PENDING
        ]

        if len(pending) != 1:

            raise AssertionError(
                "Expected exactly one PENDING notification"
            )

        print(
            "PASS: 1 PENDING notification created"
        )

        # ====================================================
        # STEP 3 — REAL DISPATCHER
        # ====================================================

        print()
        print(
            "STEP 3: REAL DISPATCHER"
        )

        print("-" * 70)

        dispatched = await (
            dispatcher
            .dispatch_pending_notifications_batch()
        )

        if dispatched != 1:

            raise AssertionError(
                f"Expected dispatcher to process 1 "
                f"notification, got {dispatched}"
            )

        print(
            "PASS: dispatcher processed notification"
        )

        # ====================================================
        # STEP 4 — VERIFY SENT
        # ====================================================

        print()
        print(
            "STEP 4: VERIFY SENT STATUS"
        )

        print("-" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )

            notification = (
                result.scalars().first()
            )

        if (
            notification is None
            or notification.status
            != NotificationStatus.SENT
            or notification.sent_at
            is None
        ):

            raise AssertionError(
                "Notification was not marked SENT"
            )

        print(
            "PASS: notification marked SENT"
        )

        # ====================================================
        # FINAL
        # ====================================================

        print()
        print("=" * 70)

        print(
            "🎉 PIPELINE → REAL RESEND EMAIL "
            "E2E TEST PASSED"
        )

        print("=" * 70)

        print()
        print(
            f"📧 Check inbox: {TEST_EMAIL}"
        )

        print(
            "📁 Also check Spam/Junk if necessary."
        )

    finally:

        # ----------------------------------------------------
        # RESTORE SEARCH
        # ----------------------------------------------------

        pipeline.search_jobs = (
            original_search
        )

        # ----------------------------------------------------
        # CLEAN TEST DATA
        # ----------------------------------------------------

        await cleanup_test_records()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())