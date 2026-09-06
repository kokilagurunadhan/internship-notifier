import asyncio

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import (
    Notification,
    NotificationStatus,
)

import app.services.notification_dispatcher as dispatcher


TEST_EMAIL = "test12_email_retry_20260904@example.com"
TEST_COMPANY = "Test Email Retry Company 12"
TEST_DOMAIN = "software"
TEST_TITLE = "Software Engineering Intern"

TEST_URL = (
    "https://example.com/jobs/"
    "test-12-email-retry-20260904-001"
)


email_attempt_count = 0
fake_email_calls = []
isolated_notifications = []


def fake_send_notification_email(
    recipient_email,
    internships,
    idempotency_key,
):
    global email_attempt_count

    email_attempt_count += 1

    fake_email_calls.append(
        {
            "recipient_email": recipient_email,
            "internships": internships,
            "idempotency_key": idempotency_key,
        }
    )

    print()
    print("=" * 70)
    print("FAKE EMAIL SENDER")
    print("=" * 70)

    print(f"Attempt           : {email_attempt_count}")
    print(f"Recipient email   : {recipient_email}")
    print(f"Internships       : {len(internships)}")
    print(f"Idempotency key   : {idempotency_key}")

    assert recipient_email == TEST_EMAIL
    assert internships is not None
    assert len(internships) == 1
    assert idempotency_key is not None
    assert idempotency_key != ""
    assert idempotency_key.startswith("internship-digest:")

    print("recipient_email correct")
    print("internships argument correct")
    print("idempotency_key correct")

    if email_attempt_count == 1:
        print()
        print("SIMULATED EMAIL FAILURE")
        return None

    if email_attempt_count == 2:
        print()
        print("SIMULATED EMAIL SUCCESS")

        return {
            "success": True,
            "recipient": recipient_email,
            "idempotency_key": idempotency_key,
        }

    raise AssertionError(
        "Unexpected third email attempt."
    )


async def isolate_existing_pending_notifications():

    global isolated_notifications

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification).where(
                Notification.status
                == NotificationStatus.PENDING
            )
        )

        notifications = result.scalars().all()

        isolated_notifications = []

        for notification in notifications:

            isolated_notifications.append(
                (
                    notification.id,
                    notification.next_retry_at,
                )
            )

            notification.next_retry_at = (
                datetime.now(timezone.utc)
                + timedelta(days=365)
            )

        await db.commit()

    print(
        f"Isolated {len(isolated_notifications)} "
        f"pre-existing PENDING notification(s)"
    )


async def restore_existing_pending_notifications():

    global isolated_notifications

    if not isolated_notifications:
        return

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
        f"Restored {len(isolated_notifications)} "
        f"pre-existing PENDING notification(s)"
    )

    isolated_notifications.clear()


async def cleanup_test_records():

    async with AsyncSessionLocal() as db:

        internship_result = await db.execute(
            select(Internship.id).where(
                Internship.url == TEST_URL
            )
        )

        internship_ids = (
            internship_result.scalars().all()
        )

        if internship_ids:

            await db.execute(
                delete(Notification).where(
                    Notification.internship_id.in_(
                        internship_ids
                    )
                )
            )

        await db.execute(
            delete(Notification).where(
                Notification.user_email
                == TEST_EMAIL
            )
        )

        await db.execute(
            delete(Internship).where(
                Internship.url == TEST_URL
            )
        )

        await db.execute(
            delete(Subscription).where(
                Subscription.user_email
                == TEST_EMAIL
            )
        )

        await db.commit()


