# ============================================================
# TEST 13 — NETWORK FAILURE AFTER EMAIL ACCEPTANCE
# ============================================================
#
# PURPOSE:
#
# Simulate the most dangerous email failure:
#
#     Application sends email
#             ↓
#     Provider accepts email
#             ↓
#     Email is actually delivered
#             ↓
#     Network response is lost
#             ↓
#     Application sees exception
#             ↓
#     Notification becomes PENDING
#             ↓
#     Retry becomes eligible
#             ↓
#     SAME IDEMPOTENCY KEY
#             ↓
#     Provider recognizes duplicate operation
#             ↓
#     NO second delivery
#             ↓
#     Notification becomes SENT
#
#
# CURRENT ARCHITECTURE:
#
# AsyncSessionLocal
# PostgreSQL
# Notification.internship_id
# Subscription.user_email
# Subscription.is_active
# notification_dispatcher
#
#
# DOES NOT USE:
#
# SessionLocal
# Subscription.email
# Subscription.active
# Notification.job_id
# notification_service.send_pending_notifications()
#
# ============================================================


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


# ============================================================
# TEST DATA
# ============================================================

TEST_EMAIL = (
    "test13_network_failure_20260904@example.com"
)

TEST_COMPANY = (
    "Test Network Failure Company 13"
)

TEST_DOMAIN = (
    "software"
)

TEST_TITLE = (
    "Software Engineering Intern"
)

TEST_URL = (
    "https://example.com/jobs/"
    "test-13-network-failure-20260904-001"
)


# ============================================================
# CONTROLLED PROVIDER STATE
# ============================================================

send_attempt_count = 0

actual_delivery_count = 0

accepted_idempotency_keys = set()

provider_idempotency_responses = {}


# ============================================================
# FAKE EMAIL PROVIDER
# ============================================================

def fake_send_notification_email(
    recipient_email,
    internships,
    idempotency_key,
):

    global send_attempt_count
    global actual_delivery_count

    send_attempt_count += 1

    print()
    print("=" * 70)
    print("📨 FAKE EMAIL PROVIDER")
    print("=" * 70)

    print(
        f"Attempt          : "
        f"{send_attempt_count}"
    )

    print(
        f"Recipient        : "
        f"{recipient_email}"
    )

    print(
        f"Internships      : "
        f"{len(internships)}"
    )

    print(
        f"Idempotency key  : "
        f"{idempotency_key}"
    )

    # ========================================================
    # VERIFY INPUTS
    # ========================================================

    assert (
        recipient_email
        == TEST_EMAIL
    ), (
        "Wrong recipient email."
    )

    assert (
        internships is not None
    ), (
        "Internships argument is missing."
    )

    assert (
        len(internships) == 1
    ), (
        "Expected exactly one internship "
        "in the digest."
    )

    assert (
        idempotency_key is not None
    ), (
        "Idempotency key is missing."
    )

    assert (
        idempotency_key != ""
    ), (
        "Idempotency key is empty."
    )

    assert (
        str(idempotency_key)
        .startswith(
            "internship-digest:"
        )
    ), (
        "Invalid idempotency key format."
    )

    print(
        "✅ recipient_email correct"
    )

    print(
        "✅ internships argument correct"
    )

    print(
        "✅ idempotency_key correct"
    )

    # ========================================================
    # FIRST REQUEST
    #
    # Provider accepts and delivers email.
    #
    # Then network response is lost.
    # ========================================================

    if (
        idempotency_key
        not in accepted_idempotency_keys
    ):

        print()
        print(
            "📡 FIRST PROVIDER REQUEST"
        )

        print(
            "✅ Provider ACCEPTED email"
        )

        # ----------------------------------------------------
        # ACTUAL DELIVERY
        # ----------------------------------------------------

        actual_delivery_count += 1

        print(
            "📬 Email actually delivered"
        )

        print(
            f"📬 Actual delivery count: "
            f"{actual_delivery_count}"
        )

        # ----------------------------------------------------
        # PROVIDER STORES IDEMPOTENCY KEY
        # ----------------------------------------------------

        accepted_idempotency_keys.add(
            idempotency_key
        )

        provider_idempotency_responses[
            idempotency_key
        ] = {
            "id": (
                "fake-provider-message-13"
            ),
            "status": "accepted",
            "idempotency_key": (
                idempotency_key
            ),
        }

        print(
            "💾 Provider stored idempotency key"
        )

        # ----------------------------------------------------
        # SIMULATE NETWORK FAILURE
        # ----------------------------------------------------

        print()
        print(
            "🌐 SIMULATING NETWORK FAILURE"
        )

        print(
            "⚠️ Email was already delivered."
        )

        print(
            "⚠️ Application does not receive "
            "provider success response."
        )

        raise ConnectionError(
            "Network connection lost "
            "after provider accepted "
            "and delivered the email."
        )

    # ========================================================
    # RETRY REQUEST
    #
    # SAME IDEMPOTENCY KEY
    # ========================================================

    print()
    print(
        "🔁 RETRY REQUEST RECEIVED"
    )

    print(
        "🔐 Same idempotency key detected"
    )

    assert (
        idempotency_key
        in accepted_idempotency_keys
    ), (
        "Provider did not recognize "
        "the previous idempotency key."
    )

    print(
        "🛡️ Provider recognizes "
        "previous accepted operation"
    )

    # --------------------------------------------------------
    # CRITICAL:
    #
    # DO NOT deliver another email.
    # --------------------------------------------------------

    print(
        "⏭️ Duplicate delivery prevented"
    )

    print(
        f"📬 Actual deliveries remain: "
        f"{actual_delivery_count}"
    )

    assert (
        actual_delivery_count == 1
    ), (
        "Duplicate email was delivered."
    )

    # --------------------------------------------------------
    # RETURN PREVIOUS PROVIDER RESPONSE
    # --------------------------------------------------------

    return provider_idempotency_responses[
        idempotency_key
    ]


