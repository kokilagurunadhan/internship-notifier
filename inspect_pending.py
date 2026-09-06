import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.notification import Notification
from app.models.subscription import Subscription
from app.models.internship import Internship

from app.models.historical_job import HistoricalJob
async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification)
            .where(Notification.status == "PENDING")
            .order_by(Notification.id)
        )

        notifications = result.scalars().all()

        print("\nPENDING notifications:\n")

        for n in notifications:

            print(
                f"id={n.id} | "
                f"user={n.user_email} | "
                f"internship={n.internship_id} | "
                f"retry_count={n.retry_count} | "
                f"next_retry_at={n.next_retry_at}"
            )

asyncio.run(main())
