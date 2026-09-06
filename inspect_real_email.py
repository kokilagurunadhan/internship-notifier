import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
from app.models.historical_job import HistoricalJob

async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Notification)
            .where(Notification.user_email == "kokilasudha9363@gmail.com")
            .order_by(Notification.id)
        )

        notifications = result.scalars().all()

        print("\nREAL EMAIL NOTIFICATIONS:\n")

        if not notifications:
            print("None found.")

        for n in notifications:
            print(
                f"id={n.id} | "
                f"internship={n.internship_id} | "
                f"status={n.status} | "
                f"retry={n.retry_count}"
            )

asyncio.run(main())
