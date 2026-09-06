
# ============================================================
# TEST 25 — FINAL DISPATCHER INTEGRATION REGRESSION
# ============================================================
#
# File:
# test_25_final_dispatcher_regression.py
#
# PURPOSE:
#
# PENDING
#    ↓
# CLAIM
#    ↓
# PROCESSING
#    ↓
# GROUP BY EMAIL
#    ↓
# PRIORITY
#    ↓
# MAX 15
#    ↓
# IDEMPOTENCY
#    ↓
# SEND EMAIL
#    ↓
# SENT
#
# ALSO CHECKS:
# - Multiple users
# - One digest per user
# - Recent internships first
# - Relevance ordering
# - MAX 15
# - Remaining notifications deferred
# - sent_at
# - processing_started_at cleared
# - retry state cleared
# - idempotency
# - second dispatch creates no duplicate email
#
# ============================================================


import asyncio

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)

import app.services.notification_dispatcher as dispatcher


# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_EMAIL_A = "test25_user_a@example.com"
TEST_EMAIL_B = "test25_user_b@example.com"

TEST_COMPANY = "test25_dispatcher"
TEST_DOMAIN = "software"

TEST_URL_PREFIX = (
    "https://test25.example.com/internship-"
)

TOTAL_JOBS = 20
MAX_EXPECTED_PER_EMAIL = 15


# ============================================================
# FAKE EMAIL PROVIDER
# ============================================================

fake_email_calls = []


def fake_send_notification_email(
    recipient_email,
    internships,
    idempotency_key,
):
    """
    Fake email provider used only by Test 25.
    """

    fake_email_calls.append(
        {
            "recipient_email": recipient_email,
            "internships": internships,
            "idempotency_key": idempotency_key,
        }
    )

    print()
    print("📧 FAKE EMAIL PROVIDER CALLED")
    print(f"   Recipient   : {recipient_email}")
    print(f"   Jobs        : {len(internships)}")
    print(f"   Idempotency : {idempotency_key}")

    return {
        "id": "test25-fake-email-id",
        "status": "sent",
    }


# ============================================================
# UTC HELPER
# ============================================================

def utc_now():
    return datetime.now(timezone.utc)


# ============================================================
# CLEANUP
# ============================================================

async def cleanup_test_records():

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # FIND TEST SUBSCRIPTIONS
        # ----------------------------------------------------

        subscription_result = await db.execute(
            select(Subscription).where(
                Subscription.user_email.in_(
                    [
                        TEST_EMAIL_A,
                        TEST_EMAIL_B,
                    ]
                )
            )
        )

        subscriptions = (
            subscription_result.scalars().all()
        )

        subscription_ids = [
            subscription.id
            for subscription in subscriptions
        ]

        # ----------------------------------------------------
        # FIND TEST INTERNSHIPS
        # ----------------------------------------------------

        internship_result = await db.execute(
            select(Internship).where(
                Internship.url.like(
                    f"{TEST_URL_PREFIX}%"
                )
            )
        )

        internships = (
            internship_result.scalars().all()
        )

        internship_ids = [
            internship.id
            for internship in internships
        ]

        # ----------------------------------------------------
        # DELETE NOTIFICATIONS
        # ----------------------------------------------------

        if subscription_ids:

            await db.execute(
                delete(Notification).where(
                    Notification.subscription_id.in_(
                        subscription_ids
                    )
                )
            )

        if internship_ids:

            await db.execute(
                delete(Notification).where(
                    Notification.internship_id.in_(
                        internship_ids
                    )
                )
            )

        # ----------------------------------------------------
        # DELETE INTERNSHIPS
        # ----------------------------------------------------

        if internship_ids:

            await db.execute(
                delete(Internship).where(
                    Internship.id.in_(
                        internship_ids
                    )
                )
            )

        # ----------------------------------------------------
        # DELETE SUBSCRIPTIONS
        # ----------------------------------------------------

        if subscription_ids:

            await db.execute(
                delete(Subscription).where(
                    Subscription.id.in_(
                        subscription_ids
                    )
                )
            )

        await db.commit()


# ============================================================
# CREATE TEST DATA
# ============================================================

