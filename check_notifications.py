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
                    internship_id,
                    status,
                    retry_count,
                    relevance_score,
                    idempotency_key,
                    error_message,
                    sent_at
                FROM notifications
                ORDER BY id DESC
                LIMIT 20
                """
            )
        )

        rows = result.mappings().all()

        if not rows:
            print("No notifications found.")
            return

        print("\n===== NOTIFICATIONS =====\n")

        for row in rows:
            print(dict(row))


if __name__ == "__main__":
    asyncio.run(check())