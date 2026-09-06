import asyncio

from sqlalchemy import select, delete

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

TEST_EMAIL = "dispatcher_test@example.com"

TEST_COMPANY = "microsoft"

TEST_URLS = [
    "https://controlled.test/microsoft-intern-001",
    "https://controlled.test/microsoft-intern-002",
    "https://controlled.test/microsoft-intern-003",
]


# ============================================================
# FAKE EMAIL PROVIDER
# ============================================================

fake_email_calls = []


def fake_send_notification_email(
    recipient_email,
    internships,
    idempotency_key,
):

    fake_email_calls.append(
        {
            "recipient_email": recipient_email,
            "internships": internships,
            "idempotency_key": idempotency_key,
        }
    )

    print()
    print("📧 FAKE EMAIL PROVIDER CALLED")
    print(f"   Recipient    : {recipient_email}")
    print(f"   Jobs         : {len(internships)}")
    print(f"   Idempotency  : {idempotency_key}")

    return {
        "id": "fake-resend-id",
        "status": "sent",
    }


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
                Subscription.user_email == TEST_EMAIL
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
                Internship.url.in_(TEST_URLS)
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
# MAIN TEST
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("🚀 CONTROLLED NOTIFICATION DISPATCHER TEST")
    print("=" * 70)

    # Reset fake calls every time
    fake_email_calls.clear()

    # ========================================================
    # CLEAN OLD DATA
    # ========================================================

    print()
    print("🧹 Cleaning previous test records...")

    await cleanup_test_records()

    print("✅ Cleanup complete.")

    # ========================================================
    # CREATE TEST DATA
    # ========================================================

    async with AsyncSessionLocal() as db:

        print()
        print("=" * 70)
        print("CREATING TEST DATA")
        print("=" * 70)

        # ----------------------------------------------------
        # SUBSCRIPTION
        # ----------------------------------------------------

        subscription = Subscription(
            user_email=TEST_EMAIL,
            company=TEST_COMPANY,
            domain="software",
            is_active=True,
        )

        db.add(subscription)

        await db.flush()

        print(
            f"Subscription ID : {subscription.id}"
        )

        # ----------------------------------------------------
        # INTERNSHIPS
        # ----------------------------------------------------

        internships = []

        for index, url in enumerate(
            TEST_URLS,
            start=1,
        ):

            internship = Internship(
                company=TEST_COMPANY,
                title=(
                    f"Controlled Software "
                    f"Engineering Intern {index}"
                ),
                location="Remote",
                url=url,
                description=(
                    "Software engineering internship "
                    "for controlled dispatcher testing."
                ),
                source="controlled_test",
                via="controlled_test",
                relevance_score=80.0 + index,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            internships.append(internship)

            db.add(internship)

        await db.flush()

        print(
            f"Internships created : "
            f"{len(internships)}"
        )

        # ----------------------------------------------------
        # NOTIFICATIONS
        # ----------------------------------------------------

        notifications = []

        for internship in internships:

            notification = Notification(
                subscription_id=subscription.id,
                user_email=TEST_EMAIL,
                internship_id=internship.id,
                relevance_score=(
                    internship.relevance_score
                ),
                status=NotificationStatus.PENDING,
            )

            notifications.append(notification)

            db.add(notification)

        await db.commit()

        notification_ids = [
            notification.id
            for notification in notifications
        ]

        print(
            f"Notifications created : "
            f"{len(notification_ids)}"
        )

    # ========================================================
    # REPLACE EMAIL FUNCTION
    # ========================================================

    print()
    print("=" * 70)
    print("INSTALLING CONTROLLED EMAIL PROVIDER")
    print("=" * 70)

    original_email_function = (
        dispatcher.send_notification_email
    )

    dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    test_passed = False

    try:

        # ====================================================
        # FIRST DISPATCH
        # ====================================================

        print()
        print("=" * 70)
        print("RUNNING FIRST DISPATCH")
        print("=" * 70)

        result = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print()
        print(
            f"Dispatcher returned : {result}"
        )

        # ====================================================
        # EMAIL VERIFICATION
        # ====================================================

        print()
        print("=" * 70)
        print("EMAIL VERIFICATION")
        print("=" * 70)

        # ----------------------------------------------------
        # ONLY CHECK OUR CONTROLLED TEST USER
        # ----------------------------------------------------

        test_email_calls = [
            call
            for call in fake_email_calls
            if call["recipient_email"] == TEST_EMAIL
        ]

        assert len(test_email_calls) == 1, (
            "Expected exactly one email call for "
            "the controlled test user."
        )

        email_call = test_email_calls[0]

        assert (
            email_call["recipient_email"]
            == TEST_EMAIL
        ), (
            "Incorrect email recipient."
        )

        assert len(
            email_call["internships"]
        ) == 3, (
            "Expected exactly 3 internships "
            "in the digest."
        )

        assert email_call[
            "idempotency_key"
        ], (
            "Digest idempotency key was not generated."
        )

        # ----------------------------------------------------
        # VERIFY IDEMPOTENCY KEY FORMAT
        # ----------------------------------------------------

        assert email_call[
            "idempotency_key"
        ].startswith(
            "internship-digest:"
        ), (
            "Invalid digest idempotency key format."
        )

        digest_idempotency_key = (
            email_call["idempotency_key"]
        )

        print("Controlled email call : PASS")
        print("Recipient              : PASS")
        print("3 jobs in digest       : PASS")
        print("Idempotency key        : PASS")
        print("Idempotency format     : PASS")

        # ====================================================
        # DATABASE VERIFICATION
        # ====================================================

        print()
        print("=" * 70)
        print("DATABASE VERIFICATION")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id.in_(
                        notification_ids
                    )
                )
                .order_by(
                    Notification.id.asc()
                )
            )

            saved_notifications = (
                result.scalars().all()
            )

            assert len(
                saved_notifications
            ) == 3, (
                "Expected exactly 3 notifications."
            )

            for notification in (
                saved_notifications
            ):

                print()
                print(
                    f"Notification ID : "
                    f"{notification.id}"
                )

                print(
                    f"Status          : "
                    f"{notification.status}"
                )

                print(
                    f"Sent at         : "
                    f"{notification.sent_at}"
                )

                print(
                    f"Processing start: "
                    f"{notification.processing_started_at}"
                )

                print(
                    f"Idempotency     : "
                    f"{notification.idempotency_key}"
                )

                # ------------------------------------------------
                # STATUS
                # ------------------------------------------------

                assert (
                    notification.status
                    == NotificationStatus.SENT
                ), (
                    f"Notification "
                    f"{notification.id} "
                    f"was not marked SENT."
                )

                # ------------------------------------------------
                # SENT TIME
                # ------------------------------------------------

                assert (
                    notification.sent_at
                    is not None
                ), (
                    f"Notification "
                    f"{notification.id} "
                    f"has no sent_at."
                )

                # ------------------------------------------------
                # PROCESSING LEASE
                # ------------------------------------------------

                assert (
                    notification.processing_started_at
                    is None
                ), (
                    f"Notification "
                    f"{notification.id} "
                    f"still has processing_started_at."
                )

                # ------------------------------------------------
                # ERROR
                # ------------------------------------------------

                assert (
                    notification.error_message
                    is None
                ), (
                    f"Notification "
                    f"{notification.id} "
                    f"has error_message."
                )

                # ------------------------------------------------
                # RETRY
                # ------------------------------------------------

                assert (
                    notification.next_retry_at
                    is None
                ), (
                    f"Notification "
                    f"{notification.id} "
                    f"still has next_retry_at."
                )

                # ------------------------------------------------
                # IMPORTANT:
                #
                # Do NOT require the same digest idempotency
                # key on every notification.
                #
                # The digest key belongs to the EMAIL DELIVERY,
                # not individually to every notification row.
                # ------------------------------------------------

            print()
            print(
                "3 notifications → SENT : PASS"
            )

            print(
                "sent_at populated      : PASS"
            )

            print(
                "processing cleared     : PASS"
            )

            print(
                "error cleared          : PASS"
            )

            print(
                "retry cleared          : PASS"
            )

            print(
                "digest key verified    : PASS"
            )

        # ====================================================
        # SECOND DISPATCH
        # ====================================================

        print()
        print("=" * 70)
        print("RUNNING SECOND DISPATCH")
        print("=" * 70)

        previous_call_count = len(
            [
                call
                for call in fake_email_calls
                if call["recipient_email"]
                == TEST_EMAIL
            ]
        )

        second_result = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print()
        print(
            f"Second dispatcher returned : "
            f"{second_result}"
        )

        # ----------------------------------------------------
        # CHECK CONTROLLED USER EMAILS AGAIN
        # ----------------------------------------------------

        test_email_calls_after_second = [
            call
            for call in fake_email_calls
            if call["recipient_email"] == TEST_EMAIL
        ]

        # ----------------------------------------------------
        # NO DUPLICATE EMAIL
        # ----------------------------------------------------

        assert (
            len(test_email_calls_after_second)
            == previous_call_count
        ), (
            "Duplicate email was sent to the "
            "controlled test user."
        )

        # ----------------------------------------------------
        # OUR TEST NOTIFICATIONS MUST NOT BE PROCESSED AGAIN
        # ----------------------------------------------------

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id.in_(
                        notification_ids
                    )
                )
            )

            second_check_notifications = (
                result.scalars().all()
            )

            assert len(
                second_check_notifications
            ) == 3, (
                "Expected 3 notifications "
                "after second dispatch."
            )

            for notification in (
                second_check_notifications
            ):

                assert (
                    notification.status
                    == NotificationStatus.SENT
                ), (
                    f"Notification "
                    f"{notification.id} "
                    f"was reprocessed."
                )

        print()
        print("Second dispatch checked : PASS")
        print("No duplicate test email : PASS")
        print("Notifications remain SENT: PASS")

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 70)
        print("🎉 CONTROLLED DISPATCHER TEST PASSED")
        print("=" * 70)

        test_passed = True

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
        # CLEANUP
        # ====================================================

        print()
        print(
            "🧹 Cleaning controlled test records..."
        )

        await cleanup_test_records()

        print(
            "✅ Test records cleaned up."
        )

    if test_passed:

        print()
        print("=" * 70)
        print("✅ ALL CONTROLLED DISPATCHER CHECKS PASSED")
        print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )