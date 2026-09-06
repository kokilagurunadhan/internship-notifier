
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete, func

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)
from app.services import notification_dispatcher


# ============================================================
# TEST CONSTANTS
# ============================================================

USER_A = "test14_user_a@example.com"
USER_B = "test14_user_b@example.com"

COMPANY_A1 = "Test14 Company A1"
COMPANY_A2 = "Test14 Company A2"

COMPANY_B1 = "Test14 Company B1"
COMPANY_B2 = "Test14 Company B2"


# ============================================================
# EMAIL CALL STORAGE
# ============================================================

email_calls = []


# ============================================================
# PRE-EXISTING PENDING NOTIFICATIONS
# ============================================================

isolated_notifications = []


# ============================================================
# FAKE EMAIL PROVIDER
# ============================================================

def fake_send_notification_email(
    user_email,
    internships,
    idempotency_key,
):
    print()
    print("📧 FAKE DIGEST EMAIL")
    print(f"Email: {user_email}")
    print(f"Internships: {len(internships)}")
    print(f"Idempotency key: {idempotency_key}")

    email_calls.append(
        {
            "email": user_email,
            "internships": internships,
            "idempotency_key": idempotency_key,
        }
    )

    return {
        "success": True,
        "idempotency_key": idempotency_key,
    }


# ============================================================
# ISOLATE PRE-EXISTING PENDING NOTIFICATIONS
# ============================================================

async def isolate_existing_pending_notifications():

    global isolated_notifications

    print()
    print("=" * 70)
    print("🔒 ISOLATING PRE-EXISTING PENDING NOTIFICATIONS")
    print("=" * 70)

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification).where(
                Notification.status
                == NotificationStatus.PENDING
            )
        )

        notifications = result.scalars().all()

        isolated_notifications = []

        future_time = (
            datetime.now(timezone.utc)
            + timedelta(days=365)
        )

        for notification in notifications:

            isolated_notifications.append(
                (
                    notification.id,
                    notification.next_retry_at,
                )
            )

            notification.next_retry_at = future_time

        await db.commit()

    print(
        f"🔒 Isolated "
        f"{len(isolated_notifications)} "
        f"pre-existing PENDING notification(s)"
    )


# ============================================================
# RESTORE PRE-EXISTING PENDING NOTIFICATIONS
# ============================================================

