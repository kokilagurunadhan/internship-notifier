# ============================================================
# CONCURRENT NOTIFICATION TEST
#
# Purpose:
# Verify that multiple workers attempting to create the
# SAME notification simultaneously cannot create duplicates.
#
# Expected:
#   10 workers
#       ↓
#   same user + same internship
#       ↓
#   PostgreSQL UNIQUE(user_email, internship_id)
#       ↓
#   exactly ONE notification
# ============================================================

import asyncio

from sqlalchemy import select, func

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription

from app.models.internship import Internship

from app.models.notification import (
    Notification,
)

from app.services.pipeline_processor import (
    create_pending_notification,
)


# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_EMAIL = "notification-race-test@example.com"

TEST_COMPANY = "TEST_NOTIFICATION_COMPANY"

TEST_TITLE = "Test Software Engineering Internship"

TEST_URL = (
    "https://example.com/test-notification-race-job"
)

NUMBER_OF_WORKERS = 10


# ============================================================
# CREATE / GET TEST SUBSCRIPTION
# ============================================================

async def get_or_create_subscription():

    async with AsyncSessionLocal() as db:

        result = await db.execute(

            select(
                Subscription
            )
            .where(
                Subscription.user_email
                == TEST_EMAIL
            )
            .limit(1)
        )

        subscription = (
            result.scalar_one_or_none()
        )

        if subscription:

            return subscription.id

        subscription = Subscription(

            user_email=TEST_EMAIL,

            company=TEST_COMPANY,

            domain="software",

            is_active=True,
        )

        db.add(subscription)

        await db.commit()

        await db.refresh(
            subscription
        )

        return subscription.id


# ============================================================
# CREATE / GET TEST INTERNSHIP
# ============================================================

async def get_or_create_internship():

    async with AsyncSessionLocal() as db:

        result = await db.execute(

            select(
                Internship
            )
            .where(
                Internship.url
                == TEST_URL
            )
            .limit(1)
        )

        internship = (
            result.scalar_one_or_none()
        )

        if internship:

            return internship.id

        internship = Internship(

            company=TEST_COMPANY,

            title=TEST_TITLE,

            location="Remote",

            url=TEST_URL,

            description=(
                "Test internship for "
                "notification concurrency testing."
            ),

            source="TEST",

            via="TEST",

            relevance_score=90.0,

            passed_filter=True,

            status="RELEVANT",

            email_sent=False,
        )

        db.add(internship)

        await db.commit()

        await db.refresh(
            internship
        )

        return internship.id


# ============================================================
# GET TEST OBJECTS
# ============================================================

async def prepare_test_data():

    subscription_id = (
        await get_or_create_subscription()
    )

    internship_id = (
        await get_or_create_internship()
    )

    async with AsyncSessionLocal() as db:

        subscription_result = await db.execute(

            select(
                Subscription
            )
            .where(
                Subscription.id
                == subscription_id
            )
        )

        subscription = (
            subscription_result.scalar_one()
        )

        internship_result = await db.execute(

            select(
                Internship
            )
            .where(
                Internship.id
                == internship_id
            )
        )

        internship = (
            internship_result.scalar_one()
        )

        return (
            subscription,
            internship,
        )


# ============================================================
# CLEAN OLD TEST NOTIFICATIONS
#
# We remove previous test notifications so every run starts
# cleanly.
# ============================================================

async def cleanup_old_notifications(
    subscription,
    internship,
):

    async with AsyncSessionLocal() as db:

        result = await db.execute(

            select(
                Notification
            )
            .where(

                Notification.user_email
                == TEST_EMAIL,

                Notification.internship_id
                == internship.id,
            )
        )

        notifications = (
            result.scalars().all()
        )

        for notification in notifications:

            await db.delete(
                notification
            )

        await db.commit()

        print(
            f"🧹 Removed {len(notifications)} "
            f"old test notification(s)"
        )


# ============================================================
# ONE WORKER
# ============================================================

