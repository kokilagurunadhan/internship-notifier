import asyncio
from sqlalchemy import text
from app.database.database import AsyncSessionLocal


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT
                    id,
                    status,
                    retry_count,
                    next_retry_at,
                    error_message,
                    idempotency_key
                FROM notifications
                WHERE id = 25;
            """)
        )

        row = result.mappings().first()

        if row:
            print(dict(row))
        else:
            print("Notification 25 not found.")


if __name__ == "__main__":
    asyncio.run(main())