import asyncio
import logging
import re

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.services.sources.serpapi import search_jobs
from app.services.internship_filter import filter_internships
from app.services.company_verification import verify_company
from app.services.relevance_engine import calculate_relevance_score
from app.services.url_utils import canonicalize_job_url
from app.database.database import AsyncSessionLocal
from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification
logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

MIN_RELEVANCE_SCORE = 50

# Existing jobs are eligible only when the DB record
# is not older than 7 days.
MAX_EXISTING_JOB_AGE_DAYS = 7

# A completely new URL can enter the global internship
# catalog if the source posting is <=45 days old.
MAX_NEW_JOB_POSTING_AGE_DAYS = 45


# ============================================================
# TIME HELPERS
# ============================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_domain(
    domain: str | None,
) -> str | None:
    if not domain:
        return None

    domain = domain.strip().lower()

    if domain.startswith("http://"):
        domain = domain[7:]

    if domain.startswith("https://"):
        domain = domain[8:]

    domain = domain.split("/")[0]
    domain = domain.split("?")[0]

    return domain or None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


# ============================================================
# JOB URL EXTRACTION
# ============================================================

def get_job_url(
    job: Dict[str, Any],
) -> str | None:
    """
    Extract the best available URL from a SerpAPI job object.

    Priority:
        1. apply_options[*].link
        2. link
        3. url
    """

    apply_options = job.get("apply_options")

    if isinstance(apply_options, list):
        for option in apply_options:
            if not isinstance(option, dict):
                continue

            link = option.get("link")

            if link:
                return str(link).strip()

    link = job.get("link")

    if link:
        return str(link).strip()

    url = job.get("url")

    if url:
        return str(url).strip()

    return None


# ============================================================
# SUBSCRIPTION HELPERS
# ============================================================

def get_subscription_email(
    subscription: Subscription,
) -> str | None:
    """
    Current schema uses user_email.
    """

    email = getattr(
        subscription,
        "user_email",
        None,
    )

    if email:
        return email.strip().lower()

    return None


def subscription_key(
    subscription: Subscription,
) -> Tuple[str, str, str | None]:

    email = (
        get_subscription_email(subscription)
        or ""
    )

    company = normalize_text(
        getattr(
            subscription,
            "company",
            None,
        )
    )

    domain = normalize_domain(
        getattr(
            subscription,
            "domain",
            None,
        )
    )

    return email, company, domain


def deduplicate_subscriptions(
    subscriptions: List[Subscription],
) -> List[Subscription]:

    seen: Set[
        Tuple[str, str, str | None]
    ] = set()

    result: List[Subscription] = []

    for subscription in subscriptions:
        key = subscription_key(subscription)

        if key in seen:
            continue

        seen.add(key)
        result.append(subscription)

    return result


# ============================================================
# EXISTING JOB AGE
# ============================================================

def is_job_within_7_days(
    internship: Internship,
) -> bool:

    created_at = internship.created_at

    if created_at is None:
        return False

    if created_at.tzinfo is None:
        created_at = created_at.replace(
            tzinfo=timezone.utc
        )

    age = utc_now() - created_at

    return (
        age
        <= timedelta(
            days=MAX_EXISTING_JOB_AGE_DAYS
        )
    )


# ============================================================
# SERPAPI POSTING AGE
# ============================================================

def get_job_posting_age_days(
    job: Dict[str, Any],
) -> float | None:
    """
    Extract posting age from SerpAPI data.

    Handles:
        posting_age_days = 10
        "10 days ago"
        "1 day ago"
        "3 weeks ago"
        "1 month ago"
        "today"
        "yesterday"
    """

    # --------------------------------------------------------
    # Numeric fields
    # --------------------------------------------------------

    numeric_fields = (
        "posting_age_days",
        "age_days",
        "days_ago",
    )

    for field in numeric_fields:
        value = job.get(field)

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                pass

    # --------------------------------------------------------
    # Text fields
    # --------------------------------------------------------

    text_fields = (
        "posting_age",
        "posted",
        "posted_at",
        "date_posted",
        "detected_extensions",
    )

    for field in text_fields:

        value = job.get(field)

        if isinstance(value, dict):
            nested_values = value.values()
        else:
            nested_values = [value]

        for nested_value in nested_values:

            if nested_value is None:
                continue

            text = (
                str(nested_value)
                .strip()
                .lower()
            )

            # ------------------------------------------------
            # Days
            # ------------------------------------------------

            match = re.search(
                r"(\d+(?:\.\d+)?)\s*(day|days)\s*ago",
                text,
            )

            if match:
                return float(match.group(1))

            # ------------------------------------------------
            # Weeks
            # ------------------------------------------------

            match = re.search(
                r"(\d+(?:\.\d+)?)\s*(week|weeks)\s*ago",
                text,
            )

            if match:
                return float(match.group(1)) * 7

            # ------------------------------------------------
            # Months
            # ------------------------------------------------

            match = re.search(
                r"(\d+(?:\.\d+)?)\s*(month|months)\s*ago",
                text,
            )

            if match:
                return float(match.group(1)) * 30

            # ------------------------------------------------
            # Today
            # ------------------------------------------------

            if (
                "today" in text
                or "just posted" in text
            ):
                return 0.0

            # ------------------------------------------------
            # Yesterday
            # ------------------------------------------------

            if "yesterday" in text:
                return 1.0

            # ------------------------------------------------
            # Generic fallback
            #
            # Example:
            # "10 days"
            # ------------------------------------------------

            match = re.search(
                r"(\d+(?:\.\d+)?)\s*days?",
                text,
            )

            if match:
                return float(match.group(1))

    return None


def is_new_job_within_45_days(
    job: Dict[str, Any],
) -> bool:

    posting_age_days = (
        get_job_posting_age_days(job)
    )

    if posting_age_days is None:
        return False

    return (
        posting_age_days
        <= MAX_NEW_JOB_POSTING_AGE_DAYS
    )


# ============================================================
# ACTIVE SUBSCRIPTIONS
# ============================================================

async def get_active_subscriptions(
    db: AsyncSession,
) -> List[Subscription]:

    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.is_active.is_(True)
        )
    )

    subscriptions = list(
        result.scalars().all()
    )

    return deduplicate_subscriptions(
        subscriptions
    )


# ============================================================
# GROUP SUBSCRIPTIONS
# ============================================================

def group_subscriptions(
    subscriptions: List[Subscription],
) -> Dict[
    Tuple[str, str | None],
    List[Subscription],
]:
    """
    Group subscriptions by company + domain.

    One SerpAPI search is performed for
    each group.
    """

    groups: Dict[
        Tuple[str, str | None],
        List[Subscription],
    ] = {}

    for subscription in subscriptions:

        company = normalize_text(
            getattr(
                subscription,
                "company",
                None,
            )
        )

        domain = normalize_domain(
            getattr(
                subscription,
                "domain",
                None,
            )
        )

        key = (
            company,
            domain,
        )

        groups.setdefault(
            key,
            [],
        ).append(subscription)

    return groups


# ============================================================
# USER-SPECIFIC DUPLICATE CHECK
# ============================================================

async def notification_exists(
    db: AsyncSession,
    user_email: str,
    internship_id: int,
) -> bool:

    result = await db.execute(
        select(Notification.id)
        .where(
            Notification.user_email == user_email,
            Notification.internship_id == internship_id,
            Notification.status.in_(
                [
                    "PENDING",
                    "PROCESSING",
                    "SENT",
                ]
            ),
        )
        .limit(1)
    )

    return (
        result.scalar_one_or_none()
        is not None
    )


# ============================================================
# BATCH NOTIFICATION LOOKUP
# ============================================================

async def get_existing_notification_pairs(
    db: AsyncSession,
    pairs: Set[Tuple[str, int]],
) -> Set[Tuple[str, int]]:
    """
    Batch-load existing user + internship notification
    pairs.

    This replaces one notification query per user/job
    during normal grouped pipeline execution.

    The database unique constraint remains the final
    concurrency safety net.
    """

    if not pairs:
        return set()

    user_emails = {
        email
        for email, _ in pairs
    }

    internship_ids = {
        internship_id
        for _, internship_id in pairs
    }

    result = await db.execute(
        select(
            Notification.user_email,
            Notification.internship_id,
        )
        .where(
            Notification.user_email.in_(
                user_emails
            ),
            Notification.internship_id.in_(
                internship_ids
            ),
            Notification.status.in_(
                [
                    "PENDING",
                    "PROCESSING",
                    "SENT",
                ]
            ),
        )
    )

    return {
        (
            row[0],
            row[1],
        )
        for row in result.all()
    }


# ============================================================
# CREATE PENDING NOTIFICATION
# ============================================================

async def create_pending_notification(
    db: AsyncSession,
    subscription: Subscription,
    internship: Internship,
    relevance_score: float,
    skip_existing_check: bool = False,
) -> Notification | None:

    if relevance_score < MIN_RELEVANCE_SCORE:
        return None

    user_email = get_subscription_email(
        subscription
    )

    if not user_email:
        return None

    # --------------------------------------------------------
    # User-specific history check
    #
    # Normal callers perform this check here.
    #
    # Batch pipeline callers may skip the redundant SELECT
    # because they already performed a batch duplicate lookup.
    #
    # The unique DB constraint still protects concurrent inserts.
    # --------------------------------------------------------

    if not skip_existing_check:

        if await notification_exists(
            db,
            user_email,
            internship.id,
        ):
            return None

    notification = Notification(
        subscription_id=subscription.id,
        user_email=user_email,
        internship_id=internship.id,
        relevance_score=float(
            relevance_score
        ),
        status="PENDING",
    )

    try:

        async with db.begin_nested():

            db.add(notification)

            await db.flush()

        logger.info(
    "PENDING notification created",
    extra={
        "internship_id": internship.id,
        "relevance_score": round(float(relevance_score), 2),
    },
)

        return notification

    except IntegrityError:

        logger.warning(
    "Notification insert conflict",
    extra={
        "internship_id": internship.id,
    },
)

        return None


# ============================================================
# GLOBAL INTERNSHIP LOOKUP
# ============================================================

async def get_existing_internship(
    db: AsyncSession,
    canonical_url: str,
) -> Internship | None:

    result = await db.execute(
        select(Internship)
        .where(
            Internship.url == canonical_url
        )
        .limit(1)
    )

    return result.scalar_one_or_none()


# ============================================================
# BATCH GLOBAL INTERNSHIP LOOKUP
# ============================================================

async def get_existing_internships_by_urls(
    db: AsyncSession,
    canonical_urls: Set[str],
) -> Dict[str, Internship]:
    """
    Batch-load existing internships for all canonical URLs
    returned by one SerpAPI search group.

    Returns:
        {
            canonical_url: Internship(...)
        }
    """

    if not canonical_urls:
        return {}

    result = await db.execute(
        select(Internship)
        .where(
            Internship.url.in_(canonical_urls)
        )
    )

    internships = result.scalars().all()

    return {
        internship.url: internship
        for internship in internships
    }


# ============================================================
# SAVE GLOBAL INTERNSHIP
# ============================================================

async def save_relevant_internship(
    db: AsyncSession,
    job: Dict[str, Any],
    canonical_url: str,
    relevance_score: float,
    existing: Internship | None = None,
) -> Tuple[Internship, bool]:

    # --------------------------------------------------------
    # Reuse already batch-loaded internship when available.
    #
    # If existing=None, this function performs the traditional
    # lookup. This preserves standalone callers/tests.
    # --------------------------------------------------------

    if existing is None:

        existing = (
            await get_existing_internship(
                db,
                canonical_url,
            )
        )

    if existing:

        existing.last_seen_at = utc_now()

        return existing, False

    internship = Internship(
        company=str(
            job.get("company")
            or job.get("company_name")
            or ""
        ).strip(),

        title=str(
            job.get("title")
            or ""
        ).strip(),

        location=job.get(
            "location"
        ),

        url=canonical_url,

        description=job.get(
            "description"
        ),

        source=job.get(
            "source"
        ),

        via=job.get(
            "via"
        ),

        # Discovery metadata only.
        relevance_score=float(
            relevance_score
        ),

        passed_filter=True,

        status="RELEVANT",

        email_sent=False,

        created_at=utc_now(),

        last_seen_at=utc_now(),
    )

    try:

        async with db.begin_nested():

            db.add(internship)

            await db.flush()

        logger.info(
    "New global internship saved",
    extra={
        "internship_id": internship.id,
    },
)

        return internship, True

    except IntegrityError:

        # Another concurrent worker may have inserted
        # the same canonical URL.
        #
        # Re-query is intentionally retained as the
        # concurrency safety fallback.

        existing = (
            await get_existing_internship(
                db,
                canonical_url,
            )
        )

        if existing is None:
            raise

        existing.last_seen_at = utc_now()

        return existing, False


# ============================================================
# SAVE LOW-RELEVANCE HISTORY
# ============================================================

async def save_low_relevance_history(
    db: AsyncSession,
    job: Dict[str, Any],
    canonical_url: str,
    relevance_score: float,
    existing: Internship | None = None,
) -> Internship:

    if existing is None:

        existing = (
            await get_existing_internship(
                db,
                canonical_url,
            )
        )

    if existing:

        existing.last_seen_at = utc_now()

        return existing

    internship = Internship(
        company=str(
            job.get("company")
            or job.get("company_name")
            or ""
        ).strip(),

        title=str(
            job.get("title")
            or ""
        ).strip(),

        location=job.get(
            "location"
        ),

        url=canonical_url,

        description=job.get(
            "description"
        ),

        source=job.get(
            "source"
        ),

        via=job.get(
            "via"
        ),

        relevance_score=float(
            relevance_score
        ),

        passed_filter=False,

        status="LOW_RELEVANCE",

        email_sent=False,

        created_at=utc_now(),

        last_seen_at=utc_now(),
    )

    try:

        async with db.begin_nested():

            db.add(internship)

            await db.flush()

        logger.info(
    "Low-relevance internship saved as history",
    extra={
        "internship_id": internship.id,
        "relevance_score": round(float(relevance_score), 2),
    },
)

        return internship

    except IntegrityError:

        existing = (
            await get_existing_internship(
                db,
                canonical_url,
            )
        )

        if existing is None:
            raise

        existing.last_seen_at = utc_now()

        return existing


# ============================================================
# USER-SPECIFIC RELEVANCE
# ============================================================

async def calculate_user_relevance(
    job: Dict[str, Any],
    subscription: Subscription,
) -> Tuple[float, bool]:

    user_email = get_subscription_email(
        subscription
    )

    user_domain = normalize_domain(
        getattr(
            subscription,
            "domain",
            None,
        )
    )

    title = str(
        job.get("title") or ""
    )

    description = str(
        job.get("description") or ""
    )

    logger.debug(
    "Calculating user-specific relevance",
    extra={
        "domain": user_domain or None,
    },
)

    # ========================================================
    # RELEVANCE ENGINE
    # ========================================================

    relevance_result = calculate_relevance_score(
        title,
        description,
        user_domain or None,
    )

    # ========================================================
    # EXTRACT AUTHORITATIVE USER SCORE
    # ========================================================

    score = float(
        relevance_result.get(
            "final_score",
            0.0,
        )
    )

    # ========================================================
    # EXTRACT DOMAIN CONFLICT
    # ========================================================

    conflict = bool(
        relevance_result.get(
            "conflict",
            False,
        )
    )

    # ========================================================
    # LOG SCORING DETAILS
    # ========================================================

    logger.debug(
    "Relevance scoring completed",
    extra={
        "keyword_score": round(
            float(relevance_result.get("keyword_score", 0.0)),
            2,
        ),
        "semantic_score": round(
            float(relevance_result.get("semantic_score", 0.0)),
            2,
        ),
        "final_score": round(float(score), 2),
        "conflict": conflict,
    }
)

    return score, conflict


# ============================================================
# PROCESS ONE JOB FOR ONE USER
# ============================================================

