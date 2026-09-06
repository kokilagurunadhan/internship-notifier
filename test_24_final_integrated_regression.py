import asyncio
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select, delete

import app.services.pipeline_processor as pipeline
import app.services.scheduler as scheduler

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification


# ============================================================
# TEST CONSTANTS
# ============================================================

USER_A = "test24_user_a@example.com"
USER_B = "test24_user_b@example.com"
INACTIVE_USER = "test24_inactive@example.com"

COMPANY = "Test24 Company"
DOMAIN = "test24.example.com"

NEW_URL = "https://test24.example.com/new-valid"

OLD_URL = "https://test24.example.com/old-valid"

TOO_OLD_URL = "https://test24.example.com/too-old"

INVALID_URL = "https://test24.example.com/not-internship"


# ============================================================
# CONTROLLED SERPAPI JOBS
# ============================================================

def fake_search_jobs(*args, **kwargs):

    return [

        # ----------------------------------------------------
        # NEW VALID JOB
        # ----------------------------------------------------

        {
            "title": "Python Software Engineering Intern",
            "company": COMPANY,
            "location": "Remote",
            "link": NEW_URL,
            "description": (
                "Python backend software engineering internship "
                "for students."
            ),
            "source": "Test24",
            "via": "Test24",
            "posting_age_days": 10,
        },

        # ----------------------------------------------------
        # EXISTING JOB
        # ----------------------------------------------------

        {
            "title": "Backend Engineering Internship",
            "company": COMPANY,
            "location": "Remote",
            "link": OLD_URL,
            "description": (
                "Backend engineering internship."
            ),
            "source": "Test24",
            "via": "Test24",
            "posting_age_days": 3,
        },

        # ----------------------------------------------------
        # NEW JOB >45 DAYS
        # ----------------------------------------------------

        {
            "title": "Old Software Internship",
            "company": COMPANY,
            "location": "Remote",
            "link": TOO_OLD_URL,
            "description": (
                "Software engineering internship."
            ),
            "source": "Test24",
            "via": "Test24",
            "posting_age_days": 60,
        },

        # ----------------------------------------------------
        # NON-INTERNSHIP
        # ----------------------------------------------------

        {
            "title": "Senior Software Engineer",
            "company": COMPANY,
            "location": "Remote",
            "link": INVALID_URL,
            "description": (
                "Full-time senior software engineer."
            ),
            "source": "Test24",
            "via": "Test24",
            "posting_age_days": 5,
        },
    ]


# ============================================================
# CONTROLLED RELEVANCE
# ============================================================

# ============================================================
# CONTROLLED RELEVANCE
# ============================================================

def fake_relevance_score(
    title,
    description,
    user_domain,
):

    # User with the Test24 domain passes.
    if user_domain == DOMAIN:
        return {
            "keyword_score": 80.0,
            "semantic_score": 80.0,
            "conflict": False,
            "final_score": 80.0,
        }

    return {
        "keyword_score": 40.0,
        "semantic_score": 40.0,
        "conflict": False,
        "final_score": 40.0,
    }

# ============================================================
# CONTROLLED FILTER
# ============================================================

def fake_filter_internships(jobs):

    result = []

    for job in jobs:

        title = job.get("title", "").lower()

        if "intern" in title or "internship" in title:
            result.append(job)

    return result


# ============================================================
# CONTROLLED COMPANY VERIFICATION
# ============================================================

def fake_verify_company(
    job,
    company=None,
    domain=None,
):

    return True


# ============================================================
# CLEANUP
# ============================================================

async def cleanup():

    async with AsyncSessionLocal() as db:

        # Notifications first because of FK.
        await db.execute(
            delete(Notification).where(
                Notification.user_email.in_(
                    [
                        USER_A,
                        USER_B,
                        INACTIVE_USER,
                    ]
                )
            )
        )

        await db.execute(
            delete(Internship).where(
                Internship.url.in_(
                    [
                        NEW_URL,
                        OLD_URL,
                        TOO_OLD_URL,
                        INVALID_URL,
                    ]
                )
            )
        )

        await db.execute(
            delete(Subscription).where(
                Subscription.user_email.in_(
                    [
                        USER_A,
                        USER_B,
                        INACTIVE_USER,
                    ]
                )
            )
        )

        await db.commit()