async def create_test_data():

    notification_ids_a = []
    notification_ids_b = []

    internship_ids = []

    async with AsyncSessionLocal() as db:

        print()
        print("=" * 70)
        print("CREATING TEST 25 DATA")
        print("=" * 70)

        # ====================================================
        # SUBSCRIPTIONS
        # ====================================================

        subscription_a = Subscription(
            user_email=TEST_EMAIL_A,
            company=TEST_COMPANY,
            domain=TEST_DOMAIN,
            is_active=True,
        )

        subscription_b = Subscription(
            user_email=TEST_EMAIL_B,
            company=TEST_COMPANY,
            domain=TEST_DOMAIN,
            is_active=True,
        )

        db.add(subscription_a)
        db.add(subscription_b)

        await db.flush()

        print(
            f"👤 User A subscription ID : "
            f"{subscription_a.id}"
        )

        print(
            f"👤 User B subscription ID : "
            f"{subscription_b.id}"
        )

        # ====================================================
        # INTERNSHIPS
        # ====================================================

        now = utc_now()

        internships = []

        for index in range(1, TOTAL_JOBS + 1):

            # ------------------------------------------------
            # JOBS 1–5 = RECENT
            # ------------------------------------------------

            if index <= 5:

                created_at = (
                    now
                    - timedelta(hours=index)
                )

            # ------------------------------------------------
            # JOBS 6–20 = OLDER
            # ------------------------------------------------

            else:

                created_at = (
                    now
                    - timedelta(
                        days=2,
                        hours=index,
                    )
                )

            # ------------------------------------------------
            # SCORE
            #
            # Job 1 = 99
            # Job 2 = 98
            # ...
            # Job 20 = 80
            # ------------------------------------------------

            relevance_score = (
                100.0 - index
            )

            internship = Internship(
                company=TEST_COMPANY,
                title=(
                    "Test25 Software "
                    "Engineering Intern "
                    f"{index}"
                ),
                location="Remote",
                url=(
                    f"{TEST_URL_PREFIX}"
                    f"{index:03d}"
                ),
                description=(
                    "Software engineering "
                    "internship for Test 25 "
                    "dispatcher regression."
                ),
                source="test25",
                via="test25",
                relevance_score=relevance_score,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
                created_at=created_at,
                last_seen_at=created_at,
            )

            internships.append(internship)

            db.add(internship)

        await db.flush()

        internship_ids = [
            internship.id
            for internship in internships
        ]

        print()
        print(
            f"📦 Internships created : "
            f"{len(internships)}"
        )

        # ====================================================
        # NOTIFICATIONS
        # ====================================================

        for internship in internships:

            # ------------------------------------------------
            # USER A
            # ------------------------------------------------

            notification_a = Notification(
                subscription_id=subscription_a.id,
                user_email=TEST_EMAIL_A,
                internship_id=internship.id,
                relevance_score=(
                    internship.relevance_score
                ),
                status=NotificationStatus.PENDING,
            )

            # ------------------------------------------------
            # USER B
            # ------------------------------------------------

            notification_b = Notification(
                subscription_id=subscription_b.id,
                user_email=TEST_EMAIL_B,
                internship_id=internship.id,
                relevance_score=(
                    internship.relevance_score
                ),
                status=NotificationStatus.PENDING,
            )

            db.add(notification_a)
            db.add(notification_b)

            notification_ids_a.append(
                notification_a
            )

            notification_ids_b.append(
                notification_b
            )

        await db.commit()

        ids_a = [
            notification.id
            for notification
            in notification_ids_a
        ]

        ids_b = [
            notification.id
            for notification
            in notification_ids_b
        ]

        print(
            f"🔔 User A notifications : "
            f"{len(ids_a)}"
        )

        print(
            f"🔔 User B notifications : "
            f"{len(ids_b)}"
        )

        assert len(ids_a) == TOTAL_JOBS
        assert len(ids_b) == TOTAL_JOBS

        print(
            "20 PENDING notifications per user : PASS"
        )

        return (
            ids_a,
            ids_b,
            internship_ids,
        )


# ============================================================
# VERIFY FIRST DISPATCH
# ============================================================

