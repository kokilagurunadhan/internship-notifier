import asyncio

from sqlalchemy import select, delete, func

import app.services.pipeline_processor as pipeline

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification


TEST_EMAIL = "kokilasudha9363@gmail.com"
TEST_COMPANY = "Test Duplicate Company 11"
TEST_DOMAIN = "software"

TEST_URL = (
    "https://example.com/jobs/"
    "test-11-duplicate-notification-20260818-002"
)


test_job = {
    "title": "Software Engineering Intern",
    "description": """
    We are looking for a Software Engineering Intern.

    You will work on software development, programming,
    Python, Java, APIs and application development.

    This internship provides hands-on software engineering
    experience.
    """,
    "company": TEST_COMPANY,
    "location": "India",
    "link": TEST_URL,
    "via": "Test 11",
    "posting_age_days": 10,
}

def fake_search_jobs(company, domain=None):
    print()
    print("TEST 11 - USING CONTROLLED TEST JOB")
    print(f"Company: {company}")
    print(f"Domain: {domain}")

    return [test_job]


pipeline.search_jobs = fake_search_jobs


async def main():

    print()
    print("=" * 70)
    print("TEST 11 - DUPLICATE NOTIFICATION PROTECTION")
    print("=" * 70)

    async with AsyncSessionLocal() as db:

        print()
        print("CHECKING TEST SUBSCRIPTION")

        result = await db.execute(
            select(Subscription).where(
                Subscription.user_email == TEST_EMAIL,
                Subscription.company.ilike(TEST_COMPANY),
                Subscription.domain == TEST_DOMAIN,
            )
        )

        subscription = result.scalar_one_or_none()

        if subscription is None:

            print("Test subscription not found.")
            print("Creating test subscription...")

            subscription = Subscription(
                user_email=TEST_EMAIL,
                company=TEST_COMPANY,
                domain=TEST_DOMAIN,
                is_active=True,
            )

            db.add(subscription)

            await db.commit()
            await db.refresh(subscription)

            print("Test subscription created.")

        else:

            print("Existing test subscription found.")

            if not subscription.is_active:

                print("Existing subscription is inactive.")
                print("Reactivating subscription...")

                subscription.is_active = True

                await db.commit()
                await db.refresh(subscription)

                print("Subscription reactivated.")

        print()
        print("CLEANING PREVIOUS TEST 11 DATA")

        internship_result = await db.execute(
            select(Internship).where(
                Internship.url == TEST_URL
            )
        )

        old_internships = internship_result.scalars().all()

        for internship in old_internships:

            await db.execute(
                delete(Notification).where(
                    Notification.internship_id == internship.id
                )
            )

            await db.delete(internship)

        await db.commit()

        print("Previous Test 11 data cleaned.")

        print()
        print("FIRST PIPELINE RUN")

        result_1 = await pipeline.process_subscription(
            subscription,
            [subscription]
        )

        print("First pipeline result:")
        print(result_1)

        internship_result = await db.execute(
            select(func.count(Internship.id)).where(
                Internship.url == TEST_URL
            )
        )

        internship_count_1 = internship_result.scalar() or 0

        notification_result = await db.execute(
            select(func.count(Notification.id))
            .join(
                Internship,
                Notification.internship_id == Internship.id
            )
            .where(
                Internship.url == TEST_URL
            )
        )

        notification_count_1 = notification_result.scalar() or 0

        print()
        print("AFTER FIRST RUN")
        print(f"Internships: {internship_count_1}")
        print(f"Notifications: {notification_count_1}")

        print()
        print("SECOND PIPELINE RUN")

        result_2 = await pipeline.process_subscription(
            subscription,
            [subscription]
        )

        print("Second pipeline result:")
        print(result_2)

        internship_result = await db.execute(
            select(func.count(Internship.id)).where(
                Internship.url == TEST_URL
            )
        )

        internship_count_2 = internship_result.scalar() or 0

        notification_result = await db.execute(
            select(func.count(Notification.id))
            .join(
                Internship,
                Notification.internship_id == Internship.id
            )
            .where(
                Internship.url == TEST_URL
            )
        )

        notification_count_2 = notification_result.scalar() or 0

        print()
        print("AFTER SECOND RUN")
        print(f"Internships: {internship_count_2}")
        print(f"Notifications: {notification_count_2}")

        notification_result = await db.execute(
            select(Notification)
            .join(
                Internship,
                Notification.internship_id == Internship.id
            )
            .where(
                Internship.url == TEST_URL
            )
            .order_by(Notification.id.asc())
        )

        notification = notification_result.scalars().first()

        print()
        print("TEST 11 ASSERTIONS")

        assert internship_count_1 == 1, (
            f"Expected 1 internship after first run, "
            f"found {internship_count_1}"
        )

        print("PASS: First run created exactly 1 Internship")

        assert notification_count_1 == 1, (
            f"Expected 1 notification after first run, "
            f"found {notification_count_1}"
        )

        print("PASS: First run created exactly 1 Notification")

        assert internship_count_2 == 1, (
            f"Expected 1 internship after second run, "
            f"found {internship_count_2}"
        )

        print("PASS: Second run did not create duplicate Internship")

        assert notification_count_2 == 1, (
            f"Expected 1 notification after second run, "
            f"found {notification_count_2}"
        )

        print("PASS: Second run did not create duplicate Notification")

        assert notification is not None

        print("PASS: Original Notification still exists")

        assert notification.user_email == TEST_EMAIL

        print("PASS: Notification belongs to correct email")

        assert str(notification.status) in (
            "PENDING",
            "NotificationStatus.PENDING"
        )

        print("PASS: Notification status is PENDING")

        print()
        print("=" * 70)
        print("TEST 11 PASSED")
        print("DUPLICATE NOTIFICATION PROTECTION VERIFIED")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())