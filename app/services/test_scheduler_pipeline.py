# ============================================================
# SCHEDULER → REAL PIPELINE INTEGRATION TEST
# File: app/services/test_scheduler_pipeline.py
# ============================================================

import asyncio
import os

from sqlalchemy import delete, select

import app.services.scheduler as scheduler
import app.services.pipeline_processor as pipeline
import app.services.notification_dispatcher as dispatcher

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)


# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_EMAIL = "scheduler_e2e@example.com"
TEST_COMPANY = "controlledtest"
TEST_DOMAIN = "software"

TEST_URL = (
    "https://controlled.test/scheduler-e2e-001"
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

            Work with Python, REST APIs, backend services,
            databases and software development.
            """,
            "via": "Controlled Test",
            "source": "Controlled Test",
            "url": TEST_URL,
        }
    ]


# ============================================================
# CONTROLLED EMAIL
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

        notifications = await db.execute(
            select(Notification).where(
                Notification.user_email
                == TEST_EMAIL
            )
        )

        notification_ids = [
            notification.id
            for notification
            in notifications.scalars().all()
        ]

        if notification_ids:

            await db.execute(
                delete(Notification).where(
                    Notification.id.in_(
                        notification_ids
                    )
                )
            )

        await db.execute(
            delete(Internship).where(
                Internship.url == TEST_URL
            )
        )

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

    print("=" * 65)
    print("SCHEDULER → REAL PIPELINE INTEGRATION TEST")
    print("=" * 65)

    # --------------------------------------------------------
    # CLEAN OLD TEST DATA
    # --------------------------------------------------------

    await cleanup_test_records()

    # --------------------------------------------------------
    # CREATE CONTROLLED SUBSCRIPTION
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
    # SAVE ORIGINAL SERVICES
    # --------------------------------------------------------

    original_search = pipeline.search_jobs
    original_email = (
        dispatcher.send_notification_email
    )

    original_scheduler_pipeline = (
        scheduler.process_all_active_subscriptions
    )

    # --------------------------------------------------------
    # CONTROL EXTERNAL SERVICES
    # --------------------------------------------------------

    pipeline.search_jobs = fake_search_jobs

    dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    # IMPORTANT:
    #
    # scheduler.py imported the pipeline function
    # directly, so patch the scheduler's reference.
    #
    # But the replacement below calls the REAL pipeline.

    async def real_pipeline_wrapper():

        return await (
            pipeline.process_all_active_subscriptions()
        )

    scheduler.process_all_active_subscriptions = (
        real_pipeline_wrapper
    )

    try:

        # ====================================================
        # TEST 1 — SCHEDULER CYCLE
        # ====================================================

        print()
        print("TEST 1: SCHEDULER → REAL PIPELINE")
        print("-" * 65)

        await scheduler.check_for_new_internships()

        print(
            "PASS: scheduler cycle completed"
        )

        # ====================================================
        # TEST 2 — NOTIFICATION CREATED
        # ====================================================

        print()
        print("TEST 2: PENDING NOTIFICATION")
        print("-" * 65)

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

        if len(pending) == 1:

            print(
                "PASS: exactly 1 PENDING notification created"
            )

        else:

            print(
                "FAIL: expected 1 PENDING notification, "
                f"found {len(pending)}"
            )

            raise AssertionError(
                "Scheduler did not create expected notification"
            )

        # ====================================================
        # TEST 3 — DISPATCHER
        # ====================================================

        print()
        print("TEST 3: DISPATCHER")
        print("-" * 65)

        EMAIL_CALLS.clear()

        dispatched = await (
            dispatcher
            .dispatch_pending_notifications_batch()
        )

        if dispatched == 1:

            print(
                "PASS: dispatcher processed notification"
            )

        else:

            print(
                "FAIL: dispatcher processed",
                dispatched,
                "notifications"
            )

            raise AssertionError(
                "Dispatcher did not process expected notification"
            )

        # ====================================================
        # TEST 4 — EMAIL
        # ====================================================

        print()
        print("TEST 4: CONTROLLED EMAIL")
        print("-" * 65)

        if (
            len(EMAIL_CALLS) == 1
            and EMAIL_CALLS[0]["recipient"]
            == TEST_EMAIL
            and len(
                EMAIL_CALLS[0]["jobs"]
            ) == 1
            and EMAIL_CALLS[0]["idempotency_key"]
        ):

            print(
                "PASS: exactly one email sent"
            )

        else:

            print(
                "FAIL: email verification failed"
            )

            raise AssertionError(
                "Controlled email verification failed"
            )

        # ====================================================
        # TEST 5 — SENT STATUS
        # ====================================================

        print()
        print("TEST 5: NOTIFICATION SENT")
        print("-" * 65)

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
            notification is not None
            and notification.status
            == NotificationStatus.SENT
            and notification.sent_at
            is not None
        ):

            print(
                "PASS: notification marked SENT"
            )

        else:

            print(
                "FAIL: notification not marked SENT"
            )

            raise AssertionError(
                "Notification SENT verification failed"
            )

        # ====================================================
        # TEST 6 — DUPLICATE PROTECTION
        # ====================================================

        print()
        print("TEST 6: SECOND DISPATCH")
        print("-" * 65)

        EMAIL_CALLS.clear()

        second_dispatch = await (
            dispatcher
            .dispatch_pending_notifications_batch()
        )

        if (
            second_dispatch == 0
            and len(EMAIL_CALLS) == 0
        ):

            print(
                "PASS: second dispatch created no duplicate email"
            )

        else:

            print(
                "FAIL: duplicate email detected"
            )

            raise AssertionError(
                "Duplicate notification was dispatched"
            )

        # ====================================================
        # TEST 7 — SCHEDULER CONFIGURATION
        # ====================================================

        print()
        print("TEST 7: SCHEDULER CONFIGURATION")
        print("-" * 65)

        os.environ["SCHEDULER_ENABLED"] = "true"

        scheduler.start_scheduler()

        job = scheduler.scheduler.get_job(
            "internship_checker"
        )

        if (
            scheduler.scheduler.running
            and job is not None
            and job.max_instances == 1
            and job.coalesce is True
            and job.trigger.interval.total_seconds()
            == 720 * 60
        ):

            print(
                "PASS: scheduler configuration valid"
            )

        else:

            raise AssertionError(
                "Scheduler configuration verification failed"
            )

        # ====================================================
        # TEST 8 — CLEAN SHUTDOWN
        # ====================================================

        print()
        print("TEST 8: CLEAN SHUTDOWN")
        print("-" * 65)

        scheduler.stop_scheduler()

        await asyncio.sleep(0)

        if not scheduler.scheduler.running:

            print(
                "PASS: scheduler stopped cleanly"
            )

        else:

            raise AssertionError(
                "Scheduler failed to stop"
            )

        # ====================================================
        # FINAL
        # ====================================================

        print()
        print("=" * 65)
        print(
            "🎉 SCHEDULER → REAL PIPELINE "
            "INTEGRATION TEST PASSED"
        )
        print("=" * 65)

    finally:

        # ----------------------------------------------------
        # RESTORE SERVICES
        # ----------------------------------------------------

        pipeline.search_jobs = (
            original_search
        )

        dispatcher.send_notification_email = (
            original_email
        )

        scheduler.process_all_active_subscriptions = (
            original_scheduler_pipeline
        )

        # ----------------------------------------------------
        # STOP SCHEDULER IF NECESSARY
        # ----------------------------------------------------

        if scheduler.scheduler.running:

            scheduler.stop_scheduler()

            await asyncio.sleep(0)

        # ----------------------------------------------------
        # REMOVE TEST DATA
        # ----------------------------------------------------

        await cleanup_test_records()

        os.environ.pop(
            "SCHEDULER_ENABLED",
            None,
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    asyncio.run(main())