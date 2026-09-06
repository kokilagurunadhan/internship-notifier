
import pytest
from unittest.mock import AsyncMock, patch

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.services.pipeline_processor import (
    process_all_active_subscriptions,
)


@pytest.mark.asyncio
async def test_grouped_query_serpapi_behavior():
    """
    TEST 22

    Verify the LOCKED grouped-query architecture.

    Expected:

        Active subscriptions
                ↓
        Group by company + domain
                ↓
        One process_subscription() per group
                ↓
        All users in the same company/domain group
        are processed together.

    The test is designed to be safely rerunnable.
    """

    company = "Test22 Grouped Company"
    domain = "software"

    user_a = "test22_user_a@example.com"
    user_b = "test22_user_b@example.com"
    user_c = "test22_user_c@example.com"
    user_d = "test22_user_d@example.com"
    user_inactive = "test22_inactive@example.com"

    different_company = "Test22 Different Company"

    test_emails = {
        user_a,
        user_b,
        user_c,
        user_d,
        user_inactive,
    }

    previous_active_states = {}

    async with AsyncSessionLocal() as db:

        print("\n" + "=" * 70)
        print("🧪 TEST 22 — GROUPED QUERY SERPAPI BEHAVIOR")
        print("=" * 70)

        # ---------------------------------------------------------
        # 1. CLEAN UP LEFTOVER TEST22 DATA
        # ---------------------------------------------------------

        existing_test22_result = await db.execute(
            select(Subscription).where(
                Subscription.user_email.in_(test_emails)
            )
        )

        existing_test22_subscriptions = (
            existing_test22_result.scalars().all()
        )

        if existing_test22_subscriptions:

            print(
                f"\n🧹 Found "
                f"{len(existing_test22_subscriptions)} "
                f"leftover Test22 subscription(s)"
            )

            for subscription in existing_test22_subscriptions:
                print(
                    f"   Removing: "
                    f"{subscription.user_email}"
                )

            await db.execute(
                delete(Subscription).where(
                    Subscription.user_email.in_(test_emails)
                )
            )

            await db.commit()

            print("✅ Leftover Test22 data removed")

        # ---------------------------------------------------------
        # 2. TEMPORARILY DISABLE UNRELATED ACTIVE SUBSCRIPTIONS
        # ---------------------------------------------------------

        active_result = await db.execute(
            select(Subscription).where(
                Subscription.is_active.is_(True)
            )
        )

        existing_active_subscriptions = (
            active_result.scalars().all()
        )

        for subscription in existing_active_subscriptions:
            previous_active_states[
                subscription.id
            ] = subscription.is_active

            subscription.is_active = False

        await db.commit()

        print(
            f"\n🔒 Temporarily disabled "
            f"{len(existing_active_subscriptions)} "
            f"pre-existing active subscription(s)"
        )

        try:

            # -----------------------------------------------------
            # 3. CREATE TEST SUBSCRIPTIONS
            # -----------------------------------------------------

            subscription_a = Subscription(
                user_email=user_a,
                company=company,
                domain=domain,
                is_active=True,
            )

            subscription_b = Subscription(
                user_email=user_b,
                company=company,
                domain=domain,
                is_active=True,
            )

            subscription_c = Subscription(
                user_email=user_c,
                company=company,
                domain=domain,
                is_active=True,
            )

            # Different company = different group.
            subscription_d = Subscription(
                user_email=user_d,
                company=different_company,
                domain=domain,
                is_active=True,
            )

            # Same company/domain but inactive.
            subscription_inactive = Subscription(
                user_email=user_inactive,
                company=company,
                domain=domain,
                is_active=False,
            )

            db.add_all(
                [
                    subscription_a,
                    subscription_b,
                    subscription_c,
                    subscription_d,
                    subscription_inactive,
                ]
            )

            await db.commit()

            await db.refresh(subscription_a)
            await db.refresh(subscription_b)
            await db.refresh(subscription_c)
            await db.refresh(subscription_d)
            await db.refresh(subscription_inactive)

            print("\n👥 Created Test22 subscriptions:")

            print(
                f"   A → {user_a} "
                f"| {company} / {domain}"
            )

            print(
                f"   B → {user_b} "
                f"| {company} / {domain}"
            )

            print(
                f"   C → {user_c} "
                f"| {company} / {domain}"
            )

            print(
                f"   D → {user_d} "
                f"| {different_company} / {domain}"
            )

            print(
                f"   X → {user_inactive} "
                f"| INACTIVE"
            )

            # -----------------------------------------------------
            # 4. CAPTURE GROUP PROCESSING
            # -----------------------------------------------------

            calls = []

            async def fake_process_subscription(
                subscription,
                subscription_group,
            ):
                """
                Mock process_subscription().

                IMPORTANT:
                Production calls this function using:

                    subscription=...
                    subscription_group=...

                Therefore the mock must accept the same
                keyword argument names.
                """

                calls.append(
                    (
                        subscription,
                        list(subscription_group),
                    )
                )

                print("\n🔎 GROUP PROCESSED:")

                print(
                    f"   Company: "
                    f"{subscription.company}"
                )

                print(
                    f"   Domain: "
                    f"{subscription.domain}"
                )

                print(
                    f"   Users in group: "
                    f"{len(subscription_group)}"
                )

                for sub in subscription_group:
                    print(
                        f"      → "
                        f"{sub.user_email}"
                    )

                return {
                    "jobs_found": 1,
                    "jobs_saved": 1,
                }

            # -----------------------------------------------------
            # 5. RUN REAL ORCHESTRATION
            #
            # process_subscription() is mocked.
            #
            # We are testing:
            #
            # DB
            # ↓
            # active subscriptions
            # ↓
            # group_subscriptions()
            # ↓
            # one process_subscription() per group
            # -----------------------------------------------------

            with patch(
                "app.services.pipeline_processor.process_subscription",
                new=AsyncMock(
                    side_effect=fake_process_subscription
                ),
            ):

                result = (
                    await process_all_active_subscriptions()
                )

            # -----------------------------------------------------
            # 6. VERIFY ACTIVE SUBSCRIPTIONS
            # -----------------------------------------------------

            print("\n📊 Pipeline result:")
            print(result)

            assert result["subscriptions"] == 4

            print(
                "\n✅ CASE 1 PASSED: "
                "Only 4 active Test22 subscriptions "
                "were processed"
            )

            # -----------------------------------------------------
            # 7. VERIFY GROUP COUNT
            #
            # Group 1:
            #   A + B + C
            #
            # Group 2:
            #   D
            #
            # Total = 2
            # -----------------------------------------------------

            assert result["groups"] == 2

            print(
                "✅ CASE 2 PASSED: "
                "4 active subscriptions became 2 groups"
            )

            # -----------------------------------------------------
            # 8. VERIFY ONE PROCESS CALL PER GROUP
            # -----------------------------------------------------

            assert len(calls) == 2

            print(
                "✅ CASE 3 PASSED: "
                "Exactly one process_subscription() "
                "call per group"
            )

            # -----------------------------------------------------
            # 9. FIND GROUPED COMPANY
            # -----------------------------------------------------

            grouped_company_calls = [
                call
                for call in calls
                if call[0].company.lower()
                == company.lower()
                and call[0].domain.lower()
                == domain.lower()
            ]

            assert len(grouped_company_calls) == 1

            grouped_primary, grouped_users = (
                grouped_company_calls[0]
            )

            # -----------------------------------------------------
            # 10. VERIFY A + B + C ARE ONE GROUP
            # -----------------------------------------------------

            grouped_emails = {
                subscription.user_email
                for subscription in grouped_users
            }

            expected_grouped_emails = {
                user_a,
                user_b,
                user_c,
            }

            assert (
                grouped_emails
                == expected_grouped_emails
            )

            assert len(grouped_users) == 3

            print(
                "✅ CASE 4 PASSED: "
                "Users A, B and C were grouped together"
            )

            # -----------------------------------------------------
            # 11. VERIFY PRIMARY SUBSCRIPTION
            # -----------------------------------------------------

            assert (
                grouped_primary.user_email
                in expected_grouped_emails
            )

            print(
                "✅ CASE 5 PASSED: "
                "Primary subscription belongs "
                "to the correct group"
            )

            # -----------------------------------------------------
            # 12. VERIFY DIFFERENT COMPANY = DIFFERENT GROUP
            # -----------------------------------------------------

            different_company_calls = [
                call
                for call in calls
                if call[0].company.lower()
                == different_company.lower()
                and call[0].domain.lower()
                == domain.lower()
            ]

            assert len(different_company_calls) == 1

            _, different_company_users = (
                different_company_calls[0]
            )

            assert len(
                different_company_users
            ) == 1

            assert (
                different_company_users[0].user_email
                == user_d
            )

            print(
                "✅ CASE 6 PASSED: "
                "Different company created "
                "a separate group"
            )

            # -----------------------------------------------------
            # 13. VERIFY INACTIVE USER WAS IGNORED
            # -----------------------------------------------------

            processed_emails = {
                subscription.user_email
                for _, group in calls
                for subscription in group
            }

            assert (
                user_inactive
                not in processed_emails
            )

            print(
                "✅ CASE 7 PASSED: "
                "Inactive subscription was ignored"
            )

            # -----------------------------------------------------
            # 14. VERIFY EXACTLY 4 ACTIVE USERS PROCESSED
            # -----------------------------------------------------

            total_grouped_users = sum(
                len(group)
                for _, group in calls
            )

            assert total_grouped_users == 4

            print(
                "✅ CASE 8 PASSED: "
                "Exactly 4 active subscriptions "
                "entered groups"
            )

            # -----------------------------------------------------
            # 15. VERIFY NO USER WAS PROCESSED TWICE
            # -----------------------------------------------------

            all_processed_emails = [
                subscription.user_email
                for _, group in calls
                for subscription in group
            ]

            assert len(all_processed_emails) == 4

            assert len(
                set(all_processed_emails)
            ) == 4

            print(
                "✅ CASE 9 PASSED: "
                "No active subscription "
                "was processed twice"
            )

            # -----------------------------------------------------
            # 16. FINAL ARCHITECTURE VERIFICATION
            # -----------------------------------------------------

            print("\n" + "=" * 70)
            print("🎯 GROUPED QUERY ARCHITECTURE VERIFIED")
            print("=" * 70)

            print(
                """
Active subscriptions
        ↓
Group by company + domain
        ↓
A + B + C → ONE group
        ↓
ONE process_subscription() call
        ↓
D → separate group
        ↓
Inactive user → ignored
"""
            )

            print("=" * 70)
            print("🎉 TEST 22 PASSED")
            print("=" * 70)

        finally:

            # -----------------------------------------------------
            # 17. CLEAN UP TEST22 SUBSCRIPTIONS
            # -----------------------------------------------------

            try:

                await db.rollback()

                await db.execute(
                    delete(Subscription).where(
                        Subscription.user_email.in_(
                            test_emails
                        )
                    )
                )

                await db.commit()

                print(
                    "\n🧹 Test22 subscriptions cleaned up."
                )

            except Exception as cleanup_error:

                await db.rollback()

                print(
                    "\n⚠️ Test22 cleanup warning:"
                )

                print(
                    f"   {cleanup_error}"
                )

            # -----------------------------------------------------
            # 18. RESTORE PREVIOUS ACTIVE STATES
            # -----------------------------------------------------

            try:

                if previous_active_states:

                    result = await db.execute(
                        select(Subscription).where(
                            Subscription.id.in_(
                                previous_active_states.keys()
                            )
                        )
                    )

                    subscriptions_to_restore = (
                        result.scalars().all()
                    )

                    for subscription in (
                        subscriptions_to_restore
                    ):
                        subscription.is_active = (
                            previous_active_states[
                                subscription.id
                            ]
                        )

                    await db.commit()

                    print(
                        "🔓 Previous subscription states restored."
                    )

            except Exception as restore_error:

                await db.rollback()

                print(
                    "\n⚠️ Subscription restore warning:"
                )

                print(
                    f"   {restore_error}"
                )
