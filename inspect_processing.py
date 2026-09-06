import asyncio

from sqlalchemy import select

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.models.historical_job import HistoricalJob

from app.database.database import AsyncSessionLocal


async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification)
            .where(
                Notification.status == "PROCESSING"
            )
            .order_by(
                Notification.processing_started_at
            )
        )

        notifications = result.scalars().all()

        print("\nPROCESSING notifications:\n")

        for n in notifications:

            print(
                f"id={n.id} | "
                f"user={n.user_email} | "
                f"internship={n.internship_id} | "
                f"processing_started_at={n.processing_started_at} | "
                f"retry_count={n.retry_count} | "
                f"next_retry_at={n.next_retry_at}"
            )


if __name__ == "__main__":
    asyncio.run(main())
