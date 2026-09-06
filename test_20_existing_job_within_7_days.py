
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification, NotificationStatus
from app.services.pipeline_processor import process_job_for_user


# ============================================================
# TEST 20 — EXISTING JOB WITHIN 7 DAYS
# ============================================================
#
# LOCKED RULE:
#
# URL ALREADY EXISTS IN DATABASE
#          ↓
#       EXISTING JOB
#          ↓
# DB age <= 7 days
#          ↓
#       CONTINUE
#          ↓
# User-specific duplicate check
#          ↓
# PENDING notification
#
# This test uses a DB internship that is 3 days old.
#
# IMPORTANT:
#
# 3 days <= 7 days
#
# Therefore the existing internship MUST proceed.
#
# This is intentionally different from Test 18:
#
# Test 18:
#   NEW job + posting age 10 days → ACCEPTED
#
# Test 20:
#   EXISTING DB job + DB age 3 days → PROCEEDS
# ============================================================


TEST_EMAIL = "test20_existing_job@example.com"
COMPANY = "Test20 Existing Job Company"

TEST_URL = (
    "https://example.com/test20/"
    "existing-software-engineering-internship"
)


def utc_now():
    return datetime.now(timezone.utc)


def make_existing_job():
    return {
        "company": COMPANY,
        "title": "Software Engineering Intern",
        "location": "Remote",
        "url": TEST_URL,
        "description": (
            "Software engineering internship for students. "
            "Work on Python programming, backend development, "
            "REST APIs, databases and software development."
        ),
        "source": "test20",
        "via": "test20",
    }


