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


router = APIRouter()


# ============================================================
# GET ALL INTERNSHIPS
# ============================================================

@router.get("/internships")
async def get_internships(
    company: str | None = None,
    location: str | None = None,
):

    internships = await get_all_internships(
        company=company,
        location=location,
    )

    return internships

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