async def restore_existing_pending_notifications():

    global isolated_notifications

    if not isolated_notifications:
        return

    print()
    print("=" * 70)
    print("🔄 RESTORING PRE-EXISTING PENDING NOTIFICATIONS")
    print("=" * 70)

    async with AsyncSessionLocal() as db:

        for (
            notification_id,
            original_next_retry_at,
        ) in isolated_notifications:

            result = await db.execute(
                select(Notification).where(
                    Notification.id
                    == notification_id
                )
            )

            notification = (
                result.scalar_one_or_none()
            )

            if notification is not None:

                notification.next_retry_at = (
                    original_next_retry_at
                )

        await db.commit()

    print(
        f"🔄 Restored "
        f"{len(isolated_notifications)} "
        f"pre-existing PENDING notification(s)"
    )

    isolated_notifications.clear()


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    global email_calls

    email_calls = []

    # ========================================================
    # REPLACE EMAIL SENDER
    # ========================================================

    original_email_sender = (
        notification_dispatcher.send_notification_email
    )

    notification_dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    try:

        # ====================================================
        # CLEAN PREVIOUS TEST 14 DATA
        # ====================================================

        async with AsyncSessionLocal() as db:

            print()
            print("=" * 70)
            print("🧹 CLEANING PREVIOUS TEST 14 DATA")
            print("=" * 70)

            # ------------------------------------------------
            # FIND OLD SUBSCRIPTIONS
            # ------------------------------------------------

            result = await db.execute(
                select(Subscription).where(
                    Subscription.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                        ]
                    )
                )
            )

            old_subscriptions = (
                result.scalars().all()
            )

            old_subscription_ids = [
                subscription.id
                for subscription in old_subscriptions
            ]

            # ------------------------------------------------
            # FIND OLD INTERNSHIPS
            # ------------------------------------------------

            result = await db.execute(
                select(Internship).where(
                    Internship.url.like(
                        "%test-14-multi-user%"
                    )
                )
            )

            old_internships = (
                result.scalars().all()
            )

            old_internship_ids = [
                internship.id
                for internship in old_internships
            ]

            # ------------------------------------------------
            # DELETE NOTIFICATIONS BY SUBSCRIPTION
            # ------------------------------------------------

            if old_subscription_ids:

                await db.execute(
                    delete(Notification).where(
                        Notification.subscription_id.in_(
                            old_subscription_ids
                        )
                    )
                )

            # ------------------------------------------------
            # DELETE NOTIFICATIONS BY INTERNSHIP
            # ------------------------------------------------

            if old_internship_ids:

                await db.execute(
                    delete(Notification).where(
                        Notification.internship_id.in_(
                            old_internship_ids
                        )
                    )
                )

            # ------------------------------------------------
            # DELETE INTERNSHIPS
            # ------------------------------------------------

            if old_internship_ids:

                await db.execute(
                    delete(Internship).where(
                        Internship.id.in_(
                            old_internship_ids
                        )
                    )
                )

            # ------------------------------------------------
            # DELETE SUBSCRIPTIONS
            # ------------------------------------------------

            if old_subscription_ids:

                await db.execute(
                    delete(Subscription).where(
                        Subscription.id.in_(
                            old_subscription_ids
                        )
                    )
                )

            await db.commit()

            print(
                "✅ Previous Test 14 data cleaned"
            )

        # ====================================================
        # ISOLATE PRE-EXISTING PENDING NOTIFICATIONS
        #
        # IMPORTANT:
        # This happens BEFORE Test 14 notifications
        # are created.
        # ====================================================

        await isolate_existing_pending_notifications()

        # ====================================================
        # CREATE TEST DATA
        # ====================================================

        async with AsyncSessionLocal() as db:

            # =================================================
            # USER A SUBSCRIPTIONS
            # =================================================

            print()
            print("=" * 70)
            print("👤 TEST 14 — CREATE USER A SUBSCRIPTIONS")
            print("=" * 70)

            subscription_a1 = Subscription(
                user_email=USER_A,
                company=COMPANY_A1,
                domain="software",
                is_active=True,
            )

            subscription_a2 = Subscription(
                user_email=USER_A,
                company=COMPANY_A2,
                domain="software",
                is_active=True,
            )

            db.add_all(
                [
                    subscription_a1,
                    subscription_a2,
                ]
            )

            await db.commit()

            await db.refresh(subscription_a1)
            await db.refresh(subscription_a2)

            print(
                f"🆔 User A Subscription 1: "
                f"{subscription_a1.id}"
            )

            print(
                f"🆔 User A Subscription 2: "
                f"{subscription_a2.id}"
            )

            # =================================================
            # USER B SUBSCRIPTIONS
            # =================================================

            print()
            print("=" * 70)
            print("👤 TEST 14 — CREATE USER B SUBSCRIPTIONS")
            print("=" * 70)

            subscription_b1 = Subscription(
                user_email=USER_B,
                company=COMPANY_B1,
                domain="software",
                is_active=True,
            )

            subscription_b2 = Subscription(
                user_email=USER_B,
                company=COMPANY_B2,
                domain="software",
                is_active=True,
            )

            db.add_all(
                [
                    subscription_b1,
                    subscription_b2,
                ]
            )

            await db.commit()

            await db.refresh(subscription_b1)
            await db.refresh(subscription_b2)

            print(
                f"🆔 User B Subscription 1: "
                f"{subscription_b1.id}"
            )

            print(
                f"🆔 User B Subscription 2: "
                f"{subscription_b2.id}"
            )

            # =================================================
            # CREATE FOUR INTERNSHIPS
            # =================================================

            print()
            print("=" * 70)
            print("🧪 TEST 14 — CREATE INTERNSHIPS")
            print("=" * 70)

            internship_a1 = Internship(
                company=COMPANY_A1,
                title="Software Engineering Intern A1",
                location="India",
                url=(
                    "https://example.com/jobs/"
                    "test-14-multi-user-a1"
                ),
                description=(
                    "Software engineering internship."
                ),
                source="SerpAPI",
                via="Test",
                relevance_score=80,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            internship_a2 = Internship(
                company=COMPANY_A2,
                title="Backend Engineering Intern A2",
                location="India",
                url=(
                    "https://example.com/jobs/"
                    "test-14-multi-user-a2"
                ),
                description=(
                    "Backend engineering internship."
                ),
                source="SerpAPI",
                via="Test",
                relevance_score=75,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            internship_b1 = Internship(
                company=COMPANY_B1,
                title="Python Engineering Intern B1",
                location="India",
                url=(
                    "https://example.com/jobs/"
                    "test-14-multi-user-b1"
                ),
                description=(
                    "Python engineering internship."
                ),
                source="SerpAPI",
                via="Test",
                relevance_score=85,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            internship_b2 = Internship(
                company=COMPANY_B2,
                title="Data Engineering Intern B2",
                location="India",
                url=(
                    "https://example.com/jobs/"
                    "test-14-multi-user-b2"
                ),
                description=(
                    "Data engineering internship."
                ),
                source="SerpAPI",
                via="Test",
                relevance_score=70,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            db.add_all(
                [
                    internship_a1,
                    internship_a2,
                    internship_b1,
                    internship_b2,
                ]
            )

            await db.commit()

            await db.refresh(internship_a1)
            await db.refresh(internship_a2)
            await db.refresh(internship_b1)
            await db.refresh(internship_b2)

            print(
                f"🆔 User A Internship 1: "
                f"{internship_a1.id}"
            )

            print(
                f"🆔 User A Internship 2: "
                f"{internship_a2.id}"
            )

            print(
                f"🆔 User B Internship 1: "
                f"{internship_b1.id}"
            )

            print(
                f"🆔 User B Internship 2: "
                f"{internship_b2.id}"
            )

            # =================================================
            # SAVE IDS
            # =================================================

            internship_a1_id = internship_a1.id
            internship_a2_id = internship_a2.id

            internship_b1_id = internship_b1.id
            internship_b2_id = internship_b2.id

            # =================================================
            # CREATE FOUR PENDING NOTIFICATIONS
            # =================================================

            print()
            print("=" * 70)
            print("🔔 TEST 14 — CREATE PENDING NOTIFICATIONS")
            print("=" * 70)

            notification_a1 = Notification(
                subscription_id=subscription_a1.id,
                user_email=USER_A,
                internship_id=internship_a1_id,
                status=NotificationStatus.PENDING,
                relevance_score=80,
                retry_count=0,
                error_message=None,
                sent_at=None,
            )

            notification_a2 = Notification(
                subscription_id=subscription_a2.id,
                user_email=USER_A,
                internship_id=internship_a2_id,
                status=NotificationStatus.PENDING,
                relevance_score=75,
                retry_count=0,
                error_message=None,
                sent_at=None,
            )

            notification_b1 = Notification(
                subscription_id=subscription_b1.id,
                user_email=USER_B,
                internship_id=internship_b1_id,
                status=NotificationStatus.PENDING,
                relevance_score=85,
                retry_count=0,
                error_message=None,
                sent_at=None,
            )

            notification_b2 = Notification(
                subscription_id=subscription_b2.id,
                user_email=USER_B,
                internship_id=internship_b2_id,
                status=NotificationStatus.PENDING,
                relevance_score=70,
                retry_count=0,
                error_message=None,
                sent_at=None,
            )

            db.add_all(
                [
                    notification_a1,
                    notification_a2,
                    notification_b1,
                    notification_b2,
                ]
            )

            await db.commit()

            await db.refresh(notification_a1)
            await db.refresh(notification_a2)
            await db.refresh(notification_b1)
            await db.refresh(notification_b2)

            notification_a1_id = notification_a1.id
            notification_a2_id = notification_a2.id
            notification_b1_id = notification_b1.id
            notification_b2_id = notification_b2.id

            print(
                f"🆔 User A Notification 1: "
                f"{notification_a1_id}"
            )

            print(
                f"🆔 User A Notification 2: "
                f"{notification_a2_id}"
            )

            print(
                f"🆔 User B Notification 1: "
                f"{notification_b1_id}"
            )

            print(
                f"🆔 User B Notification 2: "
                f"{notification_b2_id}"
            )

            # =================================================
            # VERIFY FOUR PENDING NOTIFICATIONS
            # =================================================

            result = await db.execute(
                select(func.count(Notification.id))
                .where(
                    Notification.status
                    == NotificationStatus.PENDING
                )
                .where(
                    Notification.user_email.in_(
                        [
                            USER_A,
                            USER_B,
                        ]
                    )
                )
            )

            pending_notifications = (
                result.scalar_one()
            )

            assert pending_notifications == 4

            print(
                "✅ Exactly 4 PENDING notifications created"
            )

        # ====================================================
        # RUN DISPATCHER
        # ====================================================

        print()
        print("=" * 70)
        print("🧪 TEST 14 — PROCESS PENDING NOTIFICATIONS")
        print("=" * 70)

        result = (
            await notification_dispatcher
            .dispatch_pending_notifications_batch()
        )

        print(
            f"📊 Dispatcher returned: {result}"
        )

        # ====================================================
        # VERIFY TWO DIGESTS
        # ====================================================

        assert result == 2

        assert len(email_calls) == 2

        print(
            "✅ Exactly 2 digest emails were sent"
        )

        # ====================================================
        # FIND USER A DIGEST
        # ====================================================

        user_a_calls = [
            call
            for call in email_calls
            if call["email"] == USER_A
        ]

        assert len(user_a_calls) == 1

        user_a_digest = user_a_calls[0]

        assert len(
            user_a_digest["internships"]
        ) == 2

        print(
            "✅ User A received exactly 2 internships"
        )

        # ====================================================
        # FIND USER B DIGEST
        # ====================================================

        user_b_calls = [
            call
            for call in email_calls
            if call["email"] == USER_B
        ]

        assert len(user_b_calls) == 1

        user_b_digest = user_b_calls[0]

        assert len(
            user_b_digest["internships"]
        ) == 2

        print(
            "✅ User B received exactly 2 internships"
        )

        # ====================================================
        # EXTRACT IDS FROM DIGEST DICTIONARIES
        #
        # IMPORTANT:
        # notification_dispatcher passes internship
        # dictionaries to the email sender.
        #
        # Therefore:
        #
        # internship["id"]
        #
        # NOT:
        #
        # internship.id
        # ====================================================

        user_a_internship_ids = {
            internship["id"]
            for internship
            in user_a_digest["internships"]
        }

        user_b_internship_ids = {
            internship["id"]
            for internship
            in user_b_digest["internships"]
        }

        # ====================================================
        # VERIFY USER A RECEIVED ONLY USER A JOBS
        # ====================================================

        assert internship_a1_id in (
            user_a_internship_ids
        )

        assert internship_a2_id in (
            user_a_internship_ids
        )

        assert internship_b1_id not in (
            user_a_internship_ids
        )

        assert internship_b2_id not in (
            user_a_internship_ids
        )

        print(
            "✅ User A received only User A internships"
        )

        # ====================================================
        # VERIFY USER B RECEIVED ONLY USER B JOBS
        # ====================================================

        assert internship_b1_id in (
            user_b_internship_ids
        )

        assert internship_b2_id in (
            user_b_internship_ids
        )

        assert internship_a1_id not in (
            user_b_internship_ids
        )

        assert internship_a2_id not in (
            user_b_internship_ids
        )

        print(
            "✅ User B received only User B internships"
        )

        # ====================================================
        # VERIFY IDEMPOTENCY KEYS
        # ====================================================

        user_a_key = (
            user_a_digest["idempotency_key"]
        )

        user_b_key = (
            user_b_digest["idempotency_key"]
        )

        assert user_a_key.startswith(
            "internship-digest:"
        )

        assert user_b_key.startswith(
            "internship-digest:"
        )

        assert user_a_key != user_b_key

        print(
            "✅ User A and User B have different "
            "idempotency keys"
        )

        # ====================================================
        # VERIFY DATABASE
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.id.in_(
                        [
                            notification_a1_id,
                            notification_a2_id,
                            notification_b1_id,
                            notification_b2_id,
                        ]
                    )
                )
            )

            notifications = (
                result.scalars().all()
            )

            assert len(notifications) == 4

            # ------------------------------------------------
            # ALL FOUR MUST BE SENT
            # ------------------------------------------------

            for notification in notifications:

                assert (
                    notification.status
                    == NotificationStatus.SENT
                )

                assert (
                    notification.sent_at
                    is not None
                )

            print(
                "✅ All 4 Test 14 notifications are SENT"
            )

            # ------------------------------------------------
            # EXACTLY TWO PERSISTENT IDEMPOTENCY KEYS
            # ------------------------------------------------

            persistent_keys = [
                notification.idempotency_key
                for notification in notifications
                if notification.idempotency_key
                is not None
            ]

            assert len(persistent_keys) == 2

            assert (
                len(set(persistent_keys)) == 2
            )

            print(
                "✅ Exactly 2 persistent idempotency keys"
            )

        # ====================================================
        # FINAL SUCCESS
        # ====================================================

        print()
        print("=" * 70)
        print("🎉 TEST 14 PASSED")
        print("MULTI-USER GROUPED DIGEST VERIFIED")
        print("=" * 70)

    finally:

        # ====================================================
        # RESTORE EMAIL FUNCTION
        # ====================================================

        notification_dispatcher.send_notification_email = (
            original_email_sender
        )

        # ====================================================
        # RESTORE PRE-EXISTING PENDING NOTIFICATIONS
        # ====================================================

        await restore_existing_pending_notifications()


# ============================================================
# PYTEST ENTRY POINT
# ============================================================

def test_multi_user_grouped_digest():

    asyncio.run(main())