# ============================================================
# CLEANUP
# ============================================================

async def cleanup_test_records():

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # FIND TEST INTERNSHIP
        # ----------------------------------------------------

        internship_result = await db.execute(
            select(Internship.id)
            .where(
                Internship.url
                == TEST_URL
            )
        )

        internship_ids = (
            internship_result
            .scalars()
            .all()
        )

        # ----------------------------------------------------
        # DELETE NOTIFICATIONS CONNECTED TO
        # TEST INTERNSHIP
        # ----------------------------------------------------

        if internship_ids:

            await db.execute(
                delete(Notification)
                .where(
                    Notification.internship_id.in_(
                        internship_ids
                    )
                )
            )

        # ----------------------------------------------------
        # DELETE ALL TEST USER NOTIFICATIONS
        # ----------------------------------------------------

        await db.execute(
            delete(Notification)
            .where(
                Notification.user_email
                == TEST_EMAIL
            )
        )

        # ----------------------------------------------------
        # DELETE TEST INTERNSHIP
        # ----------------------------------------------------

        await db.execute(
            delete(Internship)
            .where(
                Internship.url
                == TEST_URL
            )
        )

        # ----------------------------------------------------
        # DELETE TEST SUBSCRIPTION
        # ----------------------------------------------------

        await db.execute(
            delete(Subscription)
            .where(
                Subscription.user_email
                == TEST_EMAIL
            )
        )

        await db.commit()


# ============================================================
# ISOLATE PRE-EXISTING PENDING NOTIFICATIONS
# ============================================================

async def isolate_existing_pending_notifications():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification)
            .where(
                Notification.status
                == NotificationStatus.PENDING
            )
        )

        notifications = (
            result
            .scalars()
            .all()
        )

        original_retry_times = {}

        future_time = (
            datetime.now(timezone.utc)
            + timedelta(days=365)
        )

        for notification in notifications:

            original_retry_times[
                notification.id
            ] = notification.next_retry_at

            notification.next_retry_at = (
                future_time
            )

        await db.commit()

        return original_retry_times


# ============================================================
# RESTORE PRE-EXISTING PENDING NOTIFICATIONS
# ============================================================

async def restore_pending_notifications(
    original_retry_times
):

    if not original_retry_times:
        return

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification)
            .where(
                Notification.id.in_(
                    original_retry_times.keys()
                )
            )
        )

        notifications = (
            result
            .scalars()
            .all()
        )

        for notification in notifications:

            notification.next_retry_at = (
                original_retry_times[
                    notification.id
                ]
            )

        await db.commit()


# ============================================================
# MAIN TEST
# ============================================================

