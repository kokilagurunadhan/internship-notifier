import asyncio

from sqlalchemy import text

from app.database.database import AsyncSessionLocal


async def main():

    print("=" * 70)
    print("🔍 NOTIFICATION DATABASE CONSTRAINT TEST")
    print("=" * 70)

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            text("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'notifications'
                ORDER BY indexname;
            """)
        )

        rows = result.fetchall()

        print()
        print(
            "================ NOTIFICATION INDEXES ================"
        )
        print()

        for name, definition in rows:

            print(name)
            print(definition)
            print()

    print("=" * 70)


if __name__ == "__main__":

    asyncio.run(main())