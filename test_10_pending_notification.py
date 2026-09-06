import asyncio

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription


TEST_EMAIL = "kokilasudha9363@gmail.com"
TEST_COMPANY = "Infosys"
TEST_DOMAIN = "software"


async def main():

    async with AsyncSessionLocal() as db:

        result = await db.execute(
            select(Subscription).where(
                Subscription.user_email == TEST_EMAIL,
                Subscription.company.ilike(TEST_COMPANY),
                Subscription.domain.ilike(TEST_DOMAIN),
                Subscription.is_active == True
            )
        )

        subscription = result.scalar_one_or_none()

        print()
        print("=" * 70)
        print("TEST 10 - SUBSCRIPTION CHECK")
        print("=" * 70)

        if subscription is None:

            print()
            print("❌ Subscription not found.")
            print()
            print("Creating test subscription...")

            subscription = Subscription(
                user_email=TEST_EMAIL,
                company=TEST_COMPANY,
                domain=TEST_DOMAIN,
                is_active=True
            )

            db.add(subscription)

            await db.commit()
            await db.refresh(subscription)

            print()
            print("✅ Test subscription created.")
            print(f"ID     : {subscription.id}")
            print(f"Email  : {subscription.user_email}")
            print(f"Company: {subscription.company}")
            print(f"Domain : {subscription.domain}")

        else:

            print()
            print("✅ Active subscription found.")
            print()
            print(f"ID     : {subscription.id}")
            print(f"Email  : {subscription.user_email}")
            print(f"Company: {subscription.company}")
            print(f"Domain : {subscription.domain}")
            print(f"Active : {subscription.is_active}")

        print()
        print("=" * 70)
        print("TEST 10 SUBSCRIPTION CHECK COMPLETED")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())