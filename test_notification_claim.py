# ============================================================
# NOTIFICATION CLAIM TEST
# File:
# test_notification_claim.py
#
# PURPOSE:
#
# Validate the REAL production claim mechanism:
#
#     PENDING
#        ↓
#     SELECT FOR UPDATE SKIP LOCKED
#        ↓
#     PROCESSING
#        ↓
#     COMMIT
#
# IMPORTANT:
#
# This test does NOT assume that only test notifications exist.
# The production dispatcher claims ANY ready PENDING notification.
#
# Therefore existing project notifications are intentionally
# included in the test.
# ============================================================

import asyncio

from datetime import datetime, timezone

from sqlalchemy import (
    delete,
    or_,
    select,
)

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)

from app.services.notification_dispatcher import (
    _claim_pending_notifications,
)


# ============================================================
# TEST DATA
# ============================================================

TEST_EMAIL = (
    "claim-test@example.com"
)

TEST_COMPANY = (
    "TEST_CLAIM_COMPANY"
)

TEST_DOMAIN = (
    "software"
)

TEST_URLS = [

    "https://example.com/test-claim-internship-1",

    "https://example.com/test-claim-internship-2",

    "https://example.com/test-claim-internship-3",

]


# ============================================================
# UTC
# ============================================================

def utc_now():

    return datetime.now(
        timezone.utc
    )


# ============================================================
# CLEAN ONLY OUR TEST DATA
# ============================================================

async def clean_old_test_data():

    async with AsyncSessionLocal() as db:

        print()
        print(
            "🧹 Cleaning old test data..."
        )

        # ----------------------------------------------------
        # Find test subscriptions
        # ----------------------------------------------------

        subscription_result = await db.execute(

            select(
                Subscription
            ).where(

                Subscription.user_email
                == TEST_EMAIL

            )

        )

        subscriptions = list(
            subscription_result.scalars().all()
        )

        subscription_ids = [

            subscription.id

            for subscription
            in subscriptions

        ]

        # ----------------------------------------------------
        # Delete notifications belonging to our test user
        # ----------------------------------------------------

        await db.execute(

            delete(
                Notification
            ).where(

                Notification.user_email
                == TEST_EMAIL

            )

        )

        # ----------------------------------------------------
        # Delete test internships
        # ----------------------------------------------------

        await db.execute(

            delete(
                Internship
            ).where(

                Internship.url.in_(
                    TEST_URLS
                )

            )

        )

        # ----------------------------------------------------
        # Delete test subscriptions
        # ----------------------------------------------------

        await db.execute(

            delete(
                Subscription
            ).where(

                Subscription.user_email
                == TEST_EMAIL

            )

        )

        await db.commit()

        print(
            "✅ Old test data cleaned."
        )


# ============================================================
# CREATE TEST DATA
# ============================================================

async def create_test_data():

    async with AsyncSessionLocal() as db:

        print()
        print(
            "📦 Creating test data..."
        )

        # ----------------------------------------------------
        # Subscription
        # ----------------------------------------------------

        subscription = Subscription(

            user_email=TEST_EMAIL,

            company=TEST_COMPANY,

            domain=TEST_DOMAIN,

            is_active=True,

        )

        db.add(
            subscription
        )

        await db.flush()

        print(
            f"🆔 Subscription ID: "
            f"{subscription.id}"
        )

        # ----------------------------------------------------
        # Three DIFFERENT internships
        # ----------------------------------------------------

        internships = []

        now = utc_now()

        for index, url in enumerate(

            TEST_URLS,

            start=1

        ):

            internship = Internship(

                company=TEST_COMPANY,

                title=(
                    f"Claim Test "
                    f"Internship {index}"
                ),

                location="India",

                url=url,

                description=(
                    "Test internship for "
                    "notification claim validation."
                ),

                source="TEST",

                via="TEST",

                relevance_score=90.0,

                passed_filter=True,

                status="NEW",

                email_sent=False,

                created_at=now,

            )

            db.add(
                internship
            )

            internships.append(
                internship
            )

        await db.flush()

        print(
            "🆔 Internship IDs:"
        )

        for internship in internships:

            print(
                f"   Internship "
                f"{internship.id}"
            )

        # ----------------------------------------------------
        # One notification per internship
        # ----------------------------------------------------

        notifications = []

        for internship in internships:

            notification = Notification(

                subscription_id=(
                    subscription.id
                ),

                user_email=TEST_EMAIL,

                internship_id=(
                    internship.id
                ),

                status=(
                    NotificationStatus.PENDING
                ),

                relevance_score=90.0,

                created_at=now,

                updated_at=now,

                retry_count=0,

            )

            db.add(
                notification
            )

            notifications.append(
                notification
            )

        await db.commit()

        notification_ids = [

            notification.id

            for notification
            in notifications

        ]

        print()
        print(
            "🔔 Created "
            f"{len(notification_ids)} "
            "PENDING notifications."
        )

        print(
            f"📦 Test notification IDs: "
            f"{notification_ids}"
        )

        return notification_ids


