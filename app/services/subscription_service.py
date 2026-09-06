from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import Subscription


# ============================================================
# GET SUBSCRIPTIONS BY COMPANY
# ============================================================

async def get_subscriptions_by_company(
    db: AsyncSession,
    company: str
):

    result = await db.execute(

        select(Subscription)
        .where(
            Subscription.company.ilike(company)
        )
        .where(
            Subscription.is_active == True
        )
    )

    return result.scalars().all()
