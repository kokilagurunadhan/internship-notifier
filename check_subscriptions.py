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
                    user_email,
                    company,
                    domain,
                    is_active,
                    created_at
                FROM subscriptions
                ORDER BY id DESC
                """
            )
        )

        rows = result.mappings().all()

        print("\n===== SUBSCRIPTIONS =====\n")

        if not rows:
            print("No subscriptions found.")
            return

        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    asyncio.run(check())