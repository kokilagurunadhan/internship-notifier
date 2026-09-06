import asyncio

from sqlalchemy import text
from app.database.database import AsyncSessionLocal

async def main():
    async with AsyncSessionLocal() as db:

        result = await db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename='internships';
        """))

        print("\n================ INTERNSHIP INDEXES ================\n")

        for name, definition in result.fetchall():
            print(name)
            print(definition)
            print()

asyncio.run(main())