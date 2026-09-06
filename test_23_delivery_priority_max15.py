import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models import Subscription, Internship, Notification
from app.models.notification import NotificationStatus

from app.services.notification_dispatcher import (
    dispatch_pending_notifications_batch,
)


@pytest.mark.asyncio
async def test_delivery_priority_and_max_15():
    """
    TEST 23

    Verify the LOCKED delivery pipeline:

        PENDING
            ↓
        ATOMIC CLAIM
            ↓
        PROCESSING
            ↓
        GROUP BY EMAIL
            ↓
        FRESH / RECENT FIRST
            ↓
        RELEVANCE DESC
            ↓
        CREATED_AT DESC
            ↓
        MAX 15
            ↓
        IDEMPOTENCY
            ↓
        SEND DIGEST
            ↓
        SENT

    Also verify:

        Remaining 5
            ↓
        PENDING
            ↓
        next_retry_at = +12 hours

    IMPORTANT TEST ISOLATION:

    Existing PENDING notifications are temporarily moved
    to PROCESSING so they cannot interfere with Test23.

    They are restored to their original state afterward.

    IMPORTANT SQLALCHEMY SESSION HANDLING:

    The dispatcher uses its own AsyncSession.

    Therefore, after dispatcher execution, this test calls:

        db.expire_all()

    so cached ORM objects are refreshed from PostgreSQL.
    """

    user_email = "test23_priority@example.com"
    company = "Test23 Delivery Company"

    created_subscription_id = None
    created_internship_ids = []
    created_notification_ids = []

    isolated_notifications = []

    async with AsyncSessionLocal() as db:

        print("\n" + "=" * 70)
        print("🧪 TEST 23 — DELIVERY PRIORITY + MAX 15")
        print("=" * 70)

        try:

            # =========================================================
            # 1. CLEAN UP LEFTOVER TEST23 SUBSCRIPTION
            # =========================================================

            existing_result = await db.execute(
                select(Subscription).where(
                    Subscription.user_email == user_email
                )
            )

            existing_subscriptions = (
                existing_result.scalars().all()
            )

            for subscription in existing_subscriptions:
                await db.delete(subscription)

            await db.commit()

            print("\n🧹 Previous Test23 data cleaned up.")

            # =========================================================
            # 2. ISOLATE PRE-EXISTING PENDING NOTIFICATIONS
            # =========================================================

            pending_result = await db.execute(
                select(Notification).where(
                    Notification.status
                    == NotificationStatus.PENDING
                )
            )

            existing_pending_notifications = (
                pending_result.scalars().all()
            )

            print(
                f"\n🔒 Found "
                f"{len(existing_pending_notifications)} "
                f"pre-existing PENDING notification(s)"
            )

            for notification in (
                existing_pending_notifications
            ):

                isolated_notifications.append(
                    {
                        "id": notification.id,
                        "status": notification.status,
                        "next_retry_at": (
                            notification.next_retry_at
                        ),
                        "processing_started_at": (
                            notification.processing_started_at
                        ),
                    }
                )

                notification.status = (
                    NotificationStatus.PROCESSING
                )

                notification.processing_started_at = (
                    datetime.now(timezone.utc)
                )

            if existing_pending_notifications:
                await db.commit()

            print(
                f"🔒 Temporarily isolated "
                f"{len(existing_pending_notifications)} "
                f"pre-existing PENDING notification(s)"
            )

            # =========================================================
            # 3. CREATE TEST SUBSCRIPTION
            # =========================================================

            subscription = Subscription(
                user_email=user_email,
                company=company,
                domain="software",
                is_active=True,
            )

            db.add(subscription)

            await db.commit()
            await db.refresh(subscription)

            created_subscription_id = subscription.id

            print(
                f"\n👤 Test subscription created: "
                f"ID {subscription.id}"
            )

            # =========================================================
            # 4. CREATE 20 INTERNSHIPS
            # =========================================================

            now = datetime.now(timezone.utc)

            internships = []

            for i in range(1, 21):

                # -----------------------------------------------------
                # Jobs 1-5
                #
                # Very recent
                # Highest relevance
                # -----------------------------------------------------

                if i <= 5:

                    created_at = (
                        now
                        - timedelta(hours=i)
                    )

                    relevance = (
                        100.0 - i
                    )

                # -----------------------------------------------------
                # Jobs 6-10
                #
                # Older than 12 hours
                # Medium-high relevance
                # -----------------------------------------------------

                elif i <= 10:

                    created_at = (
                        now
                        - timedelta(
                            days=1,
                            hours=i
                        )
                    )

                    relevance = (
                        90.0 - i
                    )

                # -----------------------------------------------------
                # Jobs 11-15
                #
                # Older
                # Lower relevance
                # -----------------------------------------------------

                elif i <= 15:

                    created_at = (
                        now
                        - timedelta(
                            days=2,
                            hours=i
                        )
                    )

                    relevance = (
                        80.0 - i
                    )

                # -----------------------------------------------------
                # Jobs 16-20
                #
                # Oldest
                # Lowest relevance
                # -----------------------------------------------------

                else:

                    created_at = (
                        now
                        - timedelta(
                            days=5,
                            hours=i
                        )
                    )

                    relevance = (
                        70.0 - i
                    )

                internship = Internship(
                    company=company,
                    title=(
                        "Test23 Software Engineering "
                        f"Internship {i}"
                    ),
                    location="Remote",
                    url=(
                        "https://example.com/"
                        f"test23/internship-{i}"
                    ),
                    description=(
                        "Test23 internship used to verify "
                        "delivery priority and MAX 15."
                    ),
                    source="Test23",
                    via="Test23",
                    relevance_score=relevance,
                    passed_filter=True,
                    status="NEW",
                    email_sent=False,
                    created_at=created_at,
                    last_seen_at=created_at,
                )

                internships.append(internship)

            db.add_all(internships)

            await db.commit()

            for internship in internships:

                await db.refresh(internship)

                created_internship_ids.append(
                    internship.id
                )

            print(
                f"📦 Created "
                f"{len(internships)} internships"
            )

            # =========================================================
            # 5. CREATE 20 PENDING NOTIFICATIONS
            # =========================================================

            notifications = []

            for internship in internships:

                notification = Notification(
                    subscription_id=subscription.id,
                    user_email=user_email,
                    internship_id=internship.id,
                    status=NotificationStatus.PENDING,
                    relevance_score=(
                        internship.relevance_score
                    ),
                    created_at=(
                        internship.created_at
                    ),
                    updated_at=(
                        internship.created_at
                    ),
                    sent_at=None,
                    processing_started_at=None,
                    idempotency_key=None,
                    retry_count=0,
                    next_retry_at=None,
                    error_message=None,
                )

                notifications.append(
                    notification
                )

            db.add_all(notifications)

            await db.commit()

            for notification in notifications:

                await db.refresh(notification)

                created_notification_ids.append(
                    notification.id
                )

            print(
                f"🔔 Created "
                f"{len(notifications)} "
                f"PENDING notifications"
            )

            # =========================================================
            # 6. FAKE EMAIL SENDER
            # =========================================================

            sent_digests = []

            def fake_send_notification_email(
                recipient,
                internships_for_email,
                idempotency_key,
            ):

                sent_digests.append(
                    {
                        "recipient": recipient,
                        "internships": list(
                            internships_for_email
                        ),
                        "idempotency_key": (
                            idempotency_key
                        ),
                    }
                )

                print(
                    "\n📨 FAKE EMAIL SENT"
                )

                print(
                    f"   Recipient: "
                    f"{recipient}"
                )

                print(
                    f"   Jobs in digest: "
                    f"{len(internships_for_email)}"
                )

                print(
                    f"   Idempotency key: "
                    f"{idempotency_key}"
                )

                for internship in (
                    internships_for_email
                ):

                    print(
                        f"      → "
                        f"{internship['title']}"
                        f" | score="
                        f"{internship['relevance_score']}"
                        f" | is_new="
                        f"{internship['is_new']}"
                    )

                return True

            # =========================================================
            # 7. FIRST DISPATCHER RUN
            # =========================================================

            print(
                "\n🚀 Running first dispatcher..."
            )

            with patch(
                "app.services.notification_dispatcher"
                ".send_notification_email",
                side_effect=(
                    fake_send_notification_email
                ),
            ):

                first_result = (
                    await
                    dispatch_pending_notifications_batch()
                )

            print(
                "\n📊 First dispatcher result:"
            )

            print(first_result)

            # =========================================================
            # 8. VERIFY EXACTLY ONE TEST23 DIGEST
            # =========================================================

            test23_digests = [
                digest
                for digest in sent_digests
                if digest["recipient"]
                == user_email
            ]

            assert len(
                test23_digests
            ) == 1

            digest = test23_digests[0]

            assert (
                digest["recipient"]
                == user_email
            )

            print(
                "\n✅ CASE 1 PASSED: "
                "Exactly one Test23 digest was sent"
            )

            # =========================================================
            # 9. VERIFY MAX 15
            # =========================================================

            digest_internships = (
                digest["internships"]
            )

            assert len(
                digest_internships
            ) == 15

            assert len(
                digest_internships
            ) <= 15

            print(
                "✅ CASE 2 PASSED: "
                "MAX 15 enforced"
            )

            # =========================================================
            # 10. VERIFY EXPECTED TOP 15
            # =========================================================

            expected_titles = [
                (
                    "Test23 Software Engineering "
                    f"Internship {i}"
                )
                for i in range(1, 16)
            ]

            actual_titles = [
                internship["title"]
                for internship in digest_internships
            ]

            assert (
                actual_titles
                == expected_titles
            )

            print(
                "✅ CASE 3 PASSED: "
                "Correct top 15 internships selected"
            )

            # =========================================================
            # 11. VERIFY FRESH / RECENT FIRST
            # =========================================================

            is_new_values = [
                internship["is_new"]
                for internship
                in digest_internships
            ]

            assert all(
                is_new_values[i] is True
                for i in range(5)
            )

            assert all(
                is_new_values[i] is False
                for i in range(5, 15)
            )

            print(
                "✅ CASE 4 PASSED: "
                "Fresh/recent internships appear first"
            )

            # =========================================================
            # 12. VERIFY RELEVANCE DESCENDING
            # =========================================================

            scores = [
                float(
                    internship["relevance_score"]
                )
                for internship
                in digest_internships
            ]

            assert scores == sorted(
                scores,
                reverse=True,
            )

            print(
                "✅ CASE 5 PASSED: "
                "Relevance scores descend correctly"
            )

            # =========================================================
            # 13. IMPORTANT:
            #     REFRESH SQLALCHEMY SESSION STATE
            # =========================================================
            #
            # The dispatcher uses its own AsyncSession.
            #
            # The current Test23 AsyncSession may still contain
            # cached Notification ORM objects with their old
            # PENDING state.
            #
            # expire_all() forces SQLAlchemy to reload them from
            # PostgreSQL on the next access.
            # =========================================================

            db.expire_all()

            print(
                "\n🔄 SQLAlchemy session cache expired."
            )

            # =========================================================
            # 14. RELOAD TEST23 NOTIFICATIONS FROM DATABASE
            # =========================================================

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id.in_(
                        created_notification_ids
                    )
                )
                .order_by(Notification.id)
            )

            stored_notifications = (
                result.scalars().all()
            )

            assert len(
                stored_notifications
            ) == 20

            # =========================================================
            # 15. VERIFY 15 SENT
            # =========================================================

            sent_notifications = [
                notification
                for notification
                in stored_notifications
                if notification.status
                == NotificationStatus.SENT
            ]

            assert len(
                sent_notifications
            ) == 15

            print(
                "✅ CASE 6 PASSED: "
                "Exactly 15 notifications became SENT"
            )

            # =========================================================
            # 16. VERIFY 5 REMAIN PENDING
            # =========================================================

            pending_notifications = [
                notification
                for notification
                in stored_notifications
                if notification.status
                == NotificationStatus.PENDING
            ]

            assert len(
                pending_notifications
            ) == 5

            print(
                "✅ CASE 7 PASSED: "
                "5 unselected notifications remain PENDING"
            )

            # =========================================================
            # 17. VERIFY 5 DEFERRED +12 HOURS
            # =========================================================

            for notification in (
                pending_notifications
            ):

                assert (
                    notification.next_retry_at
                    is not None
                )

                next_retry = (
                    notification.next_retry_at
                )

                if next_retry.tzinfo is None:

                    next_retry = (
                        next_retry.replace(
                            tzinfo=timezone.utc
                        )
                    )

                remaining = (
                    next_retry
                    - datetime.now(
                        timezone.utc
                    )
                )

                assert (
                    timedelta(
                        hours=11,
                        minutes=55
                    )
                    <= remaining
                    <= timedelta(
                        hours=12,
                        minutes=1
                    )
                )

            print(
                "✅ CASE 8 PASSED: "
                "Unselected notifications deferred "
                "for approximately 12 hours"
            )

            # =========================================================
            # 18. VERIFY SENT_AT
            # =========================================================

            for notification in (
                sent_notifications
            ):

                assert (
                    notification.sent_at
                    is not None
                )

            print(
                "✅ CASE 9 PASSED: "
                "All SENT notifications have sent_at"
            )

            # =========================================================
            # 19. VERIFY IDEMPOTENCY
            # =========================================================

            idempotency_keys = [
                notification.idempotency_key
                for notification
                in sent_notifications
                if notification.idempotency_key
                is not None
            ]

            assert len(
                idempotency_keys
            ) == 1

            assert (
                idempotency_keys[0]
                == digest["idempotency_key"]
            )

            print(
                "✅ CASE 10 PASSED: "
                "Digest uses one persistent "
                "idempotency key"
            )

            # =========================================================
            # 20. SECOND DISPATCHER RUN
            # =========================================================

            print(
                "\n🔁 Running dispatcher immediately "
                "for the second time..."
            )

            before_second_run = len(
                sent_digests
            )

            with patch(
                "app.services.notification_dispatcher"
                ".send_notification_email",
                side_effect=(
                    fake_send_notification_email
                ),
            ):

                second_result = (
                    await
                    dispatch_pending_notifications_batch()
                )

            after_second_run = len(
                sent_digests
            )

            # =========================================================
            # 21. VERIFY NO IMMEDIATE TEST23 DUPLICATE
            # =========================================================

            second_test23_digests = [
                digest
                for digest in sent_digests[
                    before_second_run:
                ]
                if digest["recipient"]
                == user_email
            ]

            assert (
                len(second_test23_digests)
                == 0
            )

            assert (
                after_second_run
                == before_second_run
            )

            assert (
                second_result
                == 0
            )

            print(
                "✅ CASE 11 PASSED: "
                "Second immediate dispatcher run "
                "sent no duplicate Test23 digest"
            )

            # =========================================================
            # 22. FINAL VERIFICATION
            # =========================================================

            print("\n" + "=" * 70)
            print("🎯 DELIVERY PIPELINE VERIFIED")
            print("=" * 70)

            print(
                """
20 PENDING
        ↓
ATOMIC CLAIM
        ↓
PROCESSING
        ↓
GROUP BY EMAIL
        ↓
FRESH / RECENT FIRST
        ↓
RELEVANCE DESC
        ↓
CREATED_AT DESC
        ↓
MAX 15
        ↓
15 SENT
        ↓
5 DEFERRED
        ↓
+12 HOURS
        ↓
NO IMMEDIATE DUPLICATE
"""
            )

            print("=" * 70)
            print("🎉 TEST 23 PASSED")
            print("=" * 70)

        finally:

            # =========================================================
            # 23. CLEANUP TEST23 NOTIFICATIONS
            # =========================================================

            try:

                await db.rollback()

                if created_notification_ids:

                    await db.execute(
                        delete(Notification).where(
                            Notification.id.in_(
                                created_notification_ids
                            )
                        )
                    )

                if created_internship_ids:

                    await db.execute(
                        delete(Internship).where(
                            Internship.id.in_(
                                created_internship_ids
                            )
                        )
                    )

                await db.commit()

                print(
                    "\n🧹 Test23 notifications "
                    "and internships cleaned up."
                )

            except Exception as cleanup_error:

                await db.rollback()

                print(
                    "\n⚠️ Test23 cleanup warning:"
                )

                print(
                    f"   {cleanup_error}"
                )

            # =========================================================
            # 24. CLEANUP TEST23 SUBSCRIPTION
            # =========================================================

            try:

                if created_subscription_id:

                    subscription_to_delete = (
                        await db.get(
                            Subscription,
                            created_subscription_id,
                        )
                    )

                    if subscription_to_delete:

                        await db.delete(
                            subscription_to_delete
                        )

                    await db.commit()

                print(
                    "🧹 Test23 subscription cleaned up."
                )

            except Exception as subscription_cleanup_error:

                await db.rollback()

                print(
                    "\n⚠️ Subscription cleanup warning:"
                )

                print(
                    f"   {subscription_cleanup_error}"
                )

            # =========================================================
            # 25. RESTORE PRE-EXISTING NOTIFICATIONS
            # =========================================================

            try:

                if isolated_notifications:

                    restored_count = 0

                    for saved in (
                        isolated_notifications
                    ):

                        notification = await db.get(
                            Notification,
                            saved["id"],
                        )

                        if notification:

                            notification.status = (
                                saved["status"]
                            )

                            notification.next_retry_at = (
                                saved["next_retry_at"]
                            )

                            notification.processing_started_at = (
                                saved[
                                    "processing_started_at"
                                ]
                            )

                            restored_count += 1

                    await db.commit()

                    print(
                        f"🔓 Restored "
                        f"{restored_count} "
                        f"pre-existing notification(s)"
                    )

            except Exception as restore_error:

                await db.rollback()

                print(
                    "\n⚠️ Notification restore warning:"
                )

                print(
                    f"   {restore_error}"
                )