async def verify_first_dispatch(
    notification_ids_a,
    notification_ids_b,
):

    print()
    print("=" * 70)
    print("VERIFYING FIRST DISPATCH")
    print("=" * 70)

    # ========================================================
    # FIND EMAILS
    # ========================================================

    user_a_calls = [
        call
        for call in fake_email_calls
        if call["recipient_email"]
        == TEST_EMAIL_A
    ]

    user_b_calls = [
        call
        for call in fake_email_calls
        if call["recipient_email"]
        == TEST_EMAIL_B
    ]

    # ========================================================
    # ONE DIGEST PER USER
    # ========================================================

    assert len(user_a_calls) == 1, (
        "Expected exactly one digest "
        "for User A."
    )

    assert len(user_b_calls) == 1, (
        "Expected exactly one digest "
        "for User B."
    )

    print(
        "User A → exactly one digest : PASS"
    )

    print(
        "User B → exactly one digest : PASS"
    )

    # ========================================================
    # MAX 15
    # ========================================================

    digest_a = user_a_calls[0]
    digest_b = user_b_calls[0]

    jobs_a = digest_a["internships"]
    jobs_b = digest_b["internships"]

    assert len(jobs_a) == 15, (
        "User A digest must contain 15 jobs."
    )

    assert len(jobs_b) == 15, (
        "User B digest must contain 15 jobs."
    )

    print(
        "User A → MAX 15 : PASS"
    )

    print(
        "User B → MAX 15 : PASS"
    )

    # ========================================================
    # RECENT JOBS FIRST
    # ========================================================

    expected_recent_titles = [
        (
            "Test25 Software "
            "Engineering Intern "
            f"{index}"
        )
        for index in range(1, 6)
    ]

    actual_recent_titles_a = [
        job["title"]
        for job in jobs_a[:5]
    ]

    actual_recent_titles_b = [
        job["title"]
        for job in jobs_b[:5]
    ]

    assert (
        actual_recent_titles_a
        == expected_recent_titles
    ), (
        "User A recent-job priority "
        "is incorrect."
    )

    assert (
        actual_recent_titles_b
        == expected_recent_titles
    ), (
        "User B recent-job priority "
        "is incorrect."
    )

    print(
        "User A → recent jobs first : PASS"
    )

    print(
        "User B → recent jobs first : PASS"
    )

    # ========================================================
    # RELEVANCE ORDER
    # ========================================================

    scores_a = [
        job["relevance_score"]
        for job in jobs_a[:5]
    ]

    expected_scores = [
        99.0,
        98.0,
        97.0,
        96.0,
        95.0,
    ]

    assert scores_a == expected_scores, (
        "User A relevance ordering is incorrect."
    )

    scores_b = [
        job["relevance_score"]
        for job in jobs_b[:5]
    ]

    assert scores_b == expected_scores, (
        "User B relevance ordering is incorrect."
    )

    print(
        "User A → relevance descending : PASS"
    )

    print(
        "User B → relevance descending : PASS"
    )

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    key_a = digest_a["idempotency_key"]
    key_b = digest_b["idempotency_key"]

    assert key_a
    assert key_b

    assert key_a.startswith(
        "internship-digest:"
    )

    assert key_b.startswith(
        "internship-digest:"
    )

    assert key_a != key_b, (
        "Different users must have "
        "different digest idempotency keys."
    )

    print(
        "User A idempotency key : PASS"
    )

    print(
        "User B idempotency key : PASS"
    )

    print(
        "Different users → different keys : PASS"
    )

    # ========================================================
    # DATABASE
    # ========================================================

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification).where(
                Notification.id.in_(
                    notification_ids_a
                    + notification_ids_b
                )
            )
        )

        notifications = (
            result.scalars().all()
        )

        assert len(notifications) == 40

        # ----------------------------------------------------
        # USER A
        # ----------------------------------------------------

        notifications_a = [
            notification
            for notification in notifications
            if notification.user_email
            == TEST_EMAIL_A
        ]

        # ----------------------------------------------------
        # USER B
        # ----------------------------------------------------

        notifications_b = [
            notification
            for notification in notifications
            if notification.user_email
            == TEST_EMAIL_B
        ]

        # ----------------------------------------------------
        # SENT
        # ----------------------------------------------------

        sent_a = [
            notification
            for notification in notifications_a
            if notification.status
            == NotificationStatus.SENT
        ]

        sent_b = [
            notification
            for notification in notifications_b
            if notification.status
            == NotificationStatus.SENT
        ]

        # ----------------------------------------------------
        # PENDING
        # ----------------------------------------------------

        pending_a = [
            notification
            for notification in notifications_a
            if notification.status
            == NotificationStatus.PENDING
        ]

        pending_b = [
            notification
            for notification in notifications_b
            if notification.status
            == NotificationStatus.PENDING
        ]

        assert len(sent_a) == 15
        assert len(pending_a) == 5

        assert len(sent_b) == 15
        assert len(pending_b) == 5

        print(
            "User A → 15 SENT + 5 PENDING : PASS"
        )

        print(
            "User B → 15 SENT + 5 PENDING : PASS"
        )

        # ====================================================
        # SENT FIELD VALIDATION
        # ====================================================

        for notification in sent_a + sent_b:

            assert (
                notification.sent_at
                is not None
            ), (
                f"Notification "
                f"{notification.id} "
                f"has no sent_at."
            )

            assert (
                notification.processing_started_at
                is None
            ), (
                f"Notification "
                f"{notification.id} "
                f"still has processing_started_at."
            )

            assert (
                notification.next_retry_at
                is None
            ), (
                f"Notification "
                f"{notification.id} "
                f"still has next_retry_at."
            )

            assert (
                notification.error_message
                is None
            ), (
                f"Notification "
                f"{notification.id} "
                f"has an error message."
            )

        print(
            "SENT notifications → fields correct : PASS"
        )

        # ====================================================
        # PENDING FIELD VALIDATION
        # ====================================================

        for notification in pending_a + pending_b:

            assert (
                notification.status
                == NotificationStatus.PENDING
            )

            assert (
                notification.next_retry_at
                is not None
            ), (
                f"Notification "
                f"{notification.id} "
                f"was not deferred."
            )

        print(
            "Unselected notifications deferred : PASS"
        )