async def process_job_for_user(
    db: AsyncSession,
    job: Dict[str, Any],
    subscription: Subscription,
    existing_internship: Internship | None = None,
    duplicate_notification: bool | None = None,
) -> Dict[str, Any]:

    result = {
        "processed": False,
        "new_internship": False,
        "existing_internship": False,
        "notification_created": False,
        "duplicate_notification": False,
        "low_relevance": False,
        "domain_conflict": False,
        "stale": False,
        "rejected_posting_age": False,
    }

    # ========================================================
    # STEP 1 — CANONICAL URL
    # ========================================================

    raw_url = get_job_url(job)

    if not raw_url:
        return result

    canonical_url = canonicalize_job_url(
        raw_url
    )

    if not canonical_url:
        return result

    # ========================================================
    # STEP 2 — GLOBAL URL LOOKUP
    #
    # Standalone callers perform the lookup here.
    #
    # Batch pipeline callers pass existing_internship,
    # avoiding another SELECT.
    # ========================================================

    if existing_internship is None:

        existing_internship = (
            await get_existing_internship(
                db,
                canonical_url,
            )
        )

    # ========================================================
    # NEW URL
    # ========================================================

    if existing_internship is None:

        logger.info(
    "New internship URL detected",
)

        # ----------------------------------------------------
        # NEW JOB MUST PASS SOURCE POSTING AGE
        # ----------------------------------------------------

        posting_age_days = (
            get_job_posting_age_days(job)
        )

        if (
            posting_age_days is None
            or posting_age_days
            > MAX_NEW_JOB_POSTING_AGE_DAYS
        ):

            result[
                "rejected_posting_age"
            ] = True

            logger.info(
    "New internship rejected due to posting age",
    extra={
        "posting_age_days": posting_age_days,
        "max_allowed_days": MAX_NEW_JOB_POSTING_AGE_DAYS,
    },
)

            return result

        logger.info(
    "New internship accepted",
    extra={
        "posting_age_days": posting_age_days,
        "max_allowed_days": MAX_NEW_JOB_POSTING_AGE_DAYS,
    },
)

        # ----------------------------------------------------
        # SAVE GLOBAL INTERNSHIP FIRST
        # ----------------------------------------------------

        internship, was_created = (
            await save_relevant_internship(
                db=db,
                job=job,
                canonical_url=canonical_url,
                relevance_score=0.0,
                existing=None,
            )
        )

        result[
            "new_internship"
        ] = was_created

        # The URL could have been inserted by a concurrent
        # worker after our batch lookup.
        #
        # In that case save_relevant_internship() returns
        # the canonical existing row.

        if not was_created:
            result[
                "existing_internship"
            ] = True

            if not is_job_within_7_days(
                internship
            ):

                result["stale"] = True

                logger.info(
    "Existing internship is outside eligibility window",
    extra={
        "max_age_days": MAX_EXISTING_JOB_AGE_DAYS,
        "internship_id": internship.id,
    },
)

                return result

        # ----------------------------------------------------
        # USER EMAIL
        # ----------------------------------------------------

        user_email = (
            get_subscription_email(
                subscription
            )
        )

        if not user_email:
            return result

        # ----------------------------------------------------
        # USER DUPLICATE CHECK
        # ----------------------------------------------------

        if duplicate_notification is None:

            duplicate_notification = (
                await notification_exists(
                    db,
                    user_email,
                    internship.id,
                )
            )

        if duplicate_notification:

            result[
                "duplicate_notification"
            ] = True

            logger.debug(
    "User already has a notification for internship",
    extra={
        "internship_id": internship.id,
    },
)

            return result

        # ----------------------------------------------------
        # USER-SPECIFIC RELEVANCE
        # ----------------------------------------------------

        score, conflict = (
            await calculate_user_relevance(
                job,
                subscription,
            )
        )

        if conflict:

            result[
                "domain_conflict"
            ] = True

            logger.info(
    "User domain conflict",
)

            return result

        if score < MIN_RELEVANCE_SCORE:

            result[
                "low_relevance"
            ] = True

            logger.info(
        "Internship rejected for user due to low relevance",
        extra={
            "relevance_score": round(float(score), 2),
            "min_relevance_score": MIN_RELEVANCE_SCORE,
        },
    )


            return result

        

        # ----------------------------------------------------
        # CREATE PENDING NOTIFICATION
        # ----------------------------------------------------

        notification = (
            await create_pending_notification(
                db=db,
                subscription=subscription,
                internship=internship,
                relevance_score=score,
                skip_existing_check=(
                    duplicate_notification
                    is not None
                ),
            )
        )

        if notification:

            result[
                "notification_created"
            ] = True

            result[
                "processed"
            ] = True

        return result

    # ========================================================
    # EXISTING URL
    # ========================================================

    result[
        "existing_internship"
    ] = True

    logger.debug(
    "Existing internship found",
    extra={
        "internship_id": existing_internship.id,
    },
)

    # --------------------------------------------------------
    # EXISTING JOB MUST BE <=7 DAYS OLD
    # --------------------------------------------------------

    if not is_job_within_7_days(
        existing_internship
    ):

        result["stale"] = True

        logger.info(
    "Existing internship is outside eligibility window",
    extra={
        "internship_id": existing_internship.id,
        "max_age_days": MAX_EXISTING_JOB_AGE_DAYS,
    },
)

        return result

    existing_internship.last_seen_at = (
        utc_now()
    )

    # --------------------------------------------------------
    # USER EMAIL
    # --------------------------------------------------------

    user_email = (
        get_subscription_email(
            subscription
        )
    )

    if not user_email:
        return result

    # --------------------------------------------------------
    # USER DUPLICATE CHECK FIRST
    # --------------------------------------------------------

    if duplicate_notification is None:

        duplicate_notification = (
            await notification_exists(
                db,
                user_email,
                existing_internship.id,
            )
        )

    if duplicate_notification:

        result[
            "duplicate_notification"
        ] = True

        logger.debug(
    "Duplicate notification prevented",
    extra={
        "internship_id": existing_internship.id,
    },
)

        return result

    # --------------------------------------------------------
    # USER-SPECIFIC RELEVANCE
    # --------------------------------------------------------

    score, conflict = (
        await calculate_user_relevance(
            job,
            subscription,
        )
    )

    if conflict:

        result[
            "domain_conflict"
        ] = True

        logger.info(
    "User relevance conflict",
)

        return result

    if score < MIN_RELEVANCE_SCORE:

        result[
            "low_relevance"
        ] = True

        logger.info(
    "Internship rejected for user due to low relevance",
    extra={
        "relevance_score": round(float(score), 2),
        "min_relevance_score": MIN_RELEVANCE_SCORE,
    },
)

        return result

    logger.info(
    "User passed relevance threshold",
    extra={
        "relevance_score": round(float(score), 2),
        "min_relevance_score": MIN_RELEVANCE_SCORE,
    },
)

    # --------------------------------------------------------
    # CREATE PENDING NOTIFICATION
    # --------------------------------------------------------

    notification = (
        await create_pending_notification(
            db=db,
            subscription=subscription,
            internship=existing_internship,
            relevance_score=score,
            skip_existing_check=(
                duplicate_notification
                is not None
            ),
        )
    )

    if notification:

        result[
            "notification_created"
        ] = True

        result[
            "processed"
        ] = True

    return result


