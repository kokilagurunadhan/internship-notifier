from typing import List
import asyncio
import os

from fastapi import (
    APIRouter,
    Depends,
    Path,
    HTTPException,
    status
)


from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.models.subscription import Subscription

from app.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse
)

from app.services.email_service import (
    send_internship_email
)

from app.services.subscription_service import (
    get_subscriptions_by_company
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"]
)


# ============================================================
# CREATE SUBSCRIPTION
# ============================================================

@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED
)

# ============================================================
# CREATE SUBSCRIPTION
# ============================================================

@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_subscription(
    subscription: SubscriptionCreate,
    db: AsyncSession = Depends(get_db)
):
    # --------------------------------------------------------
    # CHECK ONLY THE EXACT COMBINATION:
    # email + company + domain
    # --------------------------------------------------------
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_email == subscription.user_email,
            Subscription.company == subscription.company,
            Subscription.domain == subscription.domain,
        )
    )

    existing_subscription = result.scalar_one_or_none()

    # --------------------------------------------------------
    # EXACT COMBINATION ALREADY EXISTS
    # --------------------------------------------------------
    if existing_subscription:

        # Active exact duplicate → reject
        if (
            existing_subscription.is_active
            and existing_subscription.status == "ACTIVE"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An active subscription already exists "
                    "for this email, company and domain."
                )
            )

        # Cancelled/inactive exact subscription → reactivate
        existing_subscription.is_active = True
        existing_subscription.status = "ACTIVE"

        await db.commit()
        await db.refresh(existing_subscription)

        return existing_subscription

    # --------------------------------------------------------
    # DIFFERENT COMPANY / DOMAIN COMBINATION → NEW ROW
    # --------------------------------------------------------
    new_subscription = Subscription(
        user_email=subscription.user_email,
        company=subscription.company,
        domain=subscription.domain,
        is_active=True,
        status="ACTIVE",
    )

    db.add(new_subscription)

    try:
        await db.commit()
        await db.refresh(new_subscription)

    except IntegrityError:
        await db.rollback()

        # Another request may have created the exact same
        # email + company + domain concurrently.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An active subscription already exists "
                "for this email, company and domain."
            )
        )

    except Exception:
        await db.rollback()
        raise

    return new_subscription



# ============================================================
# GET ALL SUBSCRIPTIONS
# ============================================================

@router.get(
    "",
    response_model=List[SubscriptionResponse]
)
async def get_subscriptions(

    db: AsyncSession = Depends(get_db)

):

    result = await db.execute(

    select(Subscription)
    .order_by(
        Subscription.created_at.desc()
    )

)

    subscriptions = result.scalars().all()

    return subscriptions


# ============================================================
# GET SUBSCRIPTIONS FOR COMPANY
# ============================================================

@router.get(
    "/company/{company}",
    response_model=List[SubscriptionResponse]
)
async def get_company_subscriptions(

    company: str = Path(
    ...,
    min_length=1,
    max_length=200,
),

    db: AsyncSession = Depends(get_db)

):

    return await get_subscriptions_by_company(

        db,

        company

    )
# ============================================================
# PAUSE SUBSCRIPTION
# ============================================================

@router.patch(
    "/{subscription_id}/pause",
    response_model=SubscriptionResponse
)
async def pause_subscription(

    subscription_id: int = Path(
        ...,
        gt=0,
    ),

    db: AsyncSession = Depends(get_db)

):

    result = await db.execute(

        select(Subscription)
        .where(
            Subscription.id == subscription_id
        )

    )

    subscription = result.scalar_one_or_none()

    # --------------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------------

    if not subscription:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=(
                f"Subscription with ID "
                f"{subscription_id} not found"
            )

        )

    # --------------------------------------------------------
    # PAUSE
    # --------------------------------------------------------

    subscription.is_active = False
    subscription.status = "PAUSED"

    try:

        await db.commit()

        await db.refresh(subscription)

    except Exception:

        await db.rollback()

        raise

    return subscription


# ============================================================
# RESUME SUBSCRIPTION
# ============================================================

@router.patch(
    "/{subscription_id}/resume",
    response_model=SubscriptionResponse
)
async def resume_subscription(

    subscription_id: int = Path(
        ...,
        gt=0,
    ),

    db: AsyncSession = Depends(get_db)

):

    result = await db.execute(

        select(Subscription)
        .where(
            Subscription.id == subscription_id
        )

    )

    subscription = result.scalar_one_or_none()

    # --------------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------------

    if not subscription:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=(
                f"Subscription with ID "
                f"{subscription_id} not found"
            )

        )

    # --------------------------------------------------------
    # RESUME
    # --------------------------------------------------------

    subscription.is_active = True
    subscription.status = "ACTIVE"

    try:

        await db.commit()

        await db.refresh(subscription)

    except Exception:

        await db.rollback()

        raise

    return subscription


# ============================================================
# CANCEL SUBSCRIPTION
# SOFT DELETE
# ============================================================

@router.delete(
    "/{subscription_id}",
    response_model=SubscriptionResponse
)
async def delete_subscription(

    subscription_id: int = Path(
    ...,
    gt=0,
),

    db: AsyncSession = Depends(get_db)

):

    result = await db.execute(

        select(Subscription)
        .where(
            Subscription.id == subscription_id
        )

    )

    subscription = result.scalar_one_or_none()


    # --------------------------------------------------------
    # NOT FOUND
    # --------------------------------------------------------

    if not subscription:

        raise HTTPException(

            status_code=status.HTTP_404_NOT_FOUND,

            detail=(
                f"Subscription with ID "
                f"{subscription_id} not found"
            )

        )


    # --------------------------------------------------------
    # SOFT DELETE
    # --------------------------------------------------------

    subscription.is_active = False
    subscription.status = "CANCELLED"

    try:

        await db.commit()

        await db.refresh(subscription)

    except Exception:

        await db.rollback()

        raise

    return subscription


# ============================================================
# TEST EMAIL
# ============================================================

@router.post(
    "/test-email"
)
async def test_email():

    test_email = os.getenv("TEST_EMAIL")

    if not test_email:

        raise HTTPException(

            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

            detail=(
                "TEST_EMAIL environment variable "
                "is not configured."
            )

        )


    result = await asyncio.to_thread(

        send_internship_email,

        recipient_email=test_email,

        company=os.getenv(
            "TEST_EMAIL_COMPANY",
            "Microsoft"
        ),

        title=os.getenv(
            "TEST_EMAIL_TITLE",
            "Software Engineering Intern"
        ),

        location=os.getenv(
            "TEST_EMAIL_LOCATION",
            "Bangalore"
        ),

        url=os.getenv(
            "TEST_EMAIL_URL",
            "https://example.com/microsoft-internship"
        )

    )


    if result is None:

        raise HTTPException(

            status_code=status.HTTP_502_BAD_GATEWAY,

            detail="Email provider failed to send the test email."

        )


    return {

        "status":
            "success",

        "detail":
            result

    }