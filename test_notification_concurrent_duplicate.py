import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.services.pipeline_processor import create_pending_notification


TEST_EMAIL = "kokilasudha9363@gmail.com"
TEST_COMPANY = "microsoft"

TEST_URL = (
    "https://example.com/concurrent-duplicate-test"
)


def utc_now():
    return datetime.now(timezone.utc)


async def main():

    print()
    print("=" * 70)
    print("NOTIFICATION CONCURRENT DUPLICATE TEST")
    print("=" * 70)

    internship_id = None
    subscription_id = None

    try:

        # ========================================================
        # FIND OR CREATE TEST SUBSCRIPTION
        # ========================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Subscription)
                .where(
                    Subscription.user_email == TEST_EMAIL,
                    Subscription.company == TEST_COMPANY,
                    Subscription.is_active.is_(True),
                )
                .limit(1)
            )

            subscription = result.scalar_one_or_none()

            if subscription:

                print()
                print(
                    f"Subscription found: "
                    f"{subscription.user_email}"
                )

                print(
                    f"Subscription ID: "
                    f"{subscription.id}"
                )

                print(
                    f"Company: "
                    f"{subscription.company}"
                )

                print(
                    f"Domain: "
                    f"{subscription.domain}"
                )

            else:

                print()
                print(
                    "⚠️ Test subscription not found."
                )

                print(
                    "📦 Creating test subscription..."
                )

                subscription = Subscription(
                    user_email=TEST_EMAIL,
                    company=TEST_COMPANY,
                    domain="software",
                    is_active=True,
                    created_at=utc_now(),
                )

                db.add(subscription)

                await db.flush()

                subscription_id = subscription.id

                print(
                    f"✅ Test subscription created: "
                    f"ID={subscription.id}"
                )

            # ====================================================
            # CREATE TEST INTERNSHIP
            # ====================================================

            internship = Internship(
                company=TEST_COMPANY,

                title=(
                    "Concurrent Duplicate "
                    "Protection Test Internship"
                ),

                location="Remote",

                url=TEST_URL,

                description=(
                    "Test internship for concurrent "
                    "notification duplicate protection."
                ),

                source="TEST",

                via="CONCURRENT_TEST",

                relevance_score=90.0,

                passed_filter=True,

                status="RELEVANT",

                email_sent=False,

                created_at=utc_now(),

                last_seen_at=utc_now(),
            )

            db.add(internship)

            await db.commit()

            await db.refresh(internship)

            internship_id = internship.id

            print()
            print(
                f"Test internship created: "
                f"ID={internship_id}"
            )

        # ========================================================
        # FIRST NOTIFICATION ATTEMPT
        # ========================================================

        print()
        print("=" * 70)
        print("FIRST NOTIFICATION ATTEMPT")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Subscription)
                .where(
                    Subscription.id
                    == subscription.id
                )
            )

            fresh_subscription = (
                result.scalar_one()
            )

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.id
                    == internship_id
                )
            )

            fresh_internship = (
                result.scalar_one()
            )

            first_result = (
                await create_pending_notification(
                    db=db,
                    subscription=fresh_subscription,
                    internship=fresh_internship,
                    relevance_score=90.0,
                )
            )

            await db.commit()

            print(
                f"First notification created: "
                f"{first_result}"
            )

        # ========================================================
        # SECOND NOTIFICATION ATTEMPT
        # ========================================================

        print()
        print("=" * 70)
        print("SECOND NOTIFICATION ATTEMPT")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Subscription)
                .where(
                    Subscription.id
                    == subscription.id
                )
            )

            fresh_subscription = (
                result.scalar_one()
            )

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.id
                    == internship_id
                )
            )

            fresh_internship = (
                result.scalar_one()
            )

            second_result = (
                await create_pending_notification(
                    db=db,
                    subscription=fresh_subscription,
                    internship=fresh_internship,
                    relevance_score=90.0,
                )
            )

            await db.commit()

            print(
                f"Second notification created: "
                f"{second_result}"
            )

        # ========================================================
        # CHECK DATABASE
        # ========================================================

        print()
        print("=" * 70)
        print("DATABASE RESULT")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.user_email
                    == TEST_EMAIL,

                    Notification.internship_id
                    == internship_id,
                )
                .order_by(
                    Notification.id
                )
            )

            notifications = (
                result.scalars().all()
            )

            print(
                f"Notifications found: "
                f"{len(notifications)}"
            )

            for notification in notifications:

                print(
                    f"ID={notification.id} | "
                    f"Subscription="
                    f"{notification.subscription_id} | "
                    f"Internship="
                    f"{notification.internship_id} | "
                    f"Status="
                    f"{notification.status}"
                )

        # ========================================================
        # VERIFICATION
        # ========================================================

        print()
        print("=" * 70)
        print("VERIFICATION")
        print("=" * 70)

        first_pass = (
         first_result is not None
)

        second_pass = (
    second_result is None
)

        count_pass = (
            len(notifications) == 1
        )

        subscription_pass = (
            len(notifications) == 1
            and
            notifications[0].subscription_id
            == subscription.id
        )

        print(
            "First notification created : "
            f"{'PASS' if first_pass else 'FAIL'}"
        )

        print(
            "Second notification blocked : "
            f"{'PASS' if second_pass else 'FAIL'}"
        )

        print(
            "Only 1 notification exists  : "
            f"{'PASS' if count_pass else 'FAIL'}"
        )

        print(
            "Correct subscription linked : "
            f"{'PASS' if subscription_pass else 'FAIL'}"
        )

        all_pass = (
            first_pass
            and second_pass
            and count_pass
            and subscription_pass
        )

        print()

        if all_pass:

            print("=" * 70)
            print("CONCURRENT DUPLICATE TEST PASSED")
            print("=" * 70)

        else:

            print("=" * 70)
            print("CONCURRENT DUPLICATE TEST FAILED")
            print("=" * 70)

    except Exception as error:

        print()
        print("=" * 70)
        print("❌ TEST ERROR")
        print("=" * 70)

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        raise

    finally:

        # ========================================================
        # CLEANUP
        # ========================================================

        async with AsyncSessionLocal() as db:

            if internship_id is not None:

                await db.execute(
                    delete(Notification)
                    .where(
                        Notification.internship_id
                        == internship_id
                    )
                )

                await db.execute(
                    delete(Internship)
                    .where(
                        Internship.id
                        == internship_id
                    )
                )

            if subscription_id is not None:

                await db.execute(
                    delete(Subscription)
                    .where(
                        Subscription.id
                        == subscription_id
                    )
                )

            await db.commit()

        print()
        print("Test records cleaned up.")
        print()


if __name__ == "__main__":

    asyncio.run(main())