
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification, NotificationStatus
from app.services.pipeline_processor import (
    process_job_for_user,
    canonicalize_job_url,
)


# ============================================================
# TEST 17 — USER-SPECIFIC DUPLICATE LOGIC
# ============================================================

TEST_EMAIL_A = "test17_user_a@example.com"
TEST_EMAIL_B = "test17_user_b@example.com"

COMPANY = "Test17 Duplicate Company"

URL_A = "https://example.com/test17/internship-a"
URL_B = "https://example.com/test17/internship-b"


def utc_now():
    return datetime.now(timezone.utc)


def make_job(title: str, url: str):
    return {
        "company": COMPANY,
        "title": title,
        "location": "Remote",
        "url": url,
        "description": (
            "Software engineering internship involving "
            "Python programming, backend development and APIs."
        ),
        "source": "test17",
        "via": "test17",
    }


@pytest.mark.asyncio
async def test_user_specific_duplicate_logic():

    async with AsyncSessionLocal() as db:

        # ====================================================
        # CLEANUP OLD TEST 17 DATA
        # ====================================================

        old_subscriptions_result = await db.execute(
            select(Subscription).where(
                Subscription.user_email.in_(
                    [TEST_EMAIL_A, TEST_EMAIL_B]
                )
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
                Internship.url.in_(
                    [
                        canonicalize_job_url(URL_A),
                        canonicalize_job_url(URL_B),
                    ]
                )
            )
        )

        await db.commit()

        # ====================================================
        # CREATE SUBSCRIPTIONS
        # ====================================================

        subscription_a = Subscription(
            user_email=TEST_EMAIL_A,
            company=COMPANY,
            domain="software",
            is_active=True,
        )

        subscription_b = Subscription(
            user_email=TEST_EMAIL_B,
            company=COMPANY,
            domain="software",
            is_active=True,
        )

        db.add_all(
            [
                subscription_a,
                subscription_b,
            ]
        )

        await db.flush()

        # ====================================================
        # CREATE TWO EXISTING INTERNSHIPS
        # ====================================================

        internship_a = Internship(
            company=COMPANY,
            title="Software Engineering Intern A",
            location="Remote",
            url=canonicalize_job_url(URL_A),
            description="Software engineering internship",
            source="test17",
            via="test17",
            relevance_score=80.0,
            passed_filter=True,
            status="RELEVANT",
            email_sent=False,
            created_at=utc_now() - timedelta(days=1),
            last_seen_at=utc_now() - timedelta(days=1),
        )

        internship_b = Internship(
            company=COMPANY,
            title="Software Engineering Intern B",
            location="Remote",
            url=canonicalize_job_url(URL_B),
            description="Software engineering internship",
            source="test17",
            via="test17",
            relevance_score=85.0,
            passed_filter=True,
            status="RELEVANT",
            email_sent=False,
            created_at=utc_now() - timedelta(days=1),
            last_seen_at=utc_now() - timedelta(days=1),
        )

        db.add_all(
            [
                internship_a,
                internship_b,
            ]
        )

        await db.flush()

        # ====================================================
        # PRE-SEED:
        #
        # USER A ALREADY RECEIVED INTERNSHIP A
        # ====================================================

        existing_notification = Notification(
            subscription_id=subscription_a.id,
            user_email=TEST_EMAIL_A,
            internship_id=internship_a.id,
            status=NotificationStatus.SENT,
            relevance_score=80.0,
            created_at=utc_now() - timedelta(hours=1),
            updated_at=utc_now() - timedelta(hours=1),
            sent_at=utc_now() - timedelta(hours=1),
        )

        db.add(existing_notification)

        await db.commit()

        # ====================================================
        # CASE 1
        #
        # SAME USER + SAME INTERNSHIP
        #
        # Expected:
        # NO NEW NOTIFICATION
        # ====================================================

        job_a = make_job(
            "Software Engineering Intern A",
            URL_A,
        )

        result_case_1 = await process_job_for_user(
            db=db,
            job=job_a,
            subscription=subscription_a,
        )

        await db.commit()

        notifications_case_1 = (
            await db.execute(
                select(Notification).where(
                    Notification.subscription_id
                    == subscription_a.id,
                    Notification.internship_id
                    == internship_a.id,
                )
            )
        )

        rows_case_1 = (
            notifications_case_1.scalars().all()
        )

        assert len(rows_case_1) == 1, (
            "Same user + same internship created "
            "a duplicate notification."
        )

        print(
            "✅ CASE 1 PASSED: "
            "Same user + same internship → no duplicate"
        )

        # ====================================================
        # CASE 2
        #
        # DIFFERENT USER + SAME INTERNSHIP
        #
        # Expected:
        # NEW PENDING NOTIFICATION
        # ====================================================

        result_case_2 = await process_job_for_user(
            db=db,
            job=job_a,
            subscription=subscription_b,
        )

        await db.commit()

        notifications_case_2 = (
            await db.execute(
                select(Notification).where(
                    Notification.subscription_id
                    == subscription_b.id,
                    Notification.internship_id
                    == internship_a.id,
                )
            )
        )

        rows_case_2 = (
            notifications_case_2.scalars().all()
        )

        assert len(rows_case_2) == 1, (
            "Different user + same internship did not "
            "create a notification."
        )

        assert (
            rows_case_2[0].status
            == NotificationStatus.PENDING
        ), (
            "Different user + same internship should "
            "create a PENDING notification."
        )

        print(
            "✅ CASE 2 PASSED: "
            "Different user + same internship → allowed"
        )

        # ====================================================
        # CASE 3
        #
        # SAME USER + DIFFERENT INTERNSHIP
        #
        # Expected:
        # NEW PENDING NOTIFICATION
        # ====================================================

        job_b = make_job(
            "Software Engineering Intern B",
            URL_B,
        )

        result_case_3 = await process_job_for_user(
            db=db,
            job=job_b,
            subscription=subscription_a,
        )

        await db.commit()

        notifications_case_3 = (
            await db.execute(
                select(Notification).where(
                    Notification.subscription_id
                    == subscription_a.id,
                    Notification.internship_id
                    == internship_b.id,
                )
            )
        )

        rows_case_3 = (
            notifications_case_3.scalars().all()
        )

        assert len(rows_case_3) == 1, (
            "Same user + different internship did not "
            "create a notification."
        )

        assert (
            rows_case_3[0].status
            == NotificationStatus.PENDING
        ), (
            "Same user + different internship should "
            "create a PENDING notification."
        )

        print(
            "✅ CASE 3 PASSED: "
            "Same user + different internship → allowed"
        )

        # ====================================================
        # FINAL VERIFICATION
        # ====================================================

        all_notifications_result = await db.execute(
            select(Notification).where(
                Notification.subscription_id.in_(
                    [
                        subscription_a.id,
                        subscription_b.id,
                    ]
                )
            )
        )

        all_notifications = (
            all_notifications_result.scalars().all()
        )

        assert len(all_notifications) == 3, (
            "Expected exactly 3 notifications total:\n"
            "1. User A + Internship A\n"
            "2. User B + Internship A\n"
            "3. User A + Internship B"
        )

        print()
        print("=" * 65)
        print("🎉 TEST 17 PASSED")
        print("=" * 65)
        print(
            "Same user + same internship → BLOCKED"
        )
        print(
            "Different user + same internship → ALLOWED"
        )
        print(
            "Same user + different internship → ALLOWED"
        )
        print("=" * 65)

