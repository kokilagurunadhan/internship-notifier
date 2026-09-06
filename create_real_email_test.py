import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification, NotificationStatus


async def main():

    async with AsyncSessionLocal() as db:

        # --------------------------------------------------------
        # GET AN EXISTING ACTIVE SUBSCRIPTION
        # --------------------------------------------------------

        result = await db.execute(
            select(Subscription)
            .where(Subscription.is_active == True)
            .limit(1)
        )

        subscription = result.scalar_one_or_none()

        if subscription is None:
            print("❌ No active subscription found.")
            print("Create a subscription first.")
            return

        # --------------------------------------------------------
        # GET LATEST INTERNSHIP
        # --------------------------------------------------------

        result = await db.execute(
            select(Internship)
            .order_by(Internship.id.desc())
            .limit(1)
        )

        internship = result.scalar_one_or_none()

        if internship is None:
            print("❌ No internship found.")
            return

        # --------------------------------------------------------
        # CREATE TEST NOTIFICATION
        # --------------------------------------------------------

        notification = Notification(
            subscription_id=subscription.id,
            user_email=subscription.user_email,
            internship_id=internship.id,
            status=NotificationStatus.PENDING,
            relevance_score=95.0,
        )

        db.add(notification)

        await db.commit()
        await db.refresh(notification)

        print()
        print("=" * 70)
        print("✅ TEST NOTIFICATION CREATED")
        print("=" * 70)

        print(f"📌 Notification ID : {notification.id}")
        print(f"📌 Subscription ID : {subscription.id}")
        print(f"📧 User Email      : {subscription.user_email}")
        print(f"🏢 Internship ID   : {internship.id}")
        print(f"🎯 Relevance Score : {notification.relevance_score}")
        print(f"📊 Status          : {notification.status}")

        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())