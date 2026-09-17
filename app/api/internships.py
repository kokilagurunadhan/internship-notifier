# ============================================================
# INTERNSHIP API
# File: app/api/internships.py
# ============================================================

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Query
from app.schemas.internship import (
    InternshipCreate,
    InternshipResponse,
    InternshipDismissRequest,
)

from app.services.internship_service import (
    get_all_internships,
    create_internship,
    save_internship,
)

from app.services.internship_search import (
    search_internships,
)

from app.database.database import get_db

from app.models.internship import Internship
from app.models.subscription import Subscription
from app.models.notification import Notification
from app.models.internship_dismissal import InternshipDismissal


router = APIRouter()


# ============================================================
# GET ALL INTERNSHIPS
# ============================================================

@router.get("/internships")
async def get_internships(
    company: str | None = None,
    location: str | None = None,
    user_email: str | None = None,
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------------------------------
    # BASE QUERY
    # --------------------------------------------------------

    query = (
        select(
            Internship,
            Notification.relevance_score,
        )
        .outerjoin(
            Notification,
            (
                Notification.internship_id == Internship.id
            )
            & (
                Notification.user_email == user_email
            ),
        )
        .order_by(
            Internship.id.desc()
        )
    )

    # --------------------------------------------------------
    # COMPANY FILTER
    # --------------------------------------------------------

    if company:

        query = query.where(
            Internship.company == company
        )

    # --------------------------------------------------------
    # LOCATION FILTER
    # --------------------------------------------------------

    if location:

        query = query.where(
            Internship.location == location
        )

    # --------------------------------------------------------
    # USER-SPECIFIC DISMISSAL FILTER
    #
    # Only apply this when a user email is supplied.
    #
    # The internship remains in the database.
    # It is simply hidden from this user's dashboard.
    # --------------------------------------------------------

    if user_email:

        dismissed_exists = select(
            InternshipDismissal.id
        ).where(
            InternshipDismissal.user_email == user_email,
            InternshipDismissal.internship_id == Internship.id,
        ).exists()

        query = query.where(
            ~dismissed_exists
        )

    # --------------------------------------------------------
    # EXECUTE
    # --------------------------------------------------------

    result = await db.execute(query)

    rows = result.all()

    # --------------------------------------------------------
    # BUILD RESPONSE
    # --------------------------------------------------------

    internships = []

    for internship, relevance_score in rows:

        data = {
            "id": internship.id,
            "company": internship.company,
            "title": internship.title,
            "location": internship.location,
            "url": internship.url,
            "description": internship.description,
            "source": internship.source,
            "via": internship.via,
            "relevance_score": (
                float(relevance_score)
                if relevance_score is not None
                else (
                    float(internship.relevance_score)
                    if internship.relevance_score is not None
                    else None
                )
            ),
            "email_sent": internship.email_sent,
            "created_at": internship.created_at,
            "last_seen_at": internship.last_seen_at,
        }

        internships.append(data)

    return internships
# ============================================================
# DISMISS INTERNSHIP FOR USER
# ============================================================

@router.post("/internships/{internship_id}/dismiss")
async def dismiss_internship(
    internship_id: int,
    request: InternshipDismissRequest,
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------------------------------
    # VERIFY INTERNSHIP EXISTS
    # --------------------------------------------------------

    result = await db.execute(
        select(Internship).where(
            Internship.id == internship_id
        )
    )

    internship = result.scalar_one_or_none()

    if internship is None:
        return {
            "success": False,
            "message": "Internship not found",
        }


    # --------------------------------------------------------
    # CHECK IF ALREADY DISMISSED
    # --------------------------------------------------------

    result = await db.execute(
        select(InternshipDismissal).where(
            InternshipDismissal.user_email == request.user_email,
            InternshipDismissal.internship_id == internship_id,
        )
    )

    existing = result.scalar_one_or_none()


    # --------------------------------------------------------
    # CREATE DISMISSAL
    # --------------------------------------------------------

    if existing is None:

        dismissal = InternshipDismissal(
            user_email=request.user_email,
            internship_id=internship_id,
        )

        db.add(dismissal)

        await db.commit()


    return {
        "success": True,
        "message": "Internship dismissed",
        "internship_id": internship_id,
    }
# ============================================================
# PUBLIC DASHBOARD
# ============================================================

@router.get("/dashboard")

# ============================================================
# PUBLIC DASHBOARD
# ============================================================

@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
):

    # --------------------------------------------------------
    # TOTAL JOBS CRAWLED
    # --------------------------------------------------------

    result = await db.execute(
        select(
            func.count(Internship.id)
        )
    )

    total_jobs = result.scalar() or 0


    # --------------------------------------------------------
    # ACTIVE SUBSCRIBERS
    # --------------------------------------------------------

    result = await db.execute(
        select(
            func.count(
                func.distinct(
                    Subscription.user_email
                )
            )
        )
        .where(
            Subscription.is_active.is_(True)
        )
    )

    active_subscribers = result.scalar() or 0


    # --------------------------------------------------------
    # NOTIFICATIONS SENT
    # --------------------------------------------------------

    result = await db.execute(
        select(
            func.count(Notification.id)
        )
        .where(
            Notification.status == "SENT"
        )
    )

    notifications_sent = result.scalar() or 0


    # --------------------------------------------------------
    # RECENT RELEVANT INTERNSHIPS
    #
    # IMPORTANT:
    # Relevance is USER-SPECIFIC.
    # Therefore use Notification.relevance_score
    # instead of Internship.relevance_score.
    # --------------------------------------------------------

    result = await db.execute(
        select(
            Internship,
            Notification.relevance_score
        )
        .join(
            Notification,
            Notification.internship_id == Internship.id
        )
        .where(
            Internship.passed_filter.is_(True),
            Notification.relevance_score.isnot(None),
        )
        .order_by(
            Internship.id.desc()
        )
        .limit(50)
    )

    rows = result.all()


    jobs = []

    for job, relevance_score in rows:

        jobs.append({

            "id": job.id,

            "title": job.title,

            "company": job.company,

            "location": job.location,

            "url": job.url,

            "description": job.description,

            "source": job.source,

            "via": job.via,

            # Use the actual user-specific relevance score
            "relevance_score":
                float(relevance_score),

            "email_sent":
                job.email_sent,

        })


    return {

        "total_jobs":
            total_jobs,

        "active_subscribers":
            active_subscribers,

        "notifications_sent":
            notifications_sent,

        "internships":
            jobs,

    }



# ============================================================
# GET COMPANIES
# ============================================================

@router.get("/companies")
async def get_companies(
    db: AsyncSession = Depends(get_db),
):

    result = await db.execute(
        select(
            Internship.company
        )
        .where(
            Internship.company.isnot(None)
        )
        .distinct()
        .order_by(
            Internship.company
        )
    )

    companies = result.scalars().all()

    return companies


# ============================================================
# CREATE INTERNSHIP
# ============================================================

@router.post(
    "/internships",
    response_model=InternshipResponse,
)
async def add_internship(
    internship: InternshipCreate,
    db: AsyncSession = Depends(get_db),
):

    return await create_internship(
        db=db,
        internship=internship,
    )


# ============================================================
# SEARCH INTERNSHIPS
# ============================================================

@router.get("/search-internships")
async def search(
    company: str = Query(
    ...,
    min_length=1,
    max_length=200,
),
):

    return await search_internships(
        company
    )


# ============================================================
# SEARCH AND SAVE
# ============================================================

@router.post("/search-and-save")
async def search_and_save(
    company: str = Query(
    ...,
    min_length=1,
    max_length=200,
),
    db: AsyncSession = Depends(get_db),
):

    results = await search_internships(
        company
    )

    saved = []

    for internship in results:

        result = await save_internship(
            db=db,
            job_data=internship,
        )

        saved.append(result)

    await db.commit()

    return saved