# ============================================================
# VERIFY IDEMPOTENCY PERSISTENCE
# ============================================================

async def verify_persisted_idempotency():

    print()
    print("=" * 70)
    print("VERIFYING PERSISTED IDEMPOTENCY")
    print("=" * 70)

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification).where(
                Notification.user_email.in_(
                    [
                        TEST_EMAIL_A,
                        TEST_EMAIL_B,
                    ]
                )
            )
        )

        notifications = (
            result.scalars().all()
        )

        keys = [
            notification.idempotency_key
            for notification in notifications
            if notification.idempotency_key
        ]

        # ----------------------------------------------------
        # Dispatcher stores one digest key per email.
        # Therefore:
        #
        # User A → 1 key
        # User B → 1 key
        #
        # Total → 2 keys
        # ----------------------------------------------------

        assert len(keys) == 2, (
            "Expected exactly two persistent "
            "digest idempotency keys."
        )

        assert len(set(keys)) == 2, (
            "Expected two unique digest "
            "idempotency keys."
        )

        print(
            "Exactly two persistent digest keys : PASS"
        )

        print(
            "Both keys unique : PASS"
        )


# ============================================================
# SECOND DISPATCH
# ============================================================

async def verify_second_dispatch():

    print()
    print("=" * 70)
    print("RUNNING SECOND DISPATCH")
    print("=" * 70)

    calls_before = len(fake_email_calls)

    second_result = (
        await
        dispatcher.dispatch_pending_notifications_batch()
    )

    calls_after = len(fake_email_calls)

    print()
    print(
        f"Second dispatcher returned : "
        f"{second_result}"
    )

    # --------------------------------------------------------
    # No new email should be sent.
    # --------------------------------------------------------

    assert (
        calls_after == calls_before
    ), (
        "Second dispatcher run sent "
        "a duplicate email."
    )

    print(
        "Second dispatch → no duplicate email : PASS"
    )

    # ========================================================
    # DATABASE SHOULD NOT REPROCESS SENT NOTIFICATIONS
    # ========================================================

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification).where(
                Notification.user_email.in_(
                    [
                        TEST_EMAIL_A,
                        TEST_EMAIL_B,
                    ]
                )
            )
        )

        notifications = (
            result.scalars().all()
        )

        sent_count = sum(
            1
            for notification in notifications
            if notification.status
            == NotificationStatus.SENT
        )

        pending_count = sum(
            1
            for notification in notifications
            if notification.status
            == NotificationStatus.PENDING
        )

        assert sent_count == 30

        assert pending_count == 10

        print(
            "30 SENT notifications preserved : PASS"
        )

        print(
            "10 deferred PENDING notifications preserved : PASS"
        )


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("🧪 TEST 25 — FINAL DISPATCHER INTEGRATION REGRESSION")
    print("=" * 70)

    fake_email_calls.clear()

    original_email_function = (
        dispatcher.send_notification_email
    )

    try:

        # ====================================================
        # CLEAN OLD TEST DATA
        # ====================================================

        print()
        print("🧹 Cleaning old Test 25 records...")

        await cleanup_test_records()

        print(
            "✅ Old Test 25 records cleaned."
        )

        # ====================================================
        # CREATE TEST DATA
        # ====================================================

        (
            notification_ids_a,
            notification_ids_b,
            internship_ids,
        ) = await create_test_data()

        # ====================================================
        # INSTALL FAKE EMAIL PROVIDER
        # ====================================================

        print()
        print("=" * 70)
        print("INSTALLING FAKE EMAIL PROVIDER")
        print("=" * 70)

        dispatcher.send_notification_email = (
            fake_send_notification_email
        )

        print(
            "✅ Fake email provider installed."
        )

        # ====================================================
        # FIRST DISPATCH
        # ====================================================

        print()
        print("=" * 70)
        print("🚀 RUNNING FIRST DISPATCH")
        print("=" * 70)

        first_result = (
            await
            dispatcher.dispatch_pending_notifications_batch()
        )

        print()
        print(
            f"First dispatcher returned : "
            f"{first_result}"
        )

        # ====================================================
        # VERIFY FIRST DISPATCH
        # ====================================================

        await verify_first_dispatch(
            notification_ids_a,
            notification_ids_b,
        )

        # ====================================================
        # VERIFY IDEMPOTENCY
        # ====================================================

        await verify_persisted_idempotency()

        # ====================================================
        # SECOND DISPATCH
        # ====================================================

        await verify_second_dispatch()

        # ====================================================
        # FINAL SUCCESS
        # ====================================================

        print()
        print("=" * 70)
        print("🎉 TEST 25 PASSED")
        print("=" * 70)

        print()
        print("Verified:")

        print(
            "  ✅ PENDING → PROCESSING → SENT"
        )

        print(
            "  ✅ Multiple users"
        )

        print(
            "  ✅ One grouped digest per user"
        )

        print(
            "  ✅ Recent internships first"
        )

        print(
            "  ✅ Relevance ordering"
        )

        print(
            "  ✅ MAX 15 per digest"
        )

        print(
            "  ✅ Remaining jobs deferred"
        )

        print(
            "  ✅ sent_at populated"
        )

        print(
            "  ✅ Processing lease cleared"
        )

        print(
            "  ✅ Retry state cleared"
        )

        print(
            "  ✅ Idempotency persisted"
        )

        print(
            "  ✅ Second dispatch sends no duplicate"
        )

        print()
        print(
            "🔥 FINAL DISPATCHER REGRESSION PASSED"
        )

    finally:

        # ====================================================
        # RESTORE REAL EMAIL FUNCTION
        # ====================================================

        dispatcher.send_notification_email = (
            original_email_function
        )

        print()
        print(
            "🔄 Real email function restored."
        )

        # ====================================================
        # CLEAN TEST DATA
        # ====================================================

        print()
        print(
            "🧹 Cleaning Test 25 records..."
        )

        await cleanup_test_records()

        print(
            "✅ Test 25 cleanup complete."
        )


# ============================================================
# RUN
# ============================================================

def test_final_dispatcher_regression():
    asyncio.run(main())