async def main():

    global email_attempt_count

    print()
    print("=" * 70)
    print("TEST 12 - EMAIL FAILURE + RETRY")
    print("=" * 70)

    email_attempt_count = 0
    fake_email_calls.clear()

    print()
    print("=" * 70)
    print("CLEANING PREVIOUS TEST 12 DATA")
    print("=" * 70)

    await cleanup_test_records()

    print("Previous Test 12 data cleaned")

    await isolate_existing_pending_notifications()

    original_email_function = (
        dispatcher.send_notification_email
    )

    dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    try:

        print()
        print("=" * 70)
        print("STEP 1 - CREATE SUBSCRIPTION")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            subscription = Subscription(
                user_email=TEST_EMAIL,
                company=TEST_COMPANY,
                domain=TEST_DOMAIN,
                is_active=True,
            )

            db.add(subscription)

            await db.commit()
            await db.refresh(subscription)

            subscription_id = subscription.id

            print(
                f"Subscription ID : {subscription_id}"
            )
            print(
                f"User email      : {subscription.user_email}"
            )
            print(
                f"Company         : {subscription.company}"
            )
            print(
                f"Domain          : {subscription.domain}"
            )
            print(
                f"Active          : {subscription.is_active}"
            )

            assert subscription.user_email == TEST_EMAIL
            assert subscription.company == TEST_COMPANY
            assert subscription.domain == TEST_DOMAIN
            assert subscription.is_active is True

        print("Subscription created")

        print()
        print("=" * 70)
        print("STEP 2 - CREATE INTERNSHIP")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            internship = Internship(
                company=TEST_COMPANY,
                title=TEST_TITLE,
                location="India",
                url=TEST_URL,
                description=(
                    "Software engineering "
                    "internship for students."
                ),
                source="Test",
                via="Test 12",
                relevance_score=68.99,
                passed_filter=True,
                status="RELEVANT",
                email_sent=False,
            )

            db.add(internship)

            await db.commit()
            await db.refresh(internship)

            internship_id = internship.id

            print(
                f"Internship ID : {internship_id}"
            )
            print(
                f"Company       : {internship.company}"
            )
            print(
                f"Title         : {internship.title}"
            )
            print(
                f"URL           : {internship.url}"
            )

            assert internship.url == TEST_URL

        print("Internship created")

        print()
        print("=" * 70)
        print("STEP 3 - CREATE PENDING NOTIFICATION")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            notification = Notification(
                subscription_id=subscription_id,
                user_email=TEST_EMAIL,
                internship_id=internship_id,
                status=NotificationStatus.PENDING,
                relevance_score=68.99,
                retry_count=0,
                error_message=None,
                sent_at=None,
                processing_started_at=None,
                idempotency_key=None,
                next_retry_at=None,
            )

            db.add(notification)

            await db.commit()
            await db.refresh(notification)

            notification_id = notification.id

            print(
                f"Notification ID : {notification_id}"
            )
            print(
                f"Status          : {notification.status}"
            )
            print(
                f"Retry count     : {notification.retry_count}"
            )

            assert (
                notification.status
                == NotificationStatus.PENDING
            )

            assert notification.retry_count == 0

        print("PENDING notification created")

        print()
        print("=" * 70)
        print("STEP 4 - VERIFY INITIAL STATE")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.id
                    == notification_id
                )
            )

            notification_before = (
                result.scalar_one()
            )

            assert (
                notification_before.status
                == NotificationStatus.PENDING
            )

            assert (
                notification_before.retry_count
                == 0
            )

            assert (
                notification_before.error_message
                is None
            )

            assert (
                notification_before.sent_at
                is None
            )

            assert (
                notification_before.next_retry_at
                is None
            )

            assert (
                notification_before.processing_started_at
                is None
            )

        print("Initial state verified")

        print()
        print("=" * 70)
        print("STEP 5 - FIRST DISPATCH")
        print("EXPECTED RESULT: EMAIL FAILURE")
        print("=" * 70)

        first_result = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print(
            f"Dispatcher result : {first_result}"
        )

        assert first_result == 0

        print("First dispatch failed as expected")

        print()
        print("=" * 70)
        print("STEP 6 - VERIFY FAILURE STATE")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.id
                    == notification_id
                )
            )

            failed_notification = (
                result.scalar_one()
            )

            print(
                f"Status             : "
                f"{failed_notification.status}"
            )

            print(
                f"Retry count        : "
                f"{failed_notification.retry_count}"
            )

            print(
                f"Error message      : "
                f"{failed_notification.error_message}"
            )

            print(
                f"Next retry at      : "
                f"{failed_notification.next_retry_at}"
            )

            print(
                f"Sent at            : "
                f"{failed_notification.sent_at}"
            )

            print(
                f"Processing started : "
                f"{failed_notification.processing_started_at}"
            )

            assert (
                failed_notification.status
                == NotificationStatus.PENDING
            )

            assert (
                failed_notification.retry_count
                == 1
            )

            assert (
                failed_notification.error_message
                is not None
            )

            assert (
                failed_notification.next_retry_at
                is not None
            )

            assert (
                failed_notification.sent_at
                is None
            )

            assert (
                failed_notification.processing_started_at
                is None
            )

        print("Failure state verified")

        print()
        print("=" * 70)
        print("STEP 7 - VERIFY FIRST EMAIL ATTEMPT")
        print("=" * 70)

        assert email_attempt_count == 1
        assert len(fake_email_calls) == 1

        first_call = fake_email_calls[0]

        assert (
            first_call["recipient_email"]
            == TEST_EMAIL
        )

        assert (
            first_call["internships"]
            is not None
        )

        assert (
            len(first_call["internships"])
            == 1
        )

        assert (
            first_call["idempotency_key"]
            is not None
        )

        assert (
            first_call["idempotency_key"]
            != ""
        )

        assert (
            first_call["idempotency_key"]
            .startswith("internship-digest:")
        )

        first_idempotency_key = (
            first_call["idempotency_key"]
        )

        print(
            f"Email attempts : {email_attempt_count}"
        )

        print(
            f"Recipient      : "
            f"{first_call['recipient_email']}"
        )

        print(
            f"Internships    : "
            f"{len(first_call['internships'])}"
        )

        print(
            f"Idempotency key: "
            f"{first_idempotency_key}"
        )

        print("First email attempt verified")

        print()
        print("=" * 70)
        print("STEP 8 - MAKE RETRY ELIGIBLE")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.id
                    == notification_id
                )
            )

            retry_notification = (
                result.scalar_one()
            )

            retry_notification.next_retry_at = (
                datetime.now(timezone.utc)
                - timedelta(seconds=1)
            )

            await db.commit()

        print(
            "next_retry_at moved into the past"
        )

        print("Retry is now eligible")

        print()
        print("=" * 70)
        print("STEP 9 - VERIFY RETRY ELIGIBILITY")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.id
                    == notification_id
                )
            )

            retry_ready = result.scalar_one()

            assert (
                retry_ready.status
                == NotificationStatus.PENDING
            )

            assert retry_ready.retry_count == 1

            assert (
                retry_ready.next_retry_at
                is not None
            )

            assert (
                retry_ready.next_retry_at
                <= datetime.now(timezone.utc)
            )

        print("Retry eligibility verified")

        print()
        print("=" * 70)
        print("STEP 10 - SECOND DISPATCH")
        print("EXPECTED RESULT: EMAIL SUCCESS")
        print("=" * 70)

        second_result = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print(
            f"Dispatcher result : {second_result}"
        )

        assert second_result == 1

        print("Second dispatch succeeded")

        print()
        print("=" * 70)
        print("STEP 11 - VERIFY EMAIL ATTEMPTS")
        print("=" * 70)

        assert email_attempt_count == 2
        assert len(fake_email_calls) == 2

        second_call = fake_email_calls[1]

        assert (
            second_call["recipient_email"]
            == TEST_EMAIL
        )

        assert (
            len(second_call["internships"])
            == 1
        )

        assert (
            second_call["idempotency_key"]
            is not None
        )

        print("Attempt 1 : FAILURE")
        print("Attempt 2 : SUCCESS")
        print(
            f"Total attempts : {email_attempt_count}"
        )

        print("Exactly two email attempts occurred")

        print()
        print("=" * 70)
        print("STEP 12 - VERIFY IDEMPOTENCY KEY")
        print("=" * 70)

        second_idempotency_key = (
            second_call["idempotency_key"]
        )

        print(
            f"First key  : {first_idempotency_key}"
        )

        print(
            f"Second key : {second_idempotency_key}"
        )

        assert (
            second_idempotency_key
            == first_idempotency_key
        )

        print(
            "Idempotency key remained consistent"
        )

        print()
        print("=" * 70)
        print("STEP 13 - VERIFY FINAL SENT STATE")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.id
                    == notification_id
                )
            )

            final_notification = (
                result.scalar_one()
            )

            print(
                f"Status             : "
                f"{final_notification.status}"
            )

            print(
                f"Retry count        : "
                f"{final_notification.retry_count}"
            )

            print(
                f"Error message      : "
                f"{final_notification.error_message}"
            )

            print(
                f"Sent at            : "
                f"{final_notification.sent_at}"
            )

            print(
                f"Next retry at      : "
                f"{final_notification.next_retry_at}"
            )

            print(
                f"Processing started : "
                f"{final_notification.processing_started_at}"
            )

            print(
                f"Idempotency key    : "
                f"{final_notification.idempotency_key}"
            )

            assert (
                final_notification.status
                == NotificationStatus.SENT
            )

            assert (
                final_notification.sent_at
                is not None
            )

            assert (
                final_notification.processing_started_at
                is None
            )

            assert (
                final_notification.error_message
                is None
            )

            assert (
                final_notification.next_retry_at
                is None
            )

            assert (
                final_notification.retry_count
                == 1
            )

            assert (
                final_notification.user_email
                == TEST_EMAIL
            )

            assert (
                final_notification.internship_id
                == internship_id
            )

            assert (
                final_notification.idempotency_key
                == first_idempotency_key
            )

        print("Final SENT state verified")

        print()
        print("=" * 70)
        print("STEP 14 - VERIFY NO DUPLICATE")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email
                    == TEST_EMAIL,
                    Notification.internship_id
                    == internship_id,
                )
            )

            notifications = (
                result.scalars().all()
            )

            assert len(notifications) == 1

            sent_notifications = [
                notification
                for notification in notifications
                if notification.status
                == NotificationStatus.SENT
            ]

            assert len(sent_notifications) == 1

            print(
                f"Notification count : "
                f"{len(notifications)}"
            )

            print("SENT notifications : 1")
            print("No duplicate notification created")

        print()
        print("=" * 70)
        print("STEP 15 - VERIFY NO PENDING")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email
                    == TEST_EMAIL,
                    Notification.internship_id
                    == internship_id,
                    Notification.status
                    == NotificationStatus.PENDING,
                )
            )

            pending_notifications = (
                result.scalars().all()
            )

            assert len(pending_notifications) == 0

            print(
                "PENDING notifications : 0"
            )

        print("No PENDING notification remains")

        print()
        print("=" * 70)
        print("STEP 16 - VERIFY NO THIRD ATTEMPT")
        print("=" * 70)

        assert email_attempt_count == 2

        print("Email attempts : 2")
        print("Third attempt  : NOT performed")
        print("No unexpected third attempt")

        print()
        print("=" * 70)
        print("TEST 12 PASSED")
        print("EMAIL FAILURE + RETRY VERIFIED")
        print("=" * 70)

    finally:

        dispatcher.send_notification_email = (
            original_email_function
        )

        print()
        print("Original email function restored")

        await cleanup_test_records()

        await restore_existing_pending_notifications()

        print("Test 12 data cleaned")


def test_email_failure_and_retry():

    asyncio.run(main())


if __name__ == "__main__":

    asyncio.run(main())