import pytest
from datetime import datetime, timezone

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification, NotificationStatus
from app.services.pipeline_processor import process_job_for_user


# ============================================================
# TEST 18 — NEW JOB WITHIN 45 DAYS
# ============================================================
#
# LOCKED RULE:
#
# NEW URL
#   ↓
# Posting age <= 45 days
#   ↓
# Strict internship filter
#   ↓
# User relevance >= 50
#   ↓
# SAVE TO DATABASE
#   ↓
# CREATE PENDING NOTIFICATION
#
# This test uses a 10-day-old job.
#
# IMPORTANT:
# 10 days > 7 days
# 10 days <= 45 days
#
# Therefore it MUST be accepted as a NEW job.
#
# ============================================================
#
# IMPORTANT ARCHITECTURE RULE:
#
# Internship.relevance_score
#     = global/discovery metadata
#
# Notification.relevance_score
#     = authoritative USER-SPECIFIC score
#
# Therefore this test checks the relevance threshold on
# Notification.relevance_score, NOT Internship.relevance_score.
#
# ============================================================


TEST_EMAIL = "test18_new_job@example.com"
COMPANY = "Test18 New Job Company"

TEST_URL = (
    "https://example.com/test18/"
    "software-engineering-internship"
)


def utc_now():
    return datetime.now(timezone.utc)


def make_new_job():
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
        "source": "test18",
        "via": "test18",

        # ====================================================
        # IMPORTANT:
        #
        # The job is 10 days old.
        #
        # This is:
        #   > 7 days
        #   <= 45 days
        #
        # Therefore it MUST pass the NEW JOB age rule.
        # ====================================================
        "posting_age_days": 10,
    }


