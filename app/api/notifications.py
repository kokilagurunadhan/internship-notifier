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

@router.get("/notifications")
async def get_notifications(
    user_email: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if not user_email:
        return []

    user_email = user_email.strip().lower()

    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_email == user_email
        )
        .order_by(
            Notification.created_at.desc()
        )
    )

    notifications = result.scalars().all()

    return notifications