# ============================================================
# PROCESS ONE SUBSCRIPTION GROUP
# ============================================================

async def process_subscription(
    subscription: Subscription,
    subscription_group:
        List[Subscription] | None = None,
) -> Dict[str, Any]:

    if subscription_group is None:
        subscription_group = [
            subscription
        ]

    company = normalize_text(
        getattr(
            subscription,
            "company",
            None,
        )
    )

    domain = normalize_domain(
        getattr(
            subscription,
            "domain",
            None,
        )
    )

    stats = {
        "subscriptions":
            len(subscription_group),

        "jobs_found": 0,

        "jobs_filtered": 0,

        "jobs_verified": 0,

        "new_internships": 0,

        "existing_internships": 0,

        "notifications_created": 0,

        "duplicates": 0,

        "low_relevance": 0,

        "conflicts": 0,

        "stale": 0,

        "rejected_posting_age": 0,
    }

    # ========================================================
    # ONE DATABASE SESSION FOR THE GROUP
    # ========================================================

    async with AsyncSessionLocal() as db:

        # ====================================================
        # ONE GROUPED SERPAPI SEARCH
        # ====================================================

        

        logger.info(
    "Searching SerpAPI",
    extra={
        "company": company,
    },
)

        jobs = await asyncio.to_thread(
            search_jobs,
            company=company,
            domain=domain or None,
        )

        if not jobs:
            jobs = []

        stats[
            "jobs_found"
        ] = len(jobs)

        logger.info(
    "SerpAPI search completed",
    extra={
        "jobs_returned": len(jobs),
    },
)

        # ====================================================
        # URL DEDUPLICATION
        # ====================================================

        seen_urls: Set[str] = set()

        unique_jobs: List[
            Dict[str, Any]
        ] = []

        for job in jobs:

            raw_url = get_job_url(job)

            if not raw_url:
                continue

            canonical_url = (
                canonicalize_job_url(
                    raw_url
                )
            )

            if not canonical_url:
                continue

            if canonical_url in seen_urls:
                continue

            seen_urls.add(
                canonical_url
            )

            unique_jobs.append(job)

        # ====================================================
        # STRICT INTERNSHIP FILTER
        # ====================================================

        filtered_jobs = filter_internships(
            unique_jobs
        )

        if not filtered_jobs:
            filtered_jobs = []

        stats[
            "jobs_filtered"
        ] = len(filtered_jobs)

        logger.info(
    "Strict internship filter completed",
    extra={
        "jobs_passed": len(filtered_jobs),
    },
)

        # ====================================================
        # COMPANY VERIFICATION
        # ====================================================

        verified_jobs = []

        for job in filtered_jobs:

            verified = verify_company(
                job,
                company,
            )

            if verified:
                verified_jobs.append(job)

        stats[
            "jobs_verified"
        ] = len(verified_jobs)

        logger.info(
    "Company verification completed",
    extra={
        "jobs_verified": len(verified_jobs),
    },
)

        # ====================================================
        # BATCH GLOBAL INTERNSHIP LOOKUP
        #
        # IMPORTANT:
        #
        # This is the main Task #2 optimization.
        #
        # Previously every user/job combination could execute
        # a separate SELECT on internships.
        #
        # Now all URLs for this SerpAPI group are loaded once.
        # ====================================================

        canonical_url_by_job_id: Dict[
            int,
            str,
        ] = {}

        canonical_urls: Set[str] = set()

        for index, job in enumerate(
            verified_jobs
        ):

            raw_url = get_job_url(job)

            if not raw_url:
                continue

            canonical_url = (
                canonicalize_job_url(
                    raw_url
                )
            )

            if not canonical_url:
                continue

            canonical_url_by_job_id[
                index
            ] = canonical_url

            canonical_urls.add(
                canonical_url
            )

        existing_internships = (
            await get_existing_internships_by_urls(
                db,
                canonical_urls,
            )
        )

        logger.info(
    "Batch internship lookup completed",
    extra={
        "existing_internships": len(existing_internships),
        "canonical_urls": len(canonical_urls),
    },
)

        # ====================================================
        # PRE-CREATE NEW INTERNSHIP ROWS
        #
        # The locked order remains:
        #
        # posting-age validation
        # → save global internship
        # → user evaluation
        #
        # We prepare/reuse the global row once per URL,
        # rather than once per user.
        # ====================================================

        internship_by_url: Dict[
            str,
            Internship,
        ] = {}

        for index, job in enumerate(
            verified_jobs
        ):

            canonical_url = (
                canonical_url_by_job_id.get(index)
            )

            if not canonical_url:
                continue

            existing = existing_internships.get(
                canonical_url
            )

            if existing is not None:

                internship_by_url[
                    canonical_url
                ] = existing

                continue

            # ------------------------------------------------
            # NEW URL — SOURCE POSTING AGE
            # ------------------------------------------------

            posting_age_days = (
                get_job_posting_age_days(job)
            )

            if (
                posting_age_days is None
                or posting_age_days
                > MAX_NEW_JOB_POSTING_AGE_DAYS
            ):
                continue

            internship, was_created = (
                await save_relevant_internship(
                    db=db,
                    job=job,
                    canonical_url=canonical_url,
                    relevance_score=0.0,
                    existing=None,
                )
            )

            internship_by_url[
                canonical_url
            ] = internship

            if was_created:
                stats[
                    "new_internships"
                ] += 1

        # ====================================================
        # BATCH USER NOTIFICATION LOOKUP
        #
        # We need the internship IDs first.
        # Only jobs that have a valid global internship
        # participate.
        # ====================================================

        notification_pairs: Set[
            Tuple[str, int]
        ] = set()

        for index, job in enumerate(
            verified_jobs
        ):

            canonical_url = (
                canonical_url_by_job_id.get(index)
            )

            if not canonical_url:
                continue

            internship = (
                internship_by_url.get(
                    canonical_url
                )
            )

            if internship is None:
                continue

            for subscriber in subscription_group:

                user_email = (
                    get_subscription_email(
                        subscriber
                    )
                )

                if not user_email:
                    continue

                notification_pairs.add(
                    (
                        user_email,
                        internship.id,
                    )
                )

        existing_notification_pairs = (
            await get_existing_notification_pairs(
                db,
                notification_pairs,
            )
        )

        logger.info(
    "Batch notification lookup completed",
    extra={
        "existing_notification_pairs": len(
            existing_notification_pairs
        ),
    },
)

        # ====================================================
        # USER EVALUATION
        # ====================================================

        for index, job in enumerate(
            verified_jobs
        ):

            canonical_url = (
                canonical_url_by_job_id.get(index)
            )

            if not canonical_url:
                continue

            internship = (
                internship_by_url.get(
                    canonical_url
                )
            )

            # ------------------------------------------------
            # New URL rejected because posting age >45 days
            # ------------------------------------------------

            if internship is None:

                posting_age_days = (
                    get_job_posting_age_days(job)
                )

                if (
                    posting_age_days is None
                    or posting_age_days
                    > MAX_NEW_JOB_POSTING_AGE_DAYS
                ):

                    for subscriber in subscription_group:

                        stats[
                            "rejected_posting_age"
                        ] += 1

                    logger.info(
    "Job skipped for group due to posting age",
    extra={
        "max_allowed_days": MAX_NEW_JOB_POSTING_AGE_DAYS,
        "posting_age_days": posting_age_days,
    },
)

                continue

            # ------------------------------------------------
            # Existing internship count
            #
            # Count it once per job, not once per user.
            # This keeps stats semantically aligned with
            # global internship records.
            # ------------------------------------------------

            if (
                canonical_url
                in existing_internships
            ):
                stats[
                    "existing_internships"
                ] += 1

                if not is_job_within_7_days(
                    internship
                ):
                    # All users will hit stale logic below,
                    # but global stats should not repeatedly
                    # count the same internship.
                    pass

            # ------------------------------------------------
            # Existing URL stale check before users
            # ------------------------------------------------

            if (
                canonical_url
                in existing_internships
                and not is_job_within_7_days(
                    internship
                )
            ):

                stats[
                    "stale"
                ] += len(subscription_group)

                logger.info(
    "Existing internship is stale",
    extra={
        "internship_id": internship.id,
        "max_age_days": MAX_EXISTING_JOB_AGE_DAYS,
    },
)

                continue

            internship.last_seen_at = (
                utc_now()
            )

            # ------------------------------------------------
            # Process each active subscriber
            # ------------------------------------------------

            for subscriber in subscription_group:

                user_email = (
                    get_subscription_email(
                        subscriber
                    )
                )

                pair = None

                if user_email:

                    pair = (
                        user_email,
                        internship.id,
                    )

                duplicate = (
                    pair in existing_notification_pairs
                    if pair is not None
                    else False
                )

                result = (
                    await process_job_for_user(
                        db=db,
                        job=job,
                        subscription=subscriber,
                        existing_internship=internship,
                        duplicate_notification=duplicate,
                    )
                )

                if result[
                    "notification_created"
                ]:
                    stats[
                        "notifications_created"
                    ] += 1

                if result[
                    "duplicates"
                    if "duplicates" in result
                    else "duplicate_notification"
                ]:
                    stats[
                        "duplicates"
                    ] += 1

                if result[
                    "low_relevance"
                ]:
                    stats[
                        "low_relevance"
                    ] += 1

                if result[
                    "domain_conflict"
                ]:
                    stats[
                        "conflicts"
                    ] += 1

                # Standalone stale logic is normally handled
                # above for the group. Keep this for defensive
                # consistency.
                if result[
                    "stale"
                ]:
                    stats[
                        "stale"
                    ] += 1

                if result[
                    "rejected_posting_age"
                ]:
                    stats[
                        "rejected_posting_age"
                    ] += 1

                # process_job_for_user() marks newly created
                # global rows, but those are already counted
                # once above in the batch preparation phase.
                #
                # Therefore do not increment new_internships
                # here.

            # ------------------------------------------------
            # COMMIT AFTER ALL USERS FOR THIS JOB
            # ------------------------------------------------

            await db.commit()

    return stats


# ============================================================
# PROCESS ALL ACTIVE SUBSCRIPTIONS
# ============================================================

async def process_all_active_subscriptions() -> Dict[str, Any]:

    totals = {
        "subscriptions": 0,
        "groups": 0,
        "jobs_found": 0,
        "jobs_filtered": 0,
        "jobs_verified": 0,
        "new_internships": 0,
        "existing_internships": 0,
        "notifications_created": 0,
        "duplicates": 0,
        "low_relevance": 0,
        "conflicts": 0,
        "stale": 0,
        "rejected_posting_age": 0,
    }

    # ========================================================
    # LOAD ACTIVE SUBSCRIPTIONS
    # ========================================================

    async with AsyncSessionLocal() as db:

        subscriptions = (
            await get_active_subscriptions(
                db
            )
        )

    totals[
        "subscriptions"
    ] = len(subscriptions)

    if not subscriptions:

        logger.info(
    "No active subscriptions found"
)

        return totals

    # ========================================================
    # GROUP
    # ========================================================

    groups = group_subscriptions(
        subscriptions
    )

    totals[
        "groups"
    ] = len(groups)

    print("")

    print(
        f"📦 Active subscriptions: "
        f"{len(subscriptions)}"
    )

    print(
        f"📦 Search groups: "
        f"{len(groups)}"
    )

    # ========================================================
    # PROCESS EACH GROUP
    # ========================================================

    for _, group in groups.items():

        if not group:
            continue

        try:

            stats = await process_subscription(
                subscription=group[0],
                subscription_group=group,
            )

            for key in totals:

                if key in stats:
                    totals[key] += stats[key]

        except asyncio.CancelledError:

            raise

        except Exception as error:

            logger.exception(
                "❌ Subscription group failed. "
                "Continuing with remaining groups. "
                "Company=%s | Domain=%s | Error=%s",
                getattr(
                    group[0],
                    "company",
                    None,
                ),
                getattr(
                    group[0],
                    "domain",
                    None,
                ),
                error,
            )

        continue

    # ========================================================
    # FINAL PIPELINE STATS
    # ========================================================

    print("")

    print(
        "📊 Pipeline totals:"
    )

    print(
        f"   Subscriptions: "
        f"{totals['subscriptions']}"
    )

    print(
        f"   Groups: "
        f"{totals['groups']}"
    )

    print(
        f"   Jobs found: "
        f"{totals['jobs_found']}"
    )

    print(
        f"   Jobs filtered: "
        f"{totals['jobs_filtered']}"
    )

    print(
        f"   Jobs verified: "
        f"{totals['jobs_verified']}"
    )

    print(
        f"   New internships: "
        f"{totals['new_internships']}"
    )

    print(
        f"   Existing internships: "
        f"{totals['existing_internships']}"
    )

    print(
        f"   Notifications created: "
        f"{totals['notifications_created']}"
    )

    print(
        f"   Duplicates blocked: "
        f"{totals['duplicates']}"
    )

    print(
        f"   Low relevance: "
        f"{totals['low_relevance']}"
    )

    print(
        f"   Conflicts: "
        f"{totals['conflicts']}"
    )

    print(
        f"   Stale: "
        f"{totals['stale']}"
    )

    print(
        f"   Rejected posting age: "
        f"{totals['rejected_posting_age']}"
    )

    print(
        "📨 Emails are NOT sent by the pipeline."
    )

    print(
        "📨 Notification dispatcher handles delivery."
    )

    return totals


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    async def main():

        result = (
            await process_all_active_subscriptions()
        )

        print("")

        print(
            "FINAL RESULT:"
        )

        print(result)

    asyncio.run(main())