@pytest.mark.asyncio
async def test_existing_job_within_7_days():

    async with AsyncSessionLocal() as db:

        # ====================================================
        # CLEANUP OLD TEST 20 DATA
        # ====================================================

        old_subscriptions_result = await db.execute(
            select(Subscription).where(
                Subscription.user_email == TEST_EMAIL
            )
        )

        old_subscriptions = (
            old_subscriptions_result.scalars().all()
        )

        old_subscription_ids = [
            subscription.id
            for subscription in old_subscriptions
        ]

        if old_subscription_ids:

            await db.execute(
                delete(Notification).where(
                    Notification.subscription_id.in_(
                        old_subscription_ids
                    )
                )
            )

            await db.execute(
                delete(Subscription).where(
                    Subscription.id.in_(
                        old_subscription_ids
                    )
                )
            )

        # Delete any previous Test 20 internship
        await db.execute(
            delete(Internship).where(
                Internship.url == TEST_URL
            )
        )

        await db.commit()

        # ====================================================
        # VERIFY JOB DOES NOT EXIST BEFORE SETUP
        # ====================================================

        before_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        before_internship = (
            before_result.scalar_one_or_none()
        )

        assert before_internship is None, (
            "Test setup failed: Test 20 internship "
            "already exists."
        )

        # ====================================================
        # CREATE ACTIVE SUBSCRIPTION
        # ====================================================

        subscription = Subscription(
            user_email=TEST_EMAIL,
            company=COMPANY,
            domain="software",
            is_active=True,
        )

        db.add(subscription)

        await db.flush()

        # ====================================================
        # CREATE EXISTING INTERNSHIP
        # ====================================================
        #
        # This is the key part of Test 20.
        #
        # The internship is ALREADY in the DB.
        #
        # created_at = 3 days ago
        #
        # 3 <= 7 → existing job is eligible.
        # ====================================================

        internship_created_at = (
            utc_now() - timedelta(days=3)
        )

        internship = Internship(
            company=COMPANY,
            title="Software Engineering Intern",
            location="Remote",
            url=TEST_URL,
            description=(
                "Software engineering internship for students."
            ),
            source="test20",
            via="test20",
            relevance_score=80.0,
            passed_filter=True,
            status="RELEVANT",
            email_sent=False,
            created_at=internship_created_at,
            last_seen_at=internship_created_at,
        )

        db.add(internship)

        await db.commit()

        # ====================================================
        # VERIFY INTERNSHIP REALLY EXISTS
        # ====================================================

        existing_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        existing_internship = (
            existing_result.scalar_one_or_none()
        )

        assert existing_internship is not None, (
            "Test setup failed: existing internship "
            "was not saved."
        )

        # ====================================================
        # VERIFY AGE IS WITHIN 7 DAYS
        # ====================================================

        age = (
            utc_now()
            - existing_internship.created_at
        )

        age_days = age.total_seconds() / 86400

        assert age_days <= 7, (
            f"Test setup failed: internship age is "
            f"{age_days:.2f} days, expected <= 7 days."
        )

        # ====================================================
        # TEST INFORMATION
        # ====================================================

        print()
        print("=" * 70)
        print("🧪 TEST 20 — EXISTING JOB WITHIN 7 DAYS")
        print("=" * 70)
        print(
            f"DB internship age: {age_days:.2f} days"
        )
        print(
            "Existing-job maximum age: 7 days"
        )
        print(
            "Database record: EXISTS"
        )
        print("=" * 70)

        print()
        print("🔎 Checking EXISTING job...")
        print(
            f"   URL: {TEST_URL}"
        )
        print(
            f"   DB age: {age_days:.2f} days"
        )

        # ====================================================
        # PROCESS JOB
        # ====================================================
        #
        # The URL already exists.
        #
        # Therefore process_job_for_user() MUST use
        # the EXISTING JOB branch.
        #
        # The existing record is only 3 days old.
        #
        # Therefore it should proceed.
        # ====================================================

        job = make_existing_job()

        result = await process_job_for_user(
            db=db,
            job=job,
            subscription=subscription,
        )

        await db.commit()

        print()
        print("📊 Pipeline result:")
        print(result)

        # ====================================================
        # VERIFY PIPELINE IDENTIFIED EXISTING JOB
        # ====================================================

        assert result is not None, (
            "Pipeline returned None unexpectedly."
        )

        assert result.get("existing_internship") is True, (
    "Job should have been identified as an "
    "EXISTING internship."
)

        assert result.get("new_internship") is False, (
    "Existing DB internship must not be "
    "treated as a NEW internship."
)

        # ====================================================
        # VERIFY JOB WAS NOT MARKED STALE
        # ====================================================

        assert result.get("stale") is False, (
            "Existing internship within 7 days "
            "was incorrectly marked stale."
        )

        print(
            "✅ Existing job correctly identified."
        )

        print(
            "✅ Existing job is within 7-day window."
        )

        # ====================================================
        # VERIFY INTERNSHIP STILL EXISTS
        # ====================================================

        saved_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        saved_internship = (
            saved_result.scalar_one_or_none()
        )

        assert saved_internship is not None, (
            "Existing internship disappeared "
            "from the database."
        )

        assert saved_internship.id == (
            existing_internship.id
        ), (
            "A different internship record was created "
            "instead of using the existing record."
        )

        print(
            "✅ Existing DB internship was reused."
        )

        # ====================================================
        # VERIFY NO DUPLICATE INTERNSHIP WAS CREATED
        # ====================================================

        all_matching_internships_result = (
            await db.execute(
                select(Internship).where(
                    Internship.url == TEST_URL
                )
            )
        )

        all_matching_internships = (
            all_matching_internships_result
            .scalars()
            .all()
        )

        assert len(all_matching_internships) == 1, (
            "More than one internship exists for "
            "the same URL."
        )

        print(
            "✅ URL uniqueness preserved."
        )

        # ====================================================
        # VERIFY PENDING NOTIFICATION
        # ====================================================
        #
        # User has NOT previously received this internship.
        #
        # Therefore a PENDING notification should be created.
        # ====================================================

        notification_result = await db.execute(
            select(Notification).where(
                Notification.subscription_id
                == subscription.id,
                Notification.internship_id
                == saved_internship.id,
            )
        )

        notification = (
            notification_result.scalar_one_or_none()
        )

        assert notification is not None, (
            "No notification was created for the "
            "eligible existing internship."
        )

        assert (
            notification.status
            == NotificationStatus.PENDING
        ), (
            "Notification for an eligible existing job "
            "must be PENDING."
        )

        assert (
            notification.user_email == TEST_EMAIL
        )

        print(
            "✅ PENDING notification created."
        )

        # ====================================================
        # VERIFY EXACTLY ONE NOTIFICATION
        # ====================================================

        all_notifications_result = await db.execute(
            select(Notification).where(
                Notification.subscription_id
                == subscription.id
            )
        )

        all_notifications = (
            all_notifications_result.scalars().all()
        )

        assert len(all_notifications) == 1, (
            "Expected exactly one notification."
        )

        # ====================================================
        # VERIFY PIPELINE DID NOT SEND EMAIL
        # ====================================================
        #
        # Locked architecture:
        #
        # Pipeline → PENDING
        # Dispatcher → Email
        #
        # Therefore the pipeline itself must not send email.
        # ====================================================

        assert (
            saved_internship.email_sent is False
        ), (
            "Pipeline should not mark the internship "
            "as email_sent."
        )

        print(
            "✅ Email was not sent by pipeline."
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 70)
        print("🎉 TEST 20 PASSED")
        print("=" * 70)
        print(
            f"Existing job age: {age_days:.2f} days"
        )
        print(
            "3 days <= 7 days → PROCEEDED ✅"
        )
        print(
            "Existing DB record reused → ✅"
        )
        print(
            "No duplicate internship → ✅"
        )
        print(
            "PENDING notification created → ✅"
        )
        print(
            "Email sent by pipeline → ❌ Correct"
        )
        print("=" * 70)
