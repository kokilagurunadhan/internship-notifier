import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification


async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Subscription)
            .where(Subscription.id == 1)
        )

        subscription = result.scalar_one_or_none()

        if not subscription:
            print("❌ Subscription ID 1 not found.")
            return

        subscription.company = "Microsoft"
        subscription.domain = "software"
        subscription.is_active = True

        await db.commit()

        print("✅ Subscription updated")
        print(f"🏢 Company: {subscription.company}")
        print(f"🎯 Domain: {subscription.domain}")
        print(f"📧 Email: {subscription.user_email}")


if __name__ == "__main__":
    asyncio.run(main())