import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.internship import Internship
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.services.internship_service import cleanup_old_internships


TEST_EMAIL = "retention-test@example.com"
TEST_COMPANY = "TEST_RETENTION_COMPANY"

OLD_URL = "https://example.com/retention-old-job"
RECENT_URL = "https://example.com/retention-recent-job"


async def cleanup_test_data():
    async with AsyncSessionLocal() as db:

        subscriptions = (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_email == TEST_EMAIL
                )
            )
        )

        for subscription in subscriptions.scalars().all():
            await db.delete(subscription)

        internships = (
            await db.execute(
                select(Internship).where(
                    Internship.url.in_(
                        [OLD_URL, RECENT_URL]
                    )
                )
            )

        )

        for internship in internships.scalars().all():
            await db.delete(internship)

        await db.commit()


async def main():

    print("=" * 70)
    print("TEST 10 - 45-DAY RETENTION CLEANUP")
    print("=" * 70)

    await cleanup_test_data()

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:

        subscription = Subscription(
            user_email=TEST_EMAIL,
            company=TEST_COMPANY,
            domain="software",
            is_active=True,
            status="ACTIVE",
        )

        db.add(subscription)

        old_internship = Internship(
            company=TEST_COMPANY,
            title="Old Retention Internship",
            location="India",
            url=OLD_URL,
            description="Old test internship",
            source="TEST",
            passed_filter=True,
            status="RELEVANT",
            last_seen_at=now - timedelta(days=46),
        )

        recent_internship = Internship(
            company=TEST_COMPANY,
            title="Recent Retention Internship",
            location="India",
            url=RECENT_URL,
            description="Recent test internship",
            source="TEST",
            passed_filter=True,
            status="RELEVANT",
            last_seen_at=now - timedelta(days=10),
        )

        db.add_all([
            old_internship,
            recent_internship,
        ])

        await db.flush()

        old_notification = Notification(
            subscription_id=subscription.id,
            user_email=TEST_EMAIL,
            internship_id=old_internship.id,
            relevance_score=80,
        )

        recent_notification = Notification(
            subscription_id=subscription.id,
            user_email=TEST_EMAIL,
            internship_id=recent_internship.id,
            relevance_score=80,
        )

        db.add_all([
            old_notification,
            recent_notification,
        ])

        await db.commit()

        old_id = old_internship.id
        recent_id = recent_internship.id

        print(f"Old internship ID    : {old_id}")
        print(f"Recent internship ID : {recent_id}")

    print()
    print("RUNNING RETENTION CLEANUP")

    deleted_count = await cleanup_old_internships()

    print(f"Deleted internships  : {deleted_count}")

    async with AsyncSessionLocal() as db:

        old_result = await db.execute(
            select(Internship).where(
                Internship.id == old_id
            )
        )

        recent_result = await db.execute(
            select(Internship).where(
                Internship.id == recent_id
            )
        )

        old_notification_result = await db.execute(
            select(Notification).where(
                Notification.internship_id == old_id
            )
        )

        recent_notification_result = await db.execute(
            select(Notification).where(
                Notification.internship_id == recent_id
            )
        )

        old_exists = (
            old_result.scalar_one_or_none()
            is not None
        )

        recent_exists = (
            recent_result.scalar_one_or_none()
            is not None
        )

        old_notification_exists = (
            old_notification_result.scalar_one_or_none()
            is not None
        )

        recent_notification_exists = (
            recent_notification_result.scalar_one_or_none()
            is not None
        )

    print()
    print("RETENTION ASSERTIONS")

    assert deleted_count == 1
    print("PASS: Exactly 1 old internship deleted")

    assert not old_exists
    print("PASS: Internship unseen for 46 days deleted")

    assert recent_exists
    print("PASS: Internship seen 10 days ago retained")

    assert not old_notification_exists
    print("PASS: Old internship notification cascade deleted")

    assert recent_notification_exists
    print("PASS: Recent internship notification retained")

    await cleanup_test_data()

    print()
    print("=" * 70)
    print("TEST 10 PASSED")
    print("45-DAY DATABASE RETENTION VERIFIED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())