import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.services.pipeline_processor import process_job_for_user


def utc_now():
    return datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_existing_job_over_7_days_is_discarded():
    """
    TEST 21

    Existing internship URL already exists in DB,
    but the DB record is older than 7 days.

    Expected:
        - Existing internship detected
        - NOT treated as a new internship
        - NOT accepted for processing
        - No new Internship row
        - No Notification created
        - stale=True
        - existing_internship=True
        - new_internship=False
    """

    test_email = "test21_existing_old_job@example.com"
    test_company = "Test21 Old Job Company"
    test_url = "https://example.com/test21/existing-old-job"

    async with AsyncSessionLocal() as db:

        # =========================================================
        # 1. CLEAN UP PREVIOUS TEST 21 SUBSCRIPTION
        # =========================================================

        existing_subscription_result = await db.execute(
            select(Subscription).where(
                Subscription.user_email == test_email,
                Subscription.company == test_company,
                Subscription.domain == "software",
            )
        )

        existing_subscription = (
            existing_subscription_result.scalar_one_or_none()
        )

        if existing_subscription is not None:

            # Delete notifications belonging to this subscription
            await db.execute(
                delete_notifications_statement(
                    existing_subscription.id
                )
            )

            # Delete the subscription
            await db.delete(existing_subscription)

            await db.commit()

        # =========================================================
        # 2. CLEAN UP PREVIOUS TEST 21 INTERNSHIP
        # =========================================================

        await db.execute(
            delete_internship_statement(test_url)
        )

        await db.commit()

        # =========================================================
        # 3. CREATE TEST SUBSCRIPTION
        # =========================================================

        subscription = Subscription(
            user_email=test_email,
            company=test_company,
            domain="software",
            is_active=True,
        )

        db.add(subscription)

        await db.commit()
        await db.refresh(subscription)

        print(
            f"\n👤 Test subscription created: "
            f"ID {subscription.id}"
        )

        # =========================================================
        # 4. CREATE EXISTING INTERNSHIP OLDER THAN 7 DAYS
        # =========================================================

        old_created_at = (
            utc_now() - timedelta(days=8)
        )

        internship = Internship(
            company=test_company,
            title="Old Software Engineering Internship",
            location="Remote",
            url=test_url,
            description=(
                "Software engineering internship for testing "
                "the existing-job stale logic."
            ),
            source="Test21",
            via="Test21",
            relevance_score=80.0,
            passed_filter=True,
            status="NEW",
            email_sent=False,
            created_at=old_created_at,
            last_seen_at=old_created_at,
        )

        db.add(internship)

        await db.commit()
        await db.refresh(internship)

        print(
            f"💾 Existing internship created: "
            f"ID {internship.id}"
        )

        # =========================================================
        # 5. VERIFY DB AGE IS ACTUALLY > 7 DAYS
        # =========================================================

        db_age = utc_now() - internship.created_at

        db_age_days = (
            db_age.total_seconds() / 86400
        )

        print(
            f"📅 DB internship age: "
            f"{db_age_days:.2f} days"
        )

        print(
            "📏 Existing-job maximum age: 7 days"
        )

        assert db_age > timedelta(days=7), (
            "Test setup failed: internship must be "
            "older than 7 days."
        )

        # =========================================================
        # 6. SEARCH RESULT
        #
        # IMPORTANT:
        # The URL already exists in the database.
        #
        # Therefore the pipeline MUST use the
        # EXISTING INTERNSHIP branch.
        #
        # posting_age_days=3 is intentionally irrelevant here.
        # For an existing URL, the database age determines
        # the 7-day stale decision.
        # =========================================================

        job = {
            "company": test_company,
            "title": "Old Software Engineering Internship",
            "location": "Remote",
            "url": test_url,
            "description": (
                "Software engineering internship involving "
                "Python, APIs, backend development and databases."
            ),
            "source": "Test21",
            "via": "Test21",
            "posting_age_days": 3,
        }

        print(
            "\n🔎 Processing existing internship URL..."
        )

        print(
            f"🔗 URL: {test_url}"
        )

        # =========================================================
        # 7. COUNT NOTIFICATIONS BEFORE PROCESSING
        # =========================================================

        notification_count_before = await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.subscription_id
                == subscription.id
            )
        )

        # =========================================================
        # 8. PROCESS THROUGH REAL PIPELINE
        # =========================================================

        result = await process_job_for_user(
            db=db,
            job=job,
            subscription=subscription,
        )

        print(
            "\n📊 Pipeline result:"
        )

        print(result)

        # =========================================================
        # 9. BASIC RESULT CHECK
        # =========================================================

        assert result is not None, (
            "Pipeline returned None unexpectedly."
        )

        # =========================================================
        # 10. EXISTING INTERNSHIP CHECK
        # =========================================================

        assert result.get(
            "existing_internship"
        ) is True, (
            "Existing DB internship must be "
            "identified as an existing internship."
        )

        print(
            "✅ Existing internship correctly identified."
        )

        # =========================================================
        # 11. MUST NOT BE A NEW INTERNSHIP
        # =========================================================

        assert result.get(
            "new_internship"
        ) is False, (
            "Existing DB internship must not be "
            "treated as a new internship."
        )

        print(
            "✅ Existing internship was not treated as new."
        )

        # =========================================================
        # 12. STALE CHECK
        # =========================================================

        assert result.get(
            "stale"
        ) is True, (
            "Existing internship older than 7 days "
            "must be marked stale."
        )

        print(
            "✅ Existing internship correctly marked stale."
        )

        # =========================================================
        # 13. NO NEW INTERNSHIP
        #
        # Current pipeline reports this through:
        # new_internship=False
        #
        # There is no current 'internship_saved' key.
        # =========================================================

        assert result.get(
            "new_internship"
        ) is False

        # =========================================================
        # 14. NO NOTIFICATION
        # =========================================================

        assert result.get(
            "notification_created"
        ) is False, (
            "Stale internship must not create "
            "a notification."
        )

        print(
            "✅ No notification created."
        )

        # =========================================================
        # 15. NO DUPLICATE NOTIFICATION
        # =========================================================

        assert result.get(
            "duplicate_notification"
        ) is False, (
            "No duplicate notification should "
            "be created."
        )

        print(
            "✅ No duplicate notification created."
        )

        # =========================================================
        # 16. NO LOW-RELEVANCE DECISION
        #
        # A stale internship must stop before
        # user relevance evaluation.
        #
        # Current pipeline therefore keeps:
        # low_relevance=False
        # =========================================================

        assert result.get(
            "low_relevance"
        ) is False, (
            "Stale job should not reach the "
            "low-relevance branch."
        )

        # =========================================================
        # 17. NO POSTING-AGE REJECTION
        #
        # This is an EXISTING internship.
        #
        # Therefore the new-job <=45-day rule
        # does not apply here.
        # =========================================================

        assert result.get(
            "rejected_posting_age"
        ) is False, (
            "Existing internship should not be "
            "rejected by the new-job posting-age rule."
        )

        # =========================================================
        # 18. VERIFY ONLY ONE INTERNSHIP ROW EXISTS
        # =========================================================

        internship_count = await db.scalar(
            select(func.count(Internship.id)).where(
                Internship.url == test_url
            )
        )

        print(
            f"\n🔢 Internship rows with same URL: "
            f"{internship_count}"
        )

        assert internship_count == 1, (
            "Existing internship URL must remain "
            "unique in the database."
        )

        print(
            "✅ URL uniqueness preserved."
        )

        # =========================================================
        # 19. VERIFY NOTIFICATION COUNT DID NOT INCREASE
        # =========================================================

        notification_count_after = await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.subscription_id
                == subscription.id
            )
        )

        print(
            f"🔔 Notifications before: "
            f"{notification_count_before}"
        )

        print(
            f"🔔 Notifications after: "
            f"{notification_count_after}"
        )

        assert (
            notification_count_after
            == notification_count_before
        ), (
            "Stale internship must not create "
            "a notification."
        )

        print(
            "✅ Notification count unchanged."
        )

        # =========================================================
        # 20. FINAL VERIFICATION
        # =========================================================

        print(
            "\n" + "=" * 70
        )

        print(
            "✅ CASE PASSED"
        )

        print(
            "Existing internship >7 days → discarded"
        )

        print(
            "Existing internship correctly detected → ✅"
        )

        print(
            "Not treated as new → ✅"
        )

        print(
            "No new internship created → ✅"
        )

        print(
            "No notification created → ✅"
        )

        print(
            "URL uniqueness preserved → ✅"
        )

        print(
            "Existing-job 7-day rule verified → ✅"
        )

        print(
            "=" * 70
        )

        print(
            "\n🎉 TEST 21 PASSED"
        )


# =============================================================
# HELPER STATEMENTS
# =============================================================

def delete_notifications_statement(subscription_id):
    """
    Return a DELETE statement for notifications belonging
    to the specified subscription.
    """

    from sqlalchemy import delete

    return delete(Notification).where(
        Notification.subscription_id == subscription_id
    )


def delete_internship_statement(url):
    """
    Return a DELETE statement for the test internship URL.
    """

    from sqlalchemy import delete

    return delete(Internship).where(
        Internship.url == url
    )