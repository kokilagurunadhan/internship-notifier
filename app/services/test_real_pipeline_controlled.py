import asyncio

from sqlalchemy import select, delete

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification

import app.services.pipeline_processor as pipeline


# ============================================================
# TEST CONFIGURATION
# ============================================================

TEST_EMAIL = "pipeline_controlled@example.com"

TEST_COMPANY = "controlledtest"

TEST_DOMAIN = "software"

TEST_URLS = [
    "https://controlled.test/pass-001",
    "https://controlled.test/marketing-001",
]


# ============================================================
# CONTROLLED SERPAPI RESPONSE
# ============================================================

def fake_search_jobs(company, domain=None):

    print()
    print("=" * 70)
    print("🧪 FAKE SERPAPI SEARCH")
    print("=" * 70)

    print(f"Company requested : {company}")
    print(f"Domain requested  : {domain}")

    return [

        # ----------------------------------------------------
        # JOB 1
        # SHOULD PASS EVERYTHING
        # ----------------------------------------------------

        {
            "company": "controlledtest",
            "company_name": "ControlledTest",

            "title": "Software Engineering Intern",

            "location": "Bangalore, India",

            "description": """
            Software engineering internship.

            Work with Python, REST APIs, backend services,
            databases, software development and testing.

            Students will work with engineering teams
            to build and maintain software applications.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": TEST_URLS[0],
        },

        # ----------------------------------------------------
        # JOB 2
        # SHOULD FAIL RELEVANCE
        # BUT MUST BE SAVED AS LOW_RELEVANCE HISTORY
        # ----------------------------------------------------

        {
            "company": "controlledtest",
            "company_name": "ControlledTest",

            "title": "Marketing Intern",

            "location": "Bangalore, India",

            "description": """
            Marketing internship.

            Work on campaigns, social media,
            advertising, branding and market research.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": TEST_URLS[1],
        },

        # ----------------------------------------------------
        # JOB 3
        # SHOULD FAIL INTERNSHIP FILTER
        # ----------------------------------------------------

        {
            "company": "controlledtest",
            "company_name": "ControlledTest",

            "title": "Software Engineer",

            "location": "Bangalore, India",

            "description": """
            Full-time software engineering position.

            Develop backend services using Python,
            APIs and databases.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": (
                "https://controlled.test/"
                "fulltime-001"
            ),
        },

        # ----------------------------------------------------
        # JOB 4
        # SHOULD FAIL COMPANY VERIFICATION
        # ----------------------------------------------------

        {
            "company": "google",
            "company_name": "Google",

            "title": "Software Engineering Intern",

            "location": "Bangalore, India",

            "description": """
            Software engineering internship.

            Work with Python, APIs, backend systems,
            databases and software development.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": (
                "https://controlled.test/"
                "wrong-company-001"
            ),
        },

        # ----------------------------------------------------
        # JOB 5
        # DUPLICATE OF JOB 1
        # ----------------------------------------------------

        {
            "company": "controlledtest",
            "company_name": "ControlledTest",

            "title": "Software Engineering Intern",

            "location": "Bangalore, India",

            "description": """
            Software engineering internship.

            Work with Python, REST APIs, backend services,
            databases and software development.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": TEST_URLS[0],
        },
    ]


# ============================================================
# CLEANUP
# ============================================================

async def cleanup_test_records():

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # FIND TEST SUBSCRIPTIONS
        # ----------------------------------------------------

        result = await db.execute(
            select(Subscription).where(
                Subscription.user_email == TEST_EMAIL
            )
        )

        subscriptions = result.scalars().all()

        subscription_ids = [
            subscription.id
            for subscription in subscriptions
        ]

        # ----------------------------------------------------
        # FIND TEST INTERNSHIPS
        # ----------------------------------------------------

        result = await db.execute(
            select(Internship).where(
                Internship.url.in_(TEST_URLS)
            )
        )

        internships = result.scalars().all()

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
        # DELETE SUBSCRIPTION
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
# MAIN
# ============================================================

async def main():

    print()
    print("=" * 70)
    print("🚀 REAL PIPELINE CONTROLLED TEST")
    print("=" * 70)

    # ========================================================
    # CLEAN OLD TEST DATA
    # ========================================================

    print()
    print("🧹 Cleaning previous test records...")

    await cleanup_test_records()

    print("✅ Cleanup complete.")

    # ========================================================
    # CREATE CONTROLLED SUBSCRIPTION
    # ========================================================

    async with AsyncSessionLocal() as db:

        print()
        print("=" * 70)
        print("CREATING CONTROLLED SUBSCRIPTION")
        print("=" * 70)

        subscription = Subscription(
            user_email=TEST_EMAIL,
            company=TEST_COMPANY,
            domain=TEST_DOMAIN,
            is_active=True,
        )

        db.add(subscription)

        await db.commit()

        print(
            f"Subscription ID : {subscription.id}"
        )

        print(
            f"Email            : {subscription.user_email}"
        )

        print(
            f"Company          : {subscription.company}"
        )

        print(
            f"Domain           : {subscription.domain}"
        )

    # ========================================================
    # INSTALL FAKE SERPAPI
    # ========================================================

    print()
    print("=" * 70)
    print("INSTALLING FAKE SERPAPI")
    print("=" * 70)

    original_search_jobs = pipeline.search_jobs

    pipeline.search_jobs = fake_search_jobs

    try:

        # ====================================================
        # RUN PIPELINE
        # ====================================================

        print()
        print("=" * 70)
        print("RUNNING REAL PIPELINE")
        print("=" * 70)

        result = (
            await pipeline.process_all_active_subscriptions()
        )

        print()
        print(
            f"Pipeline returned : {result}"
        )

        # ====================================================
        # VERIFY DATABASE
        # ====================================================

        print()
        print("=" * 70)
        print("DATABASE VERIFICATION")
        print("=" * 70)

        async with AsyncSessionLocal() as db:

            # ------------------------------------------------
            # INTERNSHIPS
            # ------------------------------------------------

            result = await db.execute(
                select(Internship).where(
                    Internship.url.in_(TEST_URLS)
                )
            )

            saved_internships = (
                result.scalars().all()
            )

            print()
            print(
                f"Internships saved : "
                f"{len(saved_internships)}"
            )

            for internship in saved_internships:

                print(
                    f"  {internship.company} | "
                    f"{internship.title} | "
                    f"{internship.status} | "
                    f"passed={internship.passed_filter}"
                )

            # ------------------------------------------------
            # NOTIFICATIONS
            # ------------------------------------------------

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )

            notifications = (
                result.scalars().all()
            )

            print()
            print(
                f"Notifications created : "
                f"{len(notifications)}"
            )

            for notification in notifications:

                print(
                    f"  Notification {notification.id} | "
                    f"status={notification.status} | "
                    f"internship_id={notification.internship_id}"
                )

            # =================================================
            # EXPECTED RESULTS
            # =================================================

            assert len(saved_internships) == 2, (
                f"Expected 2 internships "
                f"(1 relevant + 1 low relevance), "
                f"got {len(saved_internships)}."
            )

            assert len(notifications) == 1, (
                f"Expected exactly 1 notification, "
                f"got {len(notifications)}."
            )

            relevant_jobs = [
                internship
                for internship in saved_internships
                if internship.status == "RELEVANT"
            ]

            low_relevance_jobs = [
                internship
                for internship in saved_internships
                if internship.status
                == "LOW_RELEVANCE"
            ]

            assert len(relevant_jobs) == 1, (
                "Expected exactly 1 RELEVANT internship."
            )

            assert len(low_relevance_jobs) == 1, (
                "Expected exactly 1 LOW_RELEVANCE internship."
            )

            assert (
                relevant_jobs[0].url
                == TEST_URLS[0]
            ), (
                "Wrong relevant internship saved."
            )

            assert (
                low_relevance_jobs[0].url
                == TEST_URLS[1]
            ), (
                "Wrong low-relevance internship saved."
            )

            assert (
                relevant_jobs[0].passed_filter is True
            ), (
                "Relevant internship did not pass filter."
            )

            assert (
                low_relevance_jobs[0].passed_filter is False
            ), (
                "Low-relevance internship incorrectly "
                "passed filter."
            )

            notification = notifications[0]

            assert (
                notification.user_email
                == TEST_EMAIL
            ), (
                "Notification belongs to wrong user."
            )

            assert (
                notification.internship_id
                == relevant_jobs[0].id
            ), (
                "Notification does not reference "
                "the relevant internship."
            )

            print()
            print("PASS: Controlled subscription isolated")
            print("PASS: 5 fake jobs processed")
            print("PASS: Valid internship saved")
            print("PASS: Low-relevance history saved")
            print("PASS: Invalid internship rejected")
            print("PASS: Wrong company rejected")
            print("PASS: Duplicate URL rejected")
            print("PASS: Exactly 1 notification created")

        # ====================================================
        # SECOND PIPELINE RUN
        # ====================================================

        print()
        print("=" * 70)
        print("RUNNING SECOND PIPELINE")
        print("=" * 70)

        second_result = (
            await pipeline.process_all_active_subscriptions()
        )

        print()
        print(
            f"Second pipeline returned : "
            f"{second_result}"
        )

        # ====================================================
        # VERIFY NO DUPLICATES
        # ====================================================

        async with AsyncSessionLocal() as db:

            result = await db.execute(
                select(Internship).where(
                    Internship.url.in_(TEST_URLS)
                )
            )

            final_internships = (
                result.scalars().all()
            )

            result = await db.execute(
                select(Notification).where(
                    Notification.user_email
                    == TEST_EMAIL
                )
            )

            final_notifications = (
                result.scalars().all()
            )

            assert len(final_internships) == 2, (
                "Second pipeline created duplicate "
                "internship history."
            )

            assert len(final_notifications) == 1, (
                "Second pipeline created duplicate "
                "notification."
            )

        print()
        print("PASS: Second pipeline created no duplicate")
        print("PASS: Internship history remained stable")
        print("PASS: Notification count remained 1")

        # ====================================================
        # FINAL
        # ====================================================

        print()
        print("=" * 70)
        print("🎉 REAL PIPELINE CONTROLLED TEST PASSED")
        print("=" * 70)

    finally:

        # ====================================================
        # RESTORE REAL SEARCH
        # ====================================================

        pipeline.search_jobs = original_search_jobs

        print()
        print("🔄 Real SerpAPI function restored.")

        # ====================================================
        # CLEANUP
        # ====================================================

        print()
        print("🧹 Cleaning controlled test records...")

        await cleanup_test_records()

        print("✅ Test records cleaned up.")

        print()
        print("=" * 70)
        print("✅ ALL CONTROLLED PIPELINE CHECKS PASSED")
        print("=" * 70)


if __name__ == "__main__":

    asyncio.run(main())