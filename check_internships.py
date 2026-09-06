import asyncio

from sqlalchemy import text

from app.database.database import AsyncSessionLocal


async def check():
    async with AsyncSessionLocal() as db:

        result = await db.execute(
            text(
                """
                SELECT
                    id,
                    company,
                    title,
                    url,
                    relevance_score,
                    passed_filter,
                    status,
                    email_sent,
                    created_at
                FROM internships
                WHERE LOWER(company) = 'microsoft'
                ORDER BY created_at DESC
                LIMIT 20
                """
            )
        )

        rows = result.mappings().all()

        print("\n===== MICROSOFT INTERNSHIPS =====\n")

        if not rows:
            print("No Microsoft internships found.")
            return

        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    asyncio.run(check())