async def notification_worker(
    worker_number,
    subscription_id,
    internship_id,
):

    print(
        f"👷 Worker {worker_number} starting..."
    )

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # Load subscription
        # ----------------------------------------------------

        subscription_result = await db.execute(

            select(
                Subscription
            )
            .where(
                Subscription.id
                == subscription_id
            )
        )

        subscription = (
            subscription_result.scalar_one()
        )

        # ----------------------------------------------------
        # Load internship
        # ----------------------------------------------------

        internship_result = await db.execute(

            select(
                Internship
            )
            .where(
                Internship.id
                == internship_id
            )
        )

        internship = (
            internship_result.scalar_one()
        )

        # ----------------------------------------------------
        # Simultaneous start
        #
        # Small scheduling yield makes it more likely that
        # all workers reach the duplicate check around the
        # same time.
        # ----------------------------------------------------

        await asyncio.sleep(0)

        try:

            created = (
                await create_pending_notification(

                    db=db,

                    subscription=subscription,

                    internship=internship,

                    relevance_score=90.0,
                )
            )

            await db.commit()

            print(
                f"👷 Worker {worker_number}: "
                f"created={created}"
            )

            return created

        except Exception as error:

            await db.rollback()

            print(
                f"❌ Worker {worker_number} failed: "
                f"{error}"
            )

            return False


# ============================================================
# COUNT NOTIFICATIONS
# ============================================================

async def count_test_notifications(
    internship_id,
):

    async with AsyncSessionLocal() as db:

        result = await db.execute(

            select(
                func.count(
                    Notification.id
                )
            )
            .where(

                Notification.user_email
                == TEST_EMAIL,

                Notification.internship_id
                == internship_id,
            )
        )

        return result.scalar_one()


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    print()
    print("=" * 70)
    print(
        "🧪 CONCURRENT NOTIFICATION TEST"
    )
    print("=" * 70)

    print()
    print(
        f"👥 Workers: {NUMBER_OF_WORKERS}"
    )

    print(
        f"📧 User: {TEST_EMAIL}"
    )

    print(
        f"🏢 Company: {TEST_COMPANY}"
    )

    # ========================================================
    # PREPARE
    # ========================================================

    subscription, internship = (
        await prepare_test_data()
    )

    print()
    print(
        f"🆔 Subscription ID: "
        f"{subscription.id}"
    )

    print(
        f"🆔 Internship ID: "
        f"{internship.id}"
    )

    # ========================================================
    # CLEAN OLD DATA
    # ========================================================

    await cleanup_old_notifications(

        subscription,

        internship,
    )

    # ========================================================
    # START WORKERS
    # ========================================================

    print()
    print(
        f"🚀 Starting "
        f"{NUMBER_OF_WORKERS} workers simultaneously..."
    )

    tasks = [

        notification_worker(

            worker_number=i,

            subscription_id=subscription.id,

            internship_id=internship.id,
        )

        for i in range(
            1,
            NUMBER_OF_WORKERS + 1,
        )
    ]

    results = await asyncio.gather(
        *tasks
    )

    # ========================================================
    # RESULTS
    # ========================================================

    created_count = sum(
        1
        for result in results
        if result
    )

    database_count = (
        await count_test_notifications(
            internship.id
        )
    )

    print()
    print("=" * 70)
    print(
        "📊 WORKER RESULTS"
    )
    print("=" * 70)

    for index, result in enumerate(
        results,
        start=1,
    ):

        print(
            f"Worker {index}: "
            f"created={result}"
        )

    print()
    print(
        f"Successful creations: "
        f"{created_count}"
    )

    print(
        f"Database notifications: "
        f"{database_count}"
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    print()
    print("=" * 70)
    print(
        "🧪 TEST RESULT"
    )
    print("=" * 70)

    if (
        created_count == 1
        and database_count == 1
    ):

        print()
        print(
            "✅ TEST PASSED"
        )

        print(
            "PostgreSQL prevented duplicate "
            "notifications."
        )

        print(
            f"Exactly ONE notification exists "
            f"for {TEST_EMAIL} + "
            f"Internship {internship.id}."
        )

    else:

        print()
        print(
            "❌ TEST FAILED"
        )

        print(
            f"Expected successful creations: 1"
        )

        print(
            f"Actual successful creations: "
            f"{created_count}"
        )

        print(
            f"Expected database records: 1"
        )

        print(
            f"Actual database records: "
            f"{database_count}"
        )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )