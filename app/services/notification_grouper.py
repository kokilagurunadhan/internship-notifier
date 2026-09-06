from collections import defaultdict

from sqlalchemy import select

from app.database.database import AsyncSessionLocal
from app.models.internship import Internship
from app.models.subscription import Subscription


async def get_pending_internships_grouped_by_user():

    async with AsyncSessionLocal() as db:

        grouped = defaultdict(dict)

        result = await db.execute(
            select(Subscription).where(
                Subscription.is_active == True
            )
        )

        subscriptions = result.scalars().all()

        for subscription in subscriptions:

            email = (
                subscription.user_email or ""
            ).strip()

            company = (
                subscription.company or ""
            ).strip()

            if not email or not company:
                continue

            result = await db.execute(
                select(Internship).where(
                    Internship.company.ilike(company),
                    Internship.email_sent == False
                )
            )

            internships = result.scalars().all()

            for internship in internships:

                unique_key = (
                    f"{internship.company.lower().strip()}|"
                    f"{internship.title.lower().strip()}"
                )

                if unique_key not in grouped[email]:

                    grouped[email][unique_key] = internship

        return {
            email: list(internships.values())
            for email, internships in grouped.items()
        }