@pytest.mark.asyncio
async def test_new_job_within_45_days():

    async with AsyncSessionLocal() as db:

        # ====================================================
        # CLEANUP OLD TEST 18 DATA
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

        await db.execute(
            delete(Internship).where(
                Internship.url == TEST_URL
            )
        )

        await db.commit()

        # ====================================================
        # VERIFY JOB DOES NOT EXIST BEFORE TEST
        # ====================================================

        existing_before_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        existing_before = (
            existing_before_result.scalar_one_or_none()
        )

        assert existing_before is None, (
            "Test setup failed: internship already exists "
            "before testing the NEW JOB branch."
        )

        print()
        print("=" * 70)
        print("🧪 TEST 18 — NEW JOB WITHIN 45 DAYS")
        print("=" * 70)
        print("Posting age: 10 days")
        print("Existing-job limit: 7 days")
        print("New-job limit: 45 days")
        print("=" * 70)

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
        # CREATE JOB
        #
        # IMPORTANT:
        # There is NO internship record in the database.
        #
        # Therefore this MUST enter the NEW JOB branch.
        # ====================================================

        job = make_new_job()

        print()
        print("🔎 Checking NEW job...")
        print(
            f"   URL: {job['url']}"
        )
        print(
            f"   Posting age: "
            f"{job['posting_age_days']} days"
        )
        print(
            "   Database record: DOES NOT EXIST"
        )

        # ====================================================
        # PROCESS JOB
        # ====================================================

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
        # VERIFY PIPELINE RESULT
        # ====================================================

        assert result["processed"] is True, (
            "NEW job within 45 days should be processed."
        )

        assert result["new_internship"] is True, (
            "Job should enter the NEW internship branch."
        )

        assert result["existing_internship"] is False, (
            "Job must not be treated as an existing internship."
        )

        assert result["notification_created"] is True, (
            "Qualifying NEW job should create a "
            "PENDING notification."
        )

        assert result["duplicate_notification"] is False, (
            "First notification must not be treated "
            "as a duplicate."
        )

        assert result["low_relevance"] is False, (
            "Test job should pass the relevance threshold."
        )

        assert result["domain_conflict"] is False, (
            "Test job should not have a domain conflict."
        )

        assert result["rejected_posting_age"] is False, (
            "10-day-old NEW job must not be rejected "
            "by the 45-day posting-age rule."
        )

        # ====================================================
        # VERIFY INTERNSHIP WAS SAVED
        # ====================================================

        saved_internship_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        saved_internship = (
            saved_internship_result.scalar_one_or_none()
        )

        assert saved_internship is not None, (
            "NEW job within 45 days was NOT saved "
            "to the database."
        )

        print()
        print("✅ NEW job was saved to database.")

        # ====================================================
        # VERIFY CORRECT JOB DATA
        # ====================================================

        assert saved_internship.company == COMPANY

        assert (
            saved_internship.title
            == "Software Engineering Intern"
        )

        assert saved_internship.url == TEST_URL

        assert saved_internship.location == "Remote"

        assert saved_internship.source == "test18"

        assert saved_internship.via == "test18"

        print("✅ Internship data is correct.")

        # ====================================================
        # VERIFY GLOBAL INTERNSHIP FILTER
        #
        # The Internship record should have passed the
        # global strict/relevance processing.
        #
        # DO NOT use Internship.relevance_score as the
        # authoritative user relevance score.
        # ====================================================

        assert saved_internship.passed_filter is True, (
            "Job was saved but did not pass the "
            "strict/relevance filter."
        )

        print("✅ Internship passed global filter.")

        # ====================================================
        # VERIFY PENDING NOTIFICATION
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
            "new qualifying internship."
        )

        assert (
            notification.status
            == NotificationStatus.PENDING
        ), (
            "Notification must be PENDING immediately "
            "after pipeline processing."
        )

        assert notification.user_email == TEST_EMAIL

        assert (
            notification.subscription_id
            == subscription.id
        )

        assert (
            notification.internship_id
            == saved_internship.id
        )

        print("✅ PENDING notification created.")

        # ====================================================
        # VERIFY USER-SPECIFIC RELEVANCE
        #
        # LOCKED ARCHITECTURE:
        #
        # Notification.relevance_score
        #     = authoritative user-specific score
        #
        # Internship.relevance_score
        #     = discovery metadata only
        #
        # Therefore the >= 50 threshold is checked here.
        # ====================================================

        assert (
            notification.relevance_score is not None
        ), (
            "Notification has no user-specific "
            "relevance score."
        )

        assert (
            notification.relevance_score >= 50
        ), (
            "User-specific relevance score is below "
            "the required minimum of 50."
        )

        print(
            "✅ User relevance score passed: "
            f"{notification.relevance_score:.2f}"
        )

        # ====================================================
        # VERIFY ONLY ONE NOTIFICATION EXISTS
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
            "Expected exactly one notification "
            "for this new internship."
        )

        print(
            "✅ Exactly one notification exists."
        )

        # ====================================================
        # VERIFY EMAIL WAS NOT SENT
        #
        # LOCKED ARCHITECTURE:
        #
        # Pipeline → PENDING
        # Dispatcher → Email
        #
        # The pipeline itself must NOT send email.
        # ====================================================

        assert (
            saved_internship.email_sent is False
        ), (
            "Pipeline should not mark the internship "
            "as email_sent."
        )

        print(
            "✅ Email not sent during pipeline."
        )

        # ====================================================
        # VERIFY NOTIFICATION WAS NOT SENT
        # ====================================================

        assert (
            notification.status
            == NotificationStatus.PENDING
        ), (
            "Pipeline must leave the notification "
            "in PENDING state."
        )

        assert notification.sent_at is None, (
            "Pipeline must not set sent_at."
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 70)
        print("🎉 TEST 18 PASSED")
        print("=" * 70)
        print("NEW job: 10 days old")
        print("10 days <= 45 days → ACCEPTED")
        print("Job saved to database → ✅")
        print("Strict/global filter passed → ✅")
        print(
            "User relevance >= 50 → ✅"
        )
        print(
            "PENDING notification created → ✅"
        )
        print(
            "Email sent by pipeline → ❌ (correct)"
        )
        print("=" * 70)