import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription


# ============================================================
# CONTROLLED PIPELINE TEST
# ============================================================

async def test_pipeline_with_controlled_job():

    print()
    print("=" * 70)
    print("CONTROLLED PIPELINE TEST")
    print("=" * 70)

    async with AsyncSessionLocal() as db:

        # ----------------------------------------------------
        # GET ACTIVE SUBSCRIPTION
        # ----------------------------------------------------

        result = await db.execute(
            select(Subscription)
            .where(
                Subscription.is_active == True
            )
            .limit(1)
        )

        subscription = result.scalar_one_or_none()

        if not subscription:

            print("No active subscription found.")
            return

        print(
            f"Subscription: "
            f"{subscription.user_email}"
        )

        print(
            f"Company: "
            f"{subscription.company}"
        )

        print(
            f"Domain: "
            f"{subscription.domain or 'Not specified'}"
        )

        # ----------------------------------------------------
        # CONTROLLED JOB
        # ----------------------------------------------------

        test_job = {

            "company": "microsoft",

            "company_name": "microsoft",

            "title": "Software Engineering Intern",

            "location": "Bangalore, India",

            "description": """
            Software engineering internship opportunity.

            Work with Python, REST APIs, backend services,
            databases and application development.

            Responsibilities include developing software,
            writing code, testing applications and working
            with engineering teams.
            """,

            "via": "Controlled Test",

            "source": "Controlled Test",

            "url": (
                "https://test.example.com/"
                "infosys-software-intern-unique-001"
            ),
        }

        print()
        print("=" * 70)
        print("CONTROLLED TEST JOB")
        print("=" * 70)

        print(
            f"Company : {test_job['company']}"
        )

        print(
            f"Title   : {test_job['title']}"
        )

        print(
            f"URL     : {test_job['url']}"
        )

        # ====================================================
        # STAGE 1 — STRICT INTERNSHIP FILTER
        # ====================================================

        print()
        print("=" * 70)
        print("1. STRICT INTERNSHIP FILTER")
        print("=" * 70)

        from app.services.internship_filter import (
            is_internship
        )

        internship_result = is_internship(
            test_job["title"],
            test_job["description"],
            ""
        )

        print(
            f"Internship detected: "
            f"{internship_result}"
        )

        if not internship_result:

            print("FAIL: Job rejected by internship filter.")
            return

        print("PASS: Job passed internship filter.")

        # ====================================================
        # STAGE 2 — COMPANY VERIFICATION
        # ====================================================

        print()
        print("=" * 70)
        print("2. COMPANY VERIFICATION")
        print("=" * 70)

        from app.services.company_verification import (
            verify_company
        )

        company_result = verify_company(
            test_job,
            subscription.company
        )

        print(
            f"Company verified: "
            f"{company_result}"
        )

        if not company_result:

            print("FAIL: Company verification failed.")
            return

        print("PASS: Company verification passed.")

        # ====================================================
        # STAGE 3 — KEYWORD + SEMANTIC RELEVANCE
        # ====================================================

        print()
        print("=" * 70)
        print("3. KEYWORD + SEMANTIC RELEVANCE")
        print("=" * 70)

        from app.services.relevance_engine import (
            calculate_relevance_score
        )

        result = calculate_relevance_score(

            job_title=test_job["title"],

            job_description=test_job["description"],

            user_domain=(
                subscription.domain
                or None
            ),
        )

        keyword_score = result["keyword_score"]

        semantic_score = result["semantic_score"]

        final_score = result["final_score"]

        conflict = result["conflict"]

        print(
            f"Keyword score  : {keyword_score}"
        )

        print(
            f"Semantic score : {semantic_score}"
        )

        print(
            f"Final score    : {final_score}"
        )

        print(
            f"Domain conflict: {conflict}"
        )

        # ====================================================
        # STAGE 4 — FINAL RELEVANCE THRESHOLD
        # ====================================================

        print()
        print("=" * 70)
        print("4. FINAL RELEVANCE THRESHOLD")
        print("=" * 70)

        MIN_RELEVANCE_SCORE = 50

        if (
            final_score >= MIN_RELEVANCE_SCORE
            and not conflict
        ):

            print(
                "PASS: Test job passed relevance."
            )

            print()
            print(
                "Production pipeline would:"
            )

            print(
                "  1. Save internship"
            )

            print(
                "  2. Check database uniqueness"
            )

            print(
                "  3. Create PENDING notification"
            )

            print(
                "  4. Group notification by email"
            )

            print(
                "  5. Send digest"
            )

        else:

            print(
                "FAIL: Test job did not pass relevance."
            )

            print()
            print(
                "Production pipeline would:"
            )

            print(
                "  1. Save job as history"
            )

            print(
                "  2. Mark as LOW_RELEVANCE"
            )

            print(
                "  3. Create NO notification"
            )

        # ====================================================
        # COMPLETE
        # ====================================================

        print()
        print("=" * 70)
        print("CONTROLLED PIPELINE TEST COMPLETED")
        print("=" * 70)


# ============================================================
# RUN TEST
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        test_pipeline_with_controlled_job()
    )