# ============================================================
# GET ALL READY PENDING NOTIFICATIONS
# ============================================================

async def get_ready_pending_ids():

    async with AsyncSessionLocal() as db:

        now = utc_now()

        result = await db.execute(

            select(
                Notification.id
            ).where(

                Notification.status
                == NotificationStatus.PENDING,

                or_(

                    Notification.next_retry_at.is_(None),

                    Notification.next_retry_at
                    <= now,

                ),

            )

        )

        return set(
            result.scalars().all()
        )


# ============================================================
# ONE CLAIM WORKER
# ============================================================

async def claim_worker(
    worker_name,
    batch_size,
):

    print(
        f"👷 {worker_name} starting..."
    )

    async with AsyncSessionLocal() as db:

        claimed_ids = (

            await _claim_pending_notifications(

                db,

                batch_size=batch_size,

            )

        )

        print(

            f"👷 {worker_name}: "
            f"claimed={claimed_ids}"

        )

        return claimed_ids


# ============================================================
# VERIFY DATABASE STATE
# ============================================================

async def verify_database_state(
    expected_ids,
):

    async with AsyncSessionLocal() as db:

        result = await db.execute(

            select(
                Notification
            ).where(

                Notification.id.in_(
                    expected_ids
                )

            )

        )

        notifications = list(
            result.scalars().all()
        )

        print()
        print(
            "=" * 70
        )

        print(
            "📊 DATABASE STATE"
        )

        print(
            "=" * 70
        )

        for notification in sorted(

            notifications,

            key=lambda item: item.id

        ):

            print(

                f"Notification "
                f"{notification.id}: "

                f"status="
                f"{notification.status}, "

                f"processing_started_at="
                f"{notification.processing_started_at}"

            )

        # ----------------------------------------------------
        # Every notification claimed by this test must now
        # be PROCESSING.
        # ----------------------------------------------------

        for notification in notifications:

            assert (

                notification.status
                == NotificationStatus.PROCESSING

            ), (

                f"❌ Notification "
                f"{notification.id} "
                f"was not moved to PROCESSING."

            )

            assert (

                notification.processing_started_at
                is not None

            ), (

                f"❌ Notification "
                f"{notification.id} "
                f"has no processing_started_at."

            )


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    print(
        "=" * 70
    )

    print(
        "🧪 NOTIFICATION CLAIM TEST"
    )

    print(
        "=" * 70
    )

    # ========================================================
    # CLEAN OUR TEST DATA
    # ========================================================

    await clean_old_test_data()

    # ========================================================
    # CREATE OUR TEST DATA
    # ========================================================

    test_notification_ids = (

        await create_test_data()

    )

    # ========================================================
    # SNAPSHOT READY QUEUE
    #
    # IMPORTANT:
    #
    # Production claim is global.
    #
    # Therefore we capture ALL ready notifications before
    # starting the workers.
    # ========================================================

    ready_before = (

        await get_ready_pending_ids()

    )

    print()
    print(
        "📋 READY PENDING QUEUE BEFORE CLAIM:"
    )

    print(
        sorted(ready_before)
    )

    print(
        f"📦 Ready notifications: "
        f"{len(ready_before)}"
    )

    # --------------------------------------------------------
    # Confirm our test notifications are ready
    # --------------------------------------------------------

    missing_test_ids = (

        set(test_notification_ids)
        -
        ready_before

    )

    assert not missing_test_ids, (

        "❌ Some test notifications "
        "were not ready for claiming: "
        f"{sorted(missing_test_ids)}"

    )

    # ========================================================
    # CONCURRENT CLAIM
    # ========================================================

    # Split the current ready queue between two workers.
    #
    # Example:
    #
    # 7 ready notifications
    #
    # batch_size = 4
    #
    # Worker 1 → up to 4
    # Worker 2 → remaining 3
    #
    # SKIP LOCKED prevents overlap.
    # ========================================================

    worker_batch_size = (

        (
            len(ready_before)
            +
            1
        )
        //
        2

    )

    print()
    print(
        "🚀 Starting 2 workers "
        "simultaneously..."
    )

    print(
        f"   Ready queue size: "
        f"{len(ready_before)}"
    )

    print(
        f"   Batch size per worker: "
        f"{worker_batch_size}"
    )

    worker_results = await asyncio.gather(

        claim_worker(

            "Worker 1",

            batch_size=worker_batch_size,

        ),

        claim_worker(

            "Worker 2",

            batch_size=worker_batch_size,

        ),

    )

    # ========================================================
    # NORMALIZE RESULTS
    # ========================================================

    worker_1_ids = set(
        worker_results[0]
    )

    worker_2_ids = set(
        worker_results[1]
    )

    combined_ids = (

        worker_1_ids
        |
        worker_2_ids

    )

    overlap = (

        worker_1_ids
        &
        worker_2_ids

    )

    # ========================================================
    # DISPLAY
    # ========================================================

    print()
    print(
        "=" * 70
    )

    print(
        "📊 WORKER RESULTS"
    )

    print(
        "=" * 70
    )

    print(
        f"Worker 1: "
        f"{sorted(worker_1_ids)}"
    )

    print(
        f"Worker 2: "
        f"{sorted(worker_2_ids)}"
    )

    print()
    print(
        f"Total unique claimed: "
        f"{len(combined_ids)}"
    )

    print(
        f"Overlap between workers: "
        f"{sorted(overlap)}"
    )

    # ========================================================
    # TEST 1 — NO OVERLAP
    # ========================================================

    assert not overlap, (

        "❌ SAME notification was "
        "claimed by multiple workers!"

    )

    print(
        "✅ No notification was claimed "
        "by both workers."
    )

    # ========================================================
    # TEST 2 — EVERY READY NOTIFICATION CLAIMED
    # ========================================================

    missing_ids = (

        ready_before
        -
        combined_ids

    )

    assert not missing_ids, (

        "❌ Some ready notifications "
        "were not claimed: "
        f"{sorted(missing_ids)}"

    )

    print(
        "✅ Every ready PENDING notification "
        "was claimed."
    )

    # ========================================================
    # TEST 3 — NOTHING EXTRA CLAIMED
    # ========================================================

    unexpected_ids = (

        combined_ids
        -
        ready_before

    )

    assert not unexpected_ids, (

        "❌ Worker claimed notification(s) "
        "that were not ready before the test: "
        f"{sorted(unexpected_ids)}"

    )

    print(
        "✅ No unexpected notification "
        "was claimed."
    )

    # ========================================================
    # TEST 4 — OUR TEST NOTIFICATIONS CLAIMED
    # ========================================================

    test_claimed = (

        set(test_notification_ids)
        &
        combined_ids

    )

    assert (

        test_claimed
        ==
        set(test_notification_ids)

    ), (

        "❌ Not all test notifications "
        "were claimed."

    )

    print(
        "✅ All test notifications "
        "were claimed."
    )

    # ========================================================
    # VERIFY DATABASE
    # ========================================================

    await verify_database_state(
        combined_ids
    )

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print()
    print(
        "=" * 70
    )

    print(
        "🧪 TEST RESULT"
    )

    print(
        "=" * 70
    )

    print(
        "✅ TEST PASSED"
    )

    print(
        "PostgreSQL SELECT FOR UPDATE "
        "SKIP LOCKED prevented duplicate claims."
    )

    print(
        "Concurrent workers claimed each "
        "ready notification exactly once."
    )

    print(
        "All claimed notifications transitioned "
        "from PENDING → PROCESSING."
    )

    print(
        "=" * 70
    )


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )