
import pytest

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.services.pipeline_processor import (
    process_job_for_user,
)


# ================================================================
# TEST DATA
# ================================================================

TEST_EMAIL = "test19_user@example.com"

COMPANY = "Test19 Old Company"

TEST_URL = (
    "https://example.com/test19/"
    "old-software-engineering-internship"
)


# ================================================================
# CREATE TEST JOB
# ================================================================

def make_old_new_job():
    """
    Create a NEW internship job.

    The URL does NOT exist in the database.

    Posting age = 46 days.

    Locked rule:

        New URL
            ↓
        posting age > 45 days
            ↓
        REJECT
            ↓
        DO NOT SAVE
            ↓
        DO NOT CREATE NOTIFICATION
    """

    return {
        "company": COMPANY,
        "title": "Software Engineering Internship",
        "location": "Remote",
        "url": TEST_URL,
        "description": (
            "Software engineering internship "
            "for students interested in Python, "
            "backend development and software engineering."
        ),
        "source": "test19",
        "via": "test19",
        "posting_age_days": 46,
    }


# ================================================================
# TEST 19
# ================================================================

@pytest.mark.asyncio
async def test_new_job_over_45_days():

    async with AsyncSessionLocal() as db:

        # ========================================================
        # 1. CLEANUP OLD TEST 19 DATA
        # ========================================================

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

        # --------------------------------------------------------
        # Remove any previous Test 19 internship
        # --------------------------------------------------------

        await db.execute(
            delete(Internship).where(
                Internship.url == TEST_URL
            )
        )

        await db.commit()

        # ========================================================
        # 2. VERIFY JOB DOES NOT EXIST BEFORE TEST
        # ========================================================

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

        # ========================================================
        # 3. CREATE ACTIVE SUBSCRIPTION
        # ========================================================

        subscription = Subscription(
            user_email=TEST_EMAIL,
            company=COMPANY,
            domain="software",
            is_active=True,
        )

        db.add(subscription)

        await db.flush()

        # ========================================================
        # 4. CREATE 46-DAY-OLD NEW JOB
        # ========================================================

        job = make_old_new_job()

        print()
        print("=" * 70)
        print("🧪 TEST 19 — NEW JOB OVER 45 DAYS")
        print("=" * 70)

        print(
            "Posting age: "
            f"{job['posting_age_days']} days"
        )

        print(
            "New-job maximum age: 45 days"
        )

        print(
            "Database record: DOES NOT EXIST"
        )

        print("=" * 70)

        # ========================================================
        # 5. PROCESS JOB
        #
        # The job is NEW because the URL does not exist.
        #
        # Posting age = 46 days.
        #
        # 46 > 45
        #
        # Therefore:
        #
        #   ❌ Do not save internship
        #   ❌ Do not create notification
        #   ❌ Do not process job
        #   ✅ rejected_posting_age = True
        #
        # IMPORTANT:
        #
        # This is NOT the "stale existing internship" branch.
        #
        # Therefore:
        #
        #   stale = False
        #
        # is correct.
        # ========================================================

        print()
        print("🔎 Checking NEW job...")

        print(
            f"   URL: {job['url']}"
        )

        print(
            f"   Posting age: "
            f"{job['posting_age_days']} days"
        )

        result = await process_job_for_user(
            db=db,
            job=job,
            subscription=subscription,
        )

        await db.commit()

        # ========================================================
        # 6. PRINT RESULT
        # ========================================================

        print()
        print("📊 Pipeline result:")
        print(result)

        # ========================================================
        # 7. VERIFY RESULT EXISTS
        # ========================================================

        assert result is not None, (
            "Pipeline returned None unexpectedly."
        )

        # ========================================================
        # 8. VERIFY POSTING AGE REJECTION
        # ========================================================

        assert result.get("rejected_posting_age") is True, (
            "46-day-old NEW job should be rejected because "
            "posting age exceeds the 45-day limit."
        )

        print(
            "✅ CASE 1 PASSED: "
            "46-day-old NEW job was rejected "
            "by the 45-day posting-age rule"
        )

        # ========================================================
        # 9. VERIFY IT WAS NOT SAVED AS A NEW INTERNSHIP
        # ========================================================

        assert result.get("new_internship") is False, (
            "46-day-old NEW job must not be saved."
        )

        print(
            "✅ CASE 2 PASSED: "
            "Old NEW job was not saved"
        )

        # ========================================================
        # 10. VERIFY NO NOTIFICATION WAS CREATED
        # ========================================================

        assert result.get("notification_created") is False, (
            "Rejected NEW job must not create a notification."
        )

        print(
            "✅ CASE 3 PASSED: "
            "No notification was created"
        )

        # ========================================================
        # 11. VERIFY JOB WAS NOT PROCESSED
        # ========================================================

        assert result.get("processed") is False, (
            "Rejected NEW job must not be processed."
        )

        print(
            "✅ CASE 4 PASSED: "
            "Rejected NEW job was not processed"
        )

        # ========================================================
        # 12. VERIFY IT IS NOT THE STALE EXISTING-JOB BRANCH
        # ========================================================

        assert result.get("stale") is False, (
            "A NEW job rejected because of posting age "
            "must not be marked as stale."
        )

        print(
            "✅ CASE 5 PASSED: "
            "NEW posting-age rejection is correctly "
            "different from existing-job staleness"
        )

        # ========================================================
        # 13. VERIFY DATABASE — INTERNSHIP MUST NOT EXIST
        # ========================================================

        existing_after_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        existing_after = (
            existing_after_result.scalar_one_or_none()
        )

        assert existing_after is None, (
            "46-day-old NEW internship must not be saved "
            "to the database."
        )

        print(
            "✅ CASE 6 PASSED: "
            "No Internship database record was created"
        )

        # ========================================================
        # 14. VERIFY DATABASE — NO NOTIFICATION
        # ========================================================

        notification_result = await db.execute(
            select(Notification).where(
                Notification.subscription_id
                == subscription.id
            )
        )

        notifications = (
            notification_result.scalars().all()
        )

        assert len(notifications) == 0, (
            "46-day-old NEW job must not create "
            "a Notification record."
        )

        print(
            "✅ CASE 7 PASSED: "
            "No Notification database record was created"
        )

        # ========================================================
        # 15. FINAL ARCHITECTURE VERIFICATION
        # ========================================================

        print()
        print("=" * 70)
        print("🎯 TEST 19 ARCHITECTURE VERIFIED")
        print("=" * 70)

        print(
            """
NEW URL
   ↓
Posting age = 46 days
   ↓
46 > 45
   ↓
⛔ REJECT
   ↓
❌ No Internship saved
   ↓
❌ No Notification created
   ↓
❌ No email
"""
        )

        print("=" * 70)
        print("🎉 TEST 19 PASSED")
        print("=" * 70)

        # ========================================================
        # 16. CLEANUP
        # ========================================================

        await db.execute(
            delete(Notification).where(
                Notification.subscription_id
                == subscription.id
            )
        )

        await db.execute(
            delete(Subscription).where(
                Subscription.id == subscription.id
            )
        )

        await db.execute(
            delete(Internship).where(
                Internship.url == TEST_URL
            )
        )

        await db.commit()

        print(
            "\n🧹 Test19 cleanup completed."
        )

