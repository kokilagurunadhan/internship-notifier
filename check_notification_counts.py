import asyncio

from sqlalchemy import select, func

# Import ALL models so SQLAlchemy can configure relationships
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.models.historical_job import HistoricalJob

from app.database.database import AsyncSessionLocal


async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(
                Notification.status,
                func.count(Notification.id)
            )
            .group_by(Notification.status)
        )

        rows = result.all()

        print("\nNotification counts:")

        if not rows:
            print("No notifications found.")

        for status, count in rows:
            print(f"{status}: {count}")


if __name__ == "__main__":
    asyncio.run(main())