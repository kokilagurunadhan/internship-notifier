import asyncio

from sqlalchemy import delete, select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.notification import Notification
from app.models.internship import Internship


TEST_EMAILS = {
    "test@example.com",
    "notification-race-test@example.com",
    "claim-test@example.com",
}


async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Subscription).where(
                Subscription.user_email.in_(TEST_EMAILS)
            )
        )

        subscriptions = result.scalars().all()

        print("\n=== TEST SUBSCRIPTIONS TO DELETE ===\n")

        for subscription in subscriptions:
            print(
                f"id={subscription.id} | "
                f"user={subscription.user_email} | "
                f"company={subscription.company} | "
                f"domain={subscription.domain}"
            )

        if not subscriptions:
            print("No test subscriptions found.")
            return

        confirm = input(
            "\nType DELETE_TEST_DATA to continue: "
        )

        if confirm != "DELETE_TEST_DATA":
            print("Cleanup cancelled.")
            return

        await db.execute(
            delete(Subscription).where(
                Subscription.user_email.in_(TEST_EMAILS)
            )
        )

        await db.commit()

        print("\n? Test subscriptions deleted.")


if __name__ == "__main__":
    asyncio.run(main())