# ============================================================
# MAIN TEST
# ============================================================

@pytest.mark.asyncio
async def test_24_final_integrated_regression(
    monkeypatch,
):

    print("")
    print("=" * 70)
    print(
        "🧪 TEST 24 — FINAL INTEGRATED REGRESSION"
    )
    print("=" * 70)

    await cleanup()

    try:

        # ====================================================
        # PATCH REAL SEARCH / FILTER / RELEVANCE
        # ====================================================

        monkeypatch.setattr(
            pipeline,
            "search_jobs",
            fake_search_jobs,
        )

        monkeypatch.setattr(
            pipeline,
            "filter_internships",
            fake_filter_internships,
        )

        monkeypatch.setattr(
            pipeline,
            "verify_company",
            fake_verify_company,
        )

        monkeypatch.setattr(
            pipeline,
            "calculate_relevance_score",
            fake_relevance_score,
        )

        # ====================================================
        # CREATE SUBSCRIPTIONS
        # ====================================================

        async with AsyncSessionLocal() as db:

            subscription_a = Subscription(
                user_email=USER_A,
                company=COMPANY,
                domain=DOMAIN,
                is_active=True,
            )

            subscription_b = Subscription(
                user_email=USER_B,
                company=COMPANY,
                domain=DOMAIN,
                is_active=True,
            )

            inactive_subscription = Subscription(
                user_email=INACTIVE_USER,
                company=COMPANY,
                domain=DOMAIN,
                is_active=False,
            )

            db.add_all(
                [
                    subscription_a,
                    subscription_b,
                    inactive_subscription,
                ]
            )

            await db.commit()

            await db.refresh(subscription_a)
            await db.refresh(subscription_b)
            await db.refresh(inactive_subscription)

            print(
                f"👤 Active subscription A created: "
                f"ID {subscription_a.id}"
            )

            print(
                f"👤 Active subscription B created: "
                f"ID {subscription_b.id}"
            )

            print(
                f"🚫 Inactive subscription created: "
                f"ID {inactive_subscription.id}"
            )

        # ====================================================
        # CREATE EXISTING RECENT JOB
        # ====================================================

        async with AsyncSessionLocal() as db:

            recent_internship = Internship(
                company=COMPANY,
                title="Existing Backend Internship",
                location="Remote",
                url=OLD_URL,
                description="Backend internship.",
                source="Test24",
                via="Test24",
                relevance_score=70.0,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
                created_at=(
                    datetime.now(timezone.utc)
                    - timedelta(days=2)
                ),
                last_seen_at=(
                    datetime.now(timezone.utc)
                    - timedelta(days=2)
                ),
            )

            db.add(recent_internship)

            await db.commit()
            await db.refresh(recent_internship)

            print(
                f"📦 Existing recent internship: "
                f"ID {recent_internship.id}"
            )

        # ====================================================
        # RUN ACTUAL SCHEDULER
        # ====================================================

        print("")
        print(
            "🚀 Running scheduler..."
        )

        # scheduler calls pipeline.process_all_active_subscriptions
        # internally, so patch the reference used by scheduler.
        monkeypatch.setattr(
            scheduler,
            "process_all_active_subscriptions",
            pipeline.process_all_active_subscriptions,
        )

        scheduler_result = (
            await scheduler.check_for_new_internships()
        )

        assert scheduler_result is None

        print(
            "CASE 1 PASSED: Scheduler completed without "
            "returning a result."
        )

        # ====================================================
        # VERIFY GLOBAL INTERNSHIP UNIQUENESS
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.url == NEW_URL
                )
            )

            new_internships = list(
                result.scalars().all()
            )

            # CRITICAL:
            # Same URL must produce ONE global row.
            assert len(new_internships) == 1

            new_internship = new_internships[0]

            print(
                f"CASE 2 PASSED: New URL stored exactly once "
                f"as Internship ID {new_internship.id}"
            )

            # ------------------------------------------------
            # New job must be <=45 days and therefore saved.
            # ------------------------------------------------

            assert new_internship.url == NEW_URL

            # ------------------------------------------------
            # Old >45-day URL must not be saved.
            # ------------------------------------------------

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.url == TOO_OLD_URL
                )
            )

            too_old = result.scalar_one_or_none()

            assert too_old is None

            print(
                "CASE 3 PASSED: New job >45 days rejected."
            )

            # ------------------------------------------------
            # Non-internship must not be saved.
            # ------------------------------------------------

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.url == INVALID_URL
                )
            )

            invalid_job = result.scalar_one_or_none()

            assert invalid_job is None

            print(
                "CASE 4 PASSED: Strict internship filter "
                "rejected non-internship."
            )

        # ====================================================
        # VERIFY USER-SPECIFIC NOTIFICATIONS
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.internship_id
                    == new_internship.id
                )
                .order_by(
                    Notification.user_email
                )
            )

            notifications = list(
                result.scalars().all()
            )

            # Both active users should receive a notification.
            assert len(notifications) == 2

            emails = {
                notification.user_email
                for notification in notifications
            }

            assert emails == {
                USER_A,
                USER_B,
            }

            print(
                "CASE 5 PASSED: Same internship correctly "
                "created user-specific notifications."
            )

            # ------------------------------------------------
            # Verify score belongs to Notification.
            # ------------------------------------------------

            for notification in notifications:

                assert notification.relevance_score == 80.0

                assert notification.status == "PENDING"

            print(
                "CASE 6 PASSED: User relevance stored on "
                "Notification."
            )

            # ------------------------------------------------
            # Inactive user must receive nothing.
            # ------------------------------------------------

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.user_email
                    == INACTIVE_USER
                )
            )

            inactive_notifications = list(
                result.scalars().all()
            )

            assert inactive_notifications == []

            print(
                "CASE 7 PASSED: Inactive subscription ignored."
            )

        # ====================================================
        # TEST DUPLICATE USER HISTORY
        # ====================================================

        async with AsyncSessionLocal() as db:

            # Run the pipeline again.
            await pipeline.process_all_active_subscriptions()

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.internship_id
                    == new_internship.id
                )
            )

            notifications_after_second_run = list(
                result.scalars().all()
            )

            # Must still be exactly two.
            assert len(
                notifications_after_second_run
            ) == 2

            print(
                "CASE 8 PASSED: User-specific duplicate "
                "protection prevented duplicate notifications."
            )

        # ====================================================
        # VERIFY EXISTING JOB PATH
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.url == OLD_URL
                )
            )

            existing = result.scalar_one_or_none()

            assert existing is not None

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.internship_id
                    == existing.id
                )
            )

            existing_notifications = list(
                result.scalars().all()
            )

            assert len(existing_notifications) == 2

            print(
                "CASE 9 PASSED: Existing ≤7-day job reused "
                "and notifications created."
            )

        # ====================================================
        # FINAL DATABASE CHECK
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.url.in_(
                        [
                            NEW_URL,
                            OLD_URL,
                        ]
                    )
                )
            )

            final_jobs = list(
                result.scalars().all()
            )

            assert len(final_jobs) == 2

            print(
                "CASE 10 PASSED: Final global catalog "
                "contains exactly the expected jobs."
            )

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                        ]
                    )
                )
            )

            final_notifications = list(
                result.scalars().all()
            )

            # 2 users × 2 eligible internships.
            assert len(final_notifications) == 4

            print(
                "CASE 11 PASSED: Final notification count "
                "is exactly 4."
            )

        print("")
        print("=" * 70)
        print(
            "🎉 TEST 24 PASSED — FINAL INTEGRATED REGRESSION"
        )
        print("=" * 70)

    finally:

        await cleanup()

        print("")
        print(
            "🧹 Test24 data cleaned up."
        )