async def main():

    global send_attempt_count
    global actual_delivery_count

    print()
    print("=" * 70)
    print(
        "🧪 TEST 13 — NETWORK FAILURE "
        "AFTER EMAIL ACCEPTANCE"
    )
    print("=" * 70)

    # ========================================================
    # RESET CONTROLLED STATE
    # ========================================================

    send_attempt_count = 0

    actual_delivery_count = 0

    accepted_idempotency_keys.clear()

    provider_idempotency_responses.clear()

    # ========================================================
    # CLEAN PREVIOUS TEST DATA
    # ========================================================

    print()
    print("=" * 70)
    print(
        "🧹 CLEANING PREVIOUS TEST 13 DATA"
    )
    print("=" * 70)

    await cleanup_test_records()

    print(
        "✅ Previous Test 13 data cleaned"
    )

    # ========================================================
    # ISOLATE PRE-EXISTING PENDING NOTIFICATIONS
    #
    # IMPORTANT:
    #
    # This MUST happen before Test 13 creates its own
    # notification.
    #
    # Otherwise the dispatcher could process notifications
    # belonging to other tests.
    # ========================================================

    original_pending_retry_times = (
        await isolate_existing_pending_notifications()
    )

    print(
        f"🔒 Temporarily isolated "
        f"{len(original_pending_retry_times)} "
        f"pre-existing PENDING notification(s)"
    )

    # ========================================================
    # SAVE ORIGINAL EMAIL FUNCTION
    # ========================================================

    original_email_function = (
        dispatcher.send_notification_email
    )

    # ========================================================
    # REPLACE ONLY DISPATCHER EMAIL FUNCTION
    # ========================================================

    dispatcher.send_notification_email = (
        fake_send_notification_email
    )

    try:

        # ====================================================
        # STEP 1
        # CREATE SUBSCRIPTION
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 1 — CREATE SUBSCRIPTION"
        )
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

            await db.refresh(
                subscription
            )

            subscription_id = (
                subscription.id
            )

            print(
                f"Subscription ID : "
                f"{subscription_id}"
            )

            print(
                f"User email      : "
                f"{subscription.user_email}"
            )

            print(
                f"Company         : "
                f"{subscription.company}"
            )

            print(
                f"Domain          : "
                f"{subscription.domain}"
            )

            print(
                f"Active          : "
                f"{subscription.is_active}"
            )

            assert (
                subscription.user_email
                == TEST_EMAIL
            )

            assert (
                subscription.is_active
                is True
            )

        print()
        print(
            "✅ Subscription created"
        )

        # ====================================================
        # STEP 2
        # CREATE INTERNSHIP
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 2 — CREATE INTERNSHIP"
        )
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

                via="Test 13",

                relevance_score=68.99,

                passed_filter=True,

                status="RELEVANT",

                email_sent=False,
            )

            db.add(internship)

            await db.commit()

            await db.refresh(
                internship
            )

            internship_id = (
                internship.id
            )

            print(
                f"Internship ID : "
                f"{internship_id}"
            )

            print(
                f"Company       : "
                f"{internship.company}"
            )

            print(
                f"Title         : "
                f"{internship.title}"
            )

            print(
                f"URL           : "
                f"{internship.url}"
            )

            print(
                f"Email sent    : "
                f"{internship.email_sent}"
            )

            assert (
                internship.url
                == TEST_URL
            )

            assert (
                internship.email_sent
                is False
            )

        print()
        print(
            "✅ Internship created"
        )

        # ====================================================
        # STEP 3
        # CREATE PENDING NOTIFICATION
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 3 — CREATE PENDING NOTIFICATION"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            notification = Notification(

                subscription_id=(
                    subscription_id
                ),

                user_email=TEST_EMAIL,

                internship_id=(
                    internship_id
                ),

                status=(
                    NotificationStatus.PENDING
                ),

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

            await db.refresh(
                notification
            )

            notification_id = (
                notification.id
            )

            print(
                f"Notification ID : "
                f"{notification_id}"
            )

            print(
                f"Status          : "
                f"{notification.status}"
            )

            print(
                f"Internship ID   : "
                f"{notification.internship_id}"
            )

            assert (
                notification.status
                == NotificationStatus.PENDING
            )

            assert (
                notification.internship_id
                == internship_id
            )

        print()
        print(
            "✅ PENDING notification created"
        )

        # ====================================================
        # STEP 4
        # VERIFY INITIAL STATE
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 4 — VERIFY INITIAL STATE"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id
                    == notification_id
                )
            )

            initial_notification = (
                result.scalar_one()
            )

            assert (
                initial_notification.status
                == NotificationStatus.PENDING
            )

            assert (
                initial_notification.retry_count
                == 0
            )

            assert (
                initial_notification.error_message
                is None
            )

            assert (
                initial_notification.sent_at
                is None
            )

            assert (
                initial_notification.next_retry_at
                is None
            )

            assert (
                initial_notification
                .processing_started_at
                is None
            )

            assert (
                initial_notification
                .idempotency_key
                is None
            )

        print(
            "Status             : PENDING"
        )

        print(
            "Retry count        : 0"
        )

        print(
            "Error message      : None"
        )

        print(
            "Sent at            : None"
        )

        print(
            "Next retry         : None"
        )

        print(
            "Idempotency key    : None"
        )

        print()
        print(
            "✅ Initial state verified"
        )

        # ====================================================
        # STEP 5
        # FIRST DISPATCH
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 5 — FIRST DISPATCH"
        )
        print(
            "EXPECTED: PROVIDER ACCEPTS, "
            "DELIVERS, THEN NETWORK FAILS"
        )
        print("=" * 70)

        first_result = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print()
        print(
            f"First dispatcher result : "
            f"{first_result}"
        )

        assert (
            first_result == 0
        ), (
            "First dispatch should not "
            "count as successful."
        )

        print()
        print(
            "✅ First dispatch reported failure"
        )

        # ====================================================
        # STEP 6
        # VERIFY PROVIDER DELIVERY
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 6 — VERIFY ACTUAL DELIVERY"
        )
        print("=" * 70)

        assert (
            send_attempt_count == 1
        ), (
            "Expected exactly one provider attempt."
        )

        assert (
            actual_delivery_count == 1
        ), (
            "Provider should have delivered "
            "exactly one email."
        )

        assert (
            len(
                accepted_idempotency_keys
            )
            == 1
        ), (
            "Provider should have stored "
            "exactly one idempotency key."
        )

        first_idempotency_key = next(
            iter(
                accepted_idempotency_keys
            )
        )

        print(
            f"Provider attempts : "
            f"{send_attempt_count}"
        )

        print(
            f"Actual deliveries: "
            f"{actual_delivery_count}"
        )

        print(
            f"Accepted keys    : "
            f"{len(accepted_idempotency_keys)}"
        )

        print(
            f"Idempotency key  : "
            f"{first_idempotency_key}"
        )

        print()
        print(
            "✅ Email was actually delivered once"
        )

        print(
            "✅ Provider stored idempotency key"
        )

        # ====================================================
        # STEP 7
        # VERIFY APPLICATION FAILURE STATE
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 7 — VERIFY APPLICATION "
            "FAILURE STATE"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
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

            print(
                f"Stored idempotency : "
                f"{failed_notification.idempotency_key}"
            )

            assert (
                failed_notification.status
                == NotificationStatus.PENDING
            ), (
                "Notification must return "
                "to PENDING after network failure."
            )

            print(
                "✅ Notification remains PENDING"
            )

            assert (
                failed_notification.retry_count
                == 1
            ), (
                "retry_count must increase to 1."
            )

            print(
                "✅ retry_count = 1"
            )

            assert (
                failed_notification.error_message
                is not None
            ), (
                "Network failure must be recorded."
            )

            print(
                "✅ error_message recorded"
            )

            assert (
                failed_notification.sent_at
                is None
            ), (
                "sent_at must remain NULL "
                "because application did not "
                "receive provider success."
            )

            print(
                "✅ sent_at remains NULL"
            )

            assert (
                failed_notification
                .processing_started_at
                is None
            ), (
                "Processing lease must be cleared."
            )

            print(
                "✅ processing_started_at cleared"
            )

            assert (
                failed_notification
                .next_retry_at
                is not None
            ), (
                "next_retry_at must be scheduled."
            )

            print(
                "✅ next_retry_at scheduled"
            )

        # ====================================================
        # STEP 8
        # VERIFY INTERNSHIP STILL FALSE
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 8 — VERIFY INTERNSHIP STATE"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Internship)
                .where(
                    Internship.id
                    == internship_id
                )
            )

            internship_after_failure = (
                result.scalar_one()
            )

            print(
                f"email_sent : "
                f"{internship_after_failure.email_sent}"
            )

            assert (
                internship_after_failure
                .email_sent
                is False
            ), (
                "Application must not mark "
                "email_sent=True when the "
                "provider response was lost."
            )

        print()
        print(
            "✅ Internship remains email_sent=False"
        )

        # ====================================================
        # STEP 9
        # MAKE RETRY ELIGIBLE
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 9 — MAKE RETRY ELIGIBLE"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id
                    == notification_id
                )
            )

            retry_notification = (
                result.scalar_one()
            )

            retry_notification.next_retry_at = (
                datetime.now(
                    timezone.utc
                )
                - timedelta(
                    seconds=1
                )
            )

            await db.commit()

        print(
            "⏰ Retry time moved into the past"
        )

        print(
            "✅ Retry is now eligible"
        )

        # ====================================================
        # STEP 10
        # VERIFY RETRY ELIGIBILITY
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 10 — VERIFY RETRY ELIGIBILITY"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.id
                    == notification_id
                )
            )

            retry_ready = (
                result.scalar_one()
            )

            assert (
                retry_ready.status
                == NotificationStatus.PENDING
            )

            assert (
                retry_ready.retry_count
                == 1
            )

            assert (
                retry_ready.next_retry_at
                is not None
            )

            assert (
                retry_ready.next_retry_at
                <= datetime.now(
                    timezone.utc
                )
            )

        print(
            "Status        : PENDING"
        )

        print(
            "Retry count   : 1"
        )

        print(
            "Retry eligible: YES"
        )

        print()
        print(
            "✅ Retry eligibility verified"
        )

        # ====================================================
        # STEP 11
        # SECOND DISPATCH
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 11 — SECOND DISPATCH"
        )
        print(
            "EXPECTED: IDEMPOTENT RETRY SUCCESS"
        )
        print("=" * 70)

        second_result = (
            await dispatcher
            .dispatch_pending_notifications_batch()
        )

        print()
        print(
            f"Second dispatcher result : "
            f"{second_result}"
        )

        assert (
            second_result == 1
        ), (
            "Second dispatch should succeed."
        )

        print()
        print(
            "✅ Retry dispatch succeeded"
        )

        # ====================================================
        # STEP 12
        # VERIFY TWO APPLICATION ATTEMPTS
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 12 — VERIFY SEND ATTEMPTS"
        )
        print("=" * 70)

        assert (
            send_attempt_count == 2
        ), (
            "Expected exactly two provider "
            "requests."
        )

        print(
            "Attempt 1 : provider accepted "
            "+ network failure"
        )

        print(
            "Attempt 2 : idempotent retry"
        )

        print(
            f"Total provider attempts : "
            f"{send_attempt_count}"
        )

        print()
        print(
            "✅ Exactly two provider attempts occurred"
        )

        # ====================================================
        # STEP 13
        # VERIFY ONLY ONE ACTUAL DELIVERY
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 13 — VERIFY NO DUPLICATE EMAIL"
        )
        print("=" * 70)

        assert (
            actual_delivery_count == 1
        ), (
            "Duplicate email was delivered "
            "during retry."
        )

        print(
            f"Actual deliveries : "
            f"{actual_delivery_count}"
        )

        print()
        print(
            "✅ EXACTLY ONE EMAIL WAS DELIVERED"
        )

        print(
            "🛡️ Idempotency protection worked"
        )

        # ====================================================
        # STEP 14
        # VERIFY SAME IDEMPOTENCY KEY
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 14 — VERIFY SAME "
            "IDEMPOTENCY KEY"
        )
        print("=" * 70)

        assert (
            len(accepted_idempotency_keys)
            == 1
        )

        provider_key = next(
            iter(
                accepted_idempotency_keys
            )
        )

        assert (
            provider_key
            == first_idempotency_key
        )

        print(
            f"First accepted key : "
            f"{first_idempotency_key}"
        )

        print(
            f"Retry key           : "
            f"{provider_key}"
        )

        print()
        print(
            "✅ Same idempotency key recognized"
        )

        # ====================================================
        # STEP 15
        # VERIFY FINAL NOTIFICATION
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 15 — VERIFY FINAL "
            "NOTIFICATION STATE"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
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

            print(
                "✅ Notification = SENT"
            )

            assert (
                final_notification.sent_at
                is not None
            )

            print(
                "✅ sent_at recorded"
            )

            assert (
                final_notification.retry_count
                == 1
            )

            print(
                "✅ retry_count remains 1"
            )

            assert (
                final_notification.error_message
                is None
            )

            print(
                "✅ error_message cleared"
            )

            assert (
                final_notification.next_retry_at
                is None
            )

            print(
                "✅ next_retry_at cleared"
            )

            assert (
                final_notification
                .processing_started_at
                is None
            )

            print(
                "✅ processing_started_at cleared"
            )

            assert (
                final_notification.user_email
                == TEST_EMAIL
            )

            print(
                "✅ Correct user_email"
            )

            assert (
                final_notification.internship_id
                == internship_id
            )

            print(
                "✅ Correct internship_id"
            )

            assert (
                final_notification.idempotency_key
                == first_idempotency_key
            )

            print(
                "✅ Idempotency key persisted"
            )

        # ====================================================
        # STEP 17
        # VERIFY EXACTLY ONE NOTIFICATION
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 17 — VERIFY NO DUPLICATE "
            "NOTIFICATION"
        )
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
            )

            notifications = (
                result
                .scalars()
                .all()
            )

            print(
                f"Notification count : "
                f"{len(notifications)}"
            )

            assert (
                len(notifications) == 1
            ), (
                "Retry created a duplicate "
                "notification."
            )

            assert (
                notifications[0].status
                == NotificationStatus.SENT
            )

        print()
        print(
            "✅ Exactly ONE notification exists"
        )

        # ====================================================
        # STEP 18
        # VERIFY NO PENDING REMAINS
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 18 — VERIFY NO PENDING "
            "NOTIFICATION"
        )
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Notification)
                .where(
                    Notification.user_email
                    == TEST_EMAIL,

                    Notification.internship_id
                    == internship_id,

                    Notification.status
                    == NotificationStatus.PENDING,
                )
            )

            pending_notifications = (
                result
                .scalars()
                .all()
            )

            assert (
                len(
                    pending_notifications
                )
                == 0
            )

        print(
            "PENDING notifications : 0"
        )

        print()
        print(
            "✅ No PENDING notification remains"
        )

        # ====================================================
        # STEP 19
        # FINAL DELIVERY COUNT
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🧪 STEP 19 — FINAL DELIVERY COUNT"
        )
        print("=" * 70)

        assert (
            actual_delivery_count == 1
        )

        print(
            "Provider attempts : 2"
        )

        print(
            "Actual deliveries : 1"
        )

        print(
            "Duplicate emails  : 0"
        )

        print()
        print(
            "✅ NETWORK FAILURE DID NOT "
            "CAUSE DUPLICATE DELIVERY"
        )

        # ====================================================
        # FINAL RESULT
        # ====================================================

        print()
        print("=" * 70)
        print(
            "🎉 TEST 13 PASSED"
        )
        print("=" * 70)

        print()
        print(
            "🔒 NETWORK FAILURE + "
            "IDEMPOTENCY PROTECTION VERIFIED"
        )

        print()
        print(
            "Verified behavior:"
        )

        print(
            "1. PENDING notification created"
        )

        print(
            "2. Dispatcher claimed notification"
        )

        print(
            "3. Provider received first request"
        )

        print(
            "4. Provider accepted the email"
        )

        print(
            "5. Email was actually delivered"
        )

        print(
            "6. Provider stored idempotency key"
        )

        print(
            "7. Network response was lost"
        )

        print(
            "8. Application recorded failure"
        )

        print(
            "9. Notification returned to PENDING"
        )

        print(
            "10. retry_count increased to 1"
        )

        print(
            "11. error_message was recorded"
        )

        print(
            "12. next_retry_at was scheduled"
        )

        print(
            "13. Internship remained email_sent=False"
        )

        print(
            "14. Retry became eligible"
        )

        print(
            "15. Same idempotency key was reused"
        )

        print(
            "16. Provider recognized previous operation"
        )

        print(
            "17. Retry did NOT deliver another email"
        )

        print(
            "18. Notification became SENT"
        )

        print(
            "20. sent_at was recorded"
        )

        print(
            "21. Exactly two provider attempts occurred"
        )

        print(
            "22. Exactly one email was delivered"
        )

        print(
            "23. Exactly one notification exists"
        )

        print(
            "24. No PENDING notification remains"
        )

        print()
        print("=" * 70)

    finally:

        # ====================================================
        # RESTORE REAL EMAIL FUNCTION
        # ====================================================

        dispatcher.send_notification_email = (
            original_email_function
        )

        print()
        print(
            "🔄 Original email function restored"
        )

        # ====================================================
        # CLEAN TEST DATA
        # ====================================================

        await cleanup_test_records()

        print(
            "🧹 Test 13 data cleaned"
        )

        # ====================================================
        # RESTORE OTHER TESTS' PENDING NOTIFICATIONS
        # ====================================================

        await restore_pending_notifications(
            original_pending_retry_times
        )

        print(
            "🔓 Pre-existing PENDING "
            "notifications restored"
        )


# ============================================================
# PYTEST ENTRY POINT
# ============================================================

def test_network_failure_after_email_acceptance():

    asyncio.run(
        main()
    )


# ============================================================
# DIRECT SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )