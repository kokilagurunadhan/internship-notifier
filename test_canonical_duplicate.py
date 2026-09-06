import asyncio

from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal
from app.models.internship import Internship
from app.services.internship_service import save_internship


TEST_TITLE = "Canonical Duplicate Test Internship"


async def main():
    url_1 = (
        "https://www.example.com/jobs/123/"
        "?utm_source=linkedin&utm_campaign=test"
    )

    url_2 = "https://example.com/jobs/123"

    async with AsyncSessionLocal() as db:
        try:
            await db.execute(
                delete(Internship).where(
                    Internship.title == TEST_TITLE
                )
            )
            await db.commit()

            internship_1, created_1 = await save_internship(
                db=db,
                job_data={
                    "company": "Canonical Test Company",
                    "title": TEST_TITLE,
                    "location": "Remote",
                    "url": url_1,
                    "description": "Testing canonical URL duplicate handling.",
                    "source": "test",
                    "via": "canonical-test",
                    "relevance_score": 80.0,
                    "passed_filter": True,
                    "status": "NEW",
                },
            )

            await db.commit()

            internship_2, created_2 = await save_internship(
                db=db,
                job_data={
                    "company": "Canonical Test Company",
                    "title": TEST_TITLE,
                    "location": "Remote",
                    "url": url_2,
                    "description": "Testing canonical URL duplicate handling.",
                    "source": "test",
                    "via": "canonical-test",
                    "relevance_score": 80.0,
                    "passed_filter": True,
                    "status": "NEW",
                },
            )

            await db.commit()

            result = await db.execute(
                select(Internship).where(
                    Internship.title == TEST_TITLE
                )
            )

            records = result.scalars().all()

            first_url_saved = internship_1 is not None
            canonical_urls_match = (
                internship_1.url == internship_2.url
            )
            second_url_blocked = (
                created_1 is True and created_2 is False
            )
            only_one_record = len(records) == 1

            print("")
            print("CANONICAL URL DUPLICATE TEST")
            print("=" * 50)

            print(
                f"First URL saved          : "
                f"{'PASS' if first_url_saved else 'FAIL'}"
            )

            print(
                f"Canonical URLs match     : "
                f"{'PASS' if canonical_urls_match else 'FAIL'}"
            )

            print(
                f"Second URL blocked       : "
                f"{'PASS' if second_url_blocked else 'FAIL'}"
            )

            print(
                f"Only 1 DB record exists  : "
                f"{'PASS' if only_one_record else 'FAIL'}"
            )

            print("")

            if not all(
                [
                    first_url_saved,
                    canonical_urls_match,
                    second_url_blocked,
                    only_one_record,
                ]
            ):
                raise AssertionError(
                    "Canonical URL duplicate test failed."
                )

            print("✅ CANONICAL URL DUPLICATE TEST PASSED")

        finally:
            await db.execute(
                delete(Internship).where(
                    Internship.title == TEST_TITLE
                )
            )
            await db.commit()


if __name__ == "__main__":
    asyncio.run(main())