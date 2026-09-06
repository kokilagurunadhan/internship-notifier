from fastapi import APIRouter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.database.database import get_db
from app.models.notification import Notification


router = APIRouter()


# ============================================================
# GET ALL NOTIFICATIONS
# ============================================================

@router.get("/notifications")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(Notification)
        .order_by(
            Notification.created_at.desc()
        )
    )

    notifications = result.scalars().all()

    return notifications