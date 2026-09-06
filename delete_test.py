import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.internship import Internship


async def main():

    async with AsyncSessionLocal() as db:

        try:

            result = await db.execute(
                select(Internship).where(
                    Internship.company == "Test Company"
                )
            )

            test_internships = result.scalars().all()

            print()
            print("=" * 70)
            print("DELETE TEST INTERNSHIPS")
            print("=" * 70)

            print(
                f"Found {len(test_internships)} "
                f"test internship(s)."
            )

            for internship in test_internships:

                print(
                    f"Deleting: "
                    f"{internship.company} | "
                    f"{internship.title}"
                )

                await db.delete(internship)

            await db.commit()

            print()
            print("Test internship(s) deleted successfully!")

        except Exception as e:

            await db.rollback()

            print()
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())