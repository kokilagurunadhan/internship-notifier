# ============================================================
# INTERNSHIP SERVICE
# File: app/services/internship_service.py
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Set, Tuple
import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import AsyncSessionLocal

from app.models.internship import Internship
from app.models.subscription import Subscription
from app.models.notification import Notification

from app.services.url_utils import canonicalize_job_url


# ============================================================
# LOGGER & CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)

NOTIFICATION_WINDOW_DAYS = 7
MIN_RELEVANCE_SCORE = 50


# ============================================================
# UTC HELPERS
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(value: datetime) -> datetime:

    if value is None:
        return _utc_now()

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


# ============================================================
# NOTIFICATION WINDOW
# ============================================================

def _is_within_notification_window(
    internship: Internship,
    now: datetime,
) -> bool:

    if not internship.created_at:
        return False

    created_at = _ensure_utc(
        internship.created_at
    )

    cutoff = (
        now
        - timedelta(
            days=NOTIFICATION_WINDOW_DAYS
        )
    )

    return created_at >= cutoff

# ============================================================
# 45-DAY INTERNSHIP RETENTION
# ============================================================

RETENTION_DAYS = 45


async def cleanup_old_internships() -> int:
    """
    Delete internships that have not been seen
    for more than RETENTION_DAYS.

    Related notifications are removed automatically
    by the database ON DELETE CASCADE constraint.
    """

    now = _utc_now()

    cutoff = (
        now
        - timedelta(
            days=RETENTION_DAYS
        )
    )

    async with AsyncSessionLocal() as db:

        try:

            result = await db.execute(
                select(Internship).where(
                    Internship.last_seen_at < cutoff
                )
            )

            old_internships = (
                result.scalars().all()
            )

            deleted_count = len(
                old_internships
            )

            for internship in old_internships:
                await db.delete(
                    internship
                )

            await db.commit()

            logger.info(
                "🧹 45-day retention cleanup: "
                "%d old internship(s) deleted.",
                deleted_count,
            )

            return deleted_count

        except Exception:

            await db.rollback()

            logger.exception(
                "❌ Failed to clean up old internships."
            )

            raise


# ============================================================
# GET ALL INTERNSHIPS
# ============================================================

async def get_all_internships(
    company: str | None = None,
    location: str | None = None,
) -> List[Internship]:

    async with AsyncSessionLocal() as db:

        query = (
            select(Internship)
            .order_by(
                Internship.id.desc()
            )
        )

        if company:

            query = query.where(
                Internship.company == company
            )

        if location:

            query = query.where(
                Internship.location == location
            )

        result = await db.execute(
            query
        )

        return result.scalars().all()


# ============================================================
# CREATE INTERNSHIP
# ============================================================

async def create_internship(
    internship_data: Any,
) -> Internship:

    async with AsyncSessionLocal() as db:

        try:

            # ------------------------------------------------
            # Convert Pydantic model to dictionary
            # ------------------------------------------------

            if hasattr(
                internship_data,
                "model_dump"
            ):

                data = (
                    internship_data.model_dump()
                )

            elif hasattr(
                internship_data,
                "dict"
            ):

                data = (
                    internship_data.dict()
                )

            else:

                data = dict(
                    internship_data
                )

            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            raw_url = data.get(
                "url"
            )

            if not raw_url:

                raise ValueError(
                    "Internship URL is required."
                )

            canonical_url = (
                canonicalize_job_url(
                    raw_url
                )
            )

            if not canonical_url:

                raise ValueError(
                    "Invalid internship URL."
                )

            data["url"] = canonical_url

            # ------------------------------------------------
            # Defaults
            # ------------------------------------------------

            relevance_score = float(
                data.get(
                    "relevance_score",
                    0
                )
                or 0
            )

            passed_filter = (
                relevance_score
                >= MIN_RELEVANCE_SCORE
            )

            data.setdefault(
                "relevance_score",
                relevance_score
            )

            data.setdefault(
                "passed_filter",
                passed_filter
            )

            data.setdefault(
                "status",
                (
                    "RELEVANT"
                    if passed_filter
                    else "LOW_RELEVANCE"
                )
            )

            data.setdefault(
                "email_sent",
                False
            )

            now = _utc_now()

            data.setdefault(
                "created_at",
                now
            )

            data.setdefault(
                "last_seen_at",
                now
            )

            # ------------------------------------------------
            # Check URL duplicate
            # ------------------------------------------------

            result = await db.execute(
                select(
                    Internship
                )
                .where(
                    Internship.url
                    == canonical_url
                )
                .limit(1)
            )

            existing = (
                result.scalar_one_or_none()
            )

            if existing:

                existing.last_seen_at = now

                await db.commit()

                await db.refresh(
                    existing
                )

                return existing

            # ------------------------------------------------
            # Create internship
            # ------------------------------------------------

            internship = Internship(
                **data
            )

            db.add(
                internship
            )

            await db.commit()

            await db.refresh(
                internship
            )

            logger.info(
                "🆕 Internship created: %s",
                canonical_url
            )

            return internship

        except Exception:

            await db.rollback()

            logger.exception(
                "Failed to create internship."
            )

            raise


# ============================================================
# GLOBAL URL DUPLICATE CHECK
# ============================================================

async def internship_url_exists(
    db: AsyncSession,
    url: str,
) -> bool:

    if not url:
        return False

    canonical_url = (
        canonicalize_job_url(
            url
        )
    )

    if not canonical_url:
        return False

    result = await db.execute(
        select(
            Internship.id
        )
        .where(
            Internship.url
            == canonical_url
        )
        .limit(1)
    )

    return (
        result.scalar_one_or_none()
        is not None
    )


# ============================================================
# GET ACTIVE SUBSCRIPTIONS FOR COMPANY
# ============================================================

async def get_subscriptions_for_company(
    db: AsyncSession,
    company: str,
) -> List[Subscription]:

    if not company:
        return []

    company = company.strip()

    if not company:
        return []

    # --------------------------------------------------------
    # Your current schema uses "active".
    # Keep fallback for "is_active" if your model changes.
    # --------------------------------------------------------

    if hasattr(
        Subscription,
        "is_active"
    ):

        result = await db.execute(
            select(
                Subscription
            )
            .where(
                Subscription.company == company,
                Subscription.is_active.is_(True),
            )
        )

    else:

        result = await db.execute(
            select(
                Subscription
            )
            .where(
                Subscription.company == company,
                Subscription.is_active.is_(True),
            )
        )

    return result.scalars().all()


# ============================================================
# GET EXISTING NOTIFICATION SUBSCRIPTION IDS
# ============================================================

async def _get_existing_notification_ids(
    db: AsyncSession,
    internship_id: int,
) -> Set[int]:

    result = await db.execute(
        select(
            Notification.subscription_id
        )
        .where(
            Notification.internship_id
            == internship_id
        )
    )

    rows = result.all()

    return {
        subscription_id
        for (
            subscription_id,
        ) in rows
        if subscription_id is not None
    }


# ============================================================
# GET EXISTING NOTIFICATION PAIRS
# ============================================================

async def get_existing_notification_pairs(
    db: AsyncSession,
    internship_id: int,
    subscriptions: List[Subscription],
) -> Set[Tuple[str, int]]:

    if not internship_id:
        return set()

    if not subscriptions:
        return set()

    emails = set()

    for subscription in subscriptions:

        email = (
            getattr(
                subscription,
                "user_email",
                None
            )
            or getattr(
                subscription,
                "email",
                None
            )
        )

        if email:

            emails.add(
                email.strip().lower()
            )

    if not emails:
        return set()

    result = await db.execute(
        select(
            Notification.user_email,
            Notification.internship_id
        )
        .where(
            Notification.internship_id
            == internship_id,

            Notification.user_email.in_(
                list(emails)
            )
        )
    )

    rows = result.all()

    return {
        (
            email.strip().lower(),
            notification_internship_id
        )
        for (
            email,
            notification_internship_id
        ) in rows
        if email
    }


# ============================================================
# CREATE ONE PENDING NOTIFICATION
# ============================================================

async def create_pending_notification(
    db: AsyncSession,
    subscription: Subscription,
    internship: Internship,
    relevance_score: float,
) -> bool:

    if not subscription:
        return False

    if not internship:
        return False

    subscription_id = getattr(
        subscription,
        "id",
        None
    )

    internship_id = getattr(
        internship,
        "id",
        None
    )

    if subscription_id is None:
        return False

    if internship_id is None:
        return False

    # --------------------------------------------------------
    # ACTIVE SUBSCRIPTION
    # --------------------------------------------------------

    is_active = getattr(
        subscription,
        "is_active",
        None
    )

    if is_active is None:

        is_active = getattr(
            subscription,
            "active",
            True
        )

    if not is_active:
        return False

    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    user_email = (
        getattr(
            subscription,
            "user_email",
            None
        )
        or getattr(
            subscription,
            "email",
            None
        )
    )

    if not user_email:

        logger.warning(
            "Subscription %s has no email.",
            subscription_id
        )

        return False

    user_email = (
        user_email
        .strip()
        .lower()
    )

    # --------------------------------------------------------
    # NOTIFICATION WINDOW
    # --------------------------------------------------------

    now = _utc_now()

    if not _is_within_notification_window(
        internship,
        now
    ):

        logger.info(
            "Internship %s is outside notification window.",
            internship_id
        )

        return False

    # --------------------------------------------------------
    # RELEVANCE SAFETY GATE
    # --------------------------------------------------------

    relevance_score = float(
        relevance_score or 0
    )

    if relevance_score < MIN_RELEVANCE_SCORE:

        logger.info(
            "Internship %s rejected for notification. "
            "Score=%s",
            internship_id,
            relevance_score
        )

        return False

    # --------------------------------------------------------
    # IDEMPOTENCY
    # --------------------------------------------------------

    result = await db.execute(
        select(
            Notification.id
        )
        .where(
            Notification.user_email
            == user_email,

            Notification.internship_id
            == internship_id
        )
        .limit(1)
    )

    existing = (
        result.scalar_one_or_none()
    )

    if existing:

        logger.info(
            "⏭️ Notification already exists: "
            "email=%s internship=%s",
            user_email,
            internship_id
        )

        return False

    # --------------------------------------------------------
    # CREATE PENDING
    # --------------------------------------------------------

    notification = Notification(

        subscription_id=subscription_id,

        user_email=user_email,

        internship_id=internship_id,

        status="PENDING",

        relevance_score=relevance_score,

        created_at=now,

        updated_at=now,

        retry_count=0,

        next_retry_at=None,

        error_message=None,
    )

    # --------------------------------------------------------
    # SAVEPOINT
    # --------------------------------------------------------

    try:

        async with db.begin_nested():

            db.add(
                notification
            )

            await db.flush()

        logger.info(
            "🔔 PENDING notification created: "
            "subscription=%s internship=%s email=%s",
            subscription_id,
            internship_id,
            user_email
        )

        return True

    except IntegrityError:

        logger.info(
            "⏭️ Concurrent notification insertion detected: "
            "subscription=%s internship=%s email=%s",
            subscription_id,
            internship_id,
            user_email
        )

        return False


# ============================================================
# CREATE PENDING NOTIFICATIONS FOR JOB
# ============================================================

async def _create_pending_notifications_for_job(
    db: AsyncSession,
    internship: Internship,
    subscriptions: List[Subscription],
) -> int:

    if not internship:
        return 0

    if not internship.id:
        return 0

    if not subscriptions:
        return 0

    now = _utc_now()

    if not _is_within_notification_window(
        internship,
        now
    ):

        logger.info(
            "Internship %s is outside notification window.",
            internship.id
        )

        return 0

    relevance = (
        getattr(
            internship,
            "relevance_score",
            0
        )
        or 0
    )

    if relevance < MIN_RELEVANCE_SCORE:

        logger.info(
            "Internship %s rejected for notification. "
            "Score=%s",
            internship.id,
            relevance
        )

        return 0

    existing_pairs = (
        await get_existing_notification_pairs(
            db,
            internship.id,
            subscriptions
        )
    )

    created_count = 0

    for subscription in subscriptions:

        subscription_id = getattr(
            subscription,
            "id",
            None
        )

        if subscription_id is None:

            logger.warning(
                "Subscription has no database ID."
            )

            continue

        is_active = getattr(
            subscription,
            "is_active",
            None
        )

        if is_active is None:

            is_active = getattr(
                subscription,
                "active",
                True
            )

        if not is_active:
            continue

        user_email = (
            getattr(
                subscription,
                "user_email",
                None
            )
            or getattr(
                subscription,
                "email",
                None
            )
        )

        if not user_email:
            continue

        user_email = (
            user_email
            .strip()
            .lower()
        )

        notification_key = (
            user_email,
            internship.id
        )

        if notification_key in existing_pairs:

            logger.info(
                "⏭️ Notification already exists: "
                "email=%s internship=%s",
                user_email,
                internship.id
            )

            continue

        created = (
            await create_pending_notification(
                db=db,
                subscription=subscription,
                internship=internship,
                relevance_score=relevance
            )
        )

        if created:

            created_count += 1

            existing_pairs.add(
                notification_key
            )

    return created_count


# ============================================================
# FIND OR CREATE INTERNSHIP
# ============================================================

async def _find_or_create_internship(
    db: AsyncSession,
    job_data: Dict[str, Any],
) -> Tuple[Internship | None, bool]:

    if not job_data:
        return None, False

    raw_url = job_data.get(
        "url"
    )

    if not raw_url:
        return None, False

    canonical_url = (
        canonicalize_job_url(
            raw_url
        )
    )

    if not canonical_url:
        return None, False

    # --------------------------------------------------------
    # SEARCH BY URL
    # --------------------------------------------------------

    result = await db.execute(
        select(
            Internship
        )
        .where(
            Internship.url
            == canonical_url
        )
        .limit(1)
    )

    internship = (
        result.scalar_one_or_none()
    )

    # --------------------------------------------------------
    # EXISTING
    # --------------------------------------------------------

    if internship:

        internship.last_seen_at = (
            _utc_now()
        )

        return internship, False

    # --------------------------------------------------------
    # NEW
    # --------------------------------------------------------

    relevance_score = float(
        job_data.get(
            "relevance_score",
            0
        )
        or 0
    )

    passed_filter = (
        relevance_score
        >= MIN_RELEVANCE_SCORE
    )

    status = (
        "RELEVANT"
        if passed_filter
        else "LOW_RELEVANCE"
    )

    now = _utc_now()

    internship = Internship(

        url=canonical_url,

        title=(
            job_data.get(
                "title",
                ""
            )
            or ""
        ),

        company=(
            job_data.get(
                "company",
                ""
            )
            or ""
        ),

        location=(
            job_data.get(
                "location"
            )
        ),

        description=(
            job_data.get(
                "description"
            )
        ),

        source=(
            job_data.get(
                "source"
            )
        ),

        via=(
            job_data.get(
                "via"
            )
        ),

        relevance_score=relevance_score,

        passed_filter=passed_filter,

        status=status,

        email_sent=False,

        created_at=now,

        last_seen_at=now,
    )

    try:

        async with db.begin_nested():

            db.add(
                internship
            )

            await db.flush()

        logger.info(
            "🆕 New internship saved: %s",
            canonical_url
        )

        return internship, True

    except IntegrityError:

        logger.info(
            "♻️ Concurrent URL insertion detected: %s",
            canonical_url
        )

        result = await db.execute(
            select(
                Internship
            )
            .where(
                Internship.url
                == canonical_url
            )
            .limit(1)
        )

        existing = (
            result.scalar_one_or_none()
        )

        if not existing:
            raise

        existing.last_seen_at = (
            _utc_now()
        )

        return existing, False


# ============================================================
# SAVE INTERNSHIP
# ============================================================

async def save_internship(
    db: AsyncSession,
    job_data: Dict[str, Any],
):

    if not db:

        raise ValueError(
            "save_internship() requires an active "
            "AsyncSession."
        )

    if not job_data:
        return None, False

    raw_url = job_data.get(
        "url"
    )

    if not raw_url:

        logger.warning(
            "save_internship(): missing URL."
        )

        return None, False

    canonical_url = (
        canonicalize_job_url(
            raw_url
        )
    )

    if not canonical_url:

        logger.warning(
            "save_internship(): invalid URL: %s",
            raw_url
        )

        return None, False

    job_data = dict(
        job_data
    )

    job_data["url"] = canonical_url

    subscriber_group = (
        job_data.get(
            "subscriber_group"
        )
        or []
    )

    create_notification = (
        job_data.get(
            "create_notification",
            False
        )
    )

    requested_status = (
        job_data.get(
            "status"
        )
    )

    internship, created = (
        await _find_or_create_internship(
            db,
            job_data
        )
    )

    if not internship:
        return None, False

    internship.last_seen_at = (
        _utc_now()
    )

    if requested_status:

        internship.status = (
            requested_status
        )

    if not create_notification:

        if requested_status == "LOW_RELEVANCE":

            internship.passed_filter = False

    notification_count = 0

    if (
        create_notification
        and subscriber_group
    ):

        notification_count = (
            await _create_pending_notifications_for_job(
                db,
                internship,
                list(
                    subscriber_group
                )
            )
        )

        logger.info(
            "🔔 Created %s pending notifications "
            "for internship %s.",
            notification_count,
            internship.id
        )

    return internship, created


# ============================================================
# PROCESS ONE JOB
# ============================================================

async def process_single_job(
    db: AsyncSession,
    job_data: Dict[str, Any],
) -> Tuple[int, bool]:

    internship, is_new = (
        await _find_or_create_internship(
            db,
            job_data
        )
    )

    if not internship:
        return 0, False

    now = _utc_now()

    if not _is_within_notification_window(
        internship,
        now
    ):

        return 0, is_new

    relevance = (
        getattr(
            internship,
            "relevance_score",
            0
        )
        or 0
    )

    if relevance < MIN_RELEVANCE_SCORE:

        return 0, is_new

    subscriptions = (
        await get_subscriptions_for_company(
            db,
            internship.company
        )
    )

    if not subscriptions:
        return 0, is_new

    created_count = (
        await _create_pending_notifications_for_job(
            db,
            internship,
            subscriptions
        )
    )

    return created_count, is_new


# ============================================================
# PROCESS MULTIPLE JOBS
# ============================================================

async def process_job_batch(
    raw_jobs: List[Dict[str, Any]],
) -> Dict[str, int]:

    stats = {

        "processed": 0,

        "new_internships": 0,

        "existing_internships": 0,

        "notifications_created": 0,

        "duplicates_in_cycle": 0,

        "outside_window": 0,

        "low_relevance": 0,

        "invalid_jobs": 0,
    }

    seen_urls_in_cycle: Set[str] = set()

    async with AsyncSessionLocal() as db:

        try:

            for job_data in raw_jobs:

                if not job_data:

                    stats[
                        "invalid_jobs"
                    ] += 1

                    continue

                raw_url = job_data.get(
                    "url"
                )

                if not raw_url:

                    stats[
                        "invalid_jobs"
                    ] += 1

                    continue

                canonical_url = (
                    canonicalize_job_url(
                        raw_url
                    )
                )

                if not canonical_url:

                    stats[
                        "invalid_jobs"
                    ] += 1

                    continue

                if canonical_url in seen_urls_in_cycle:

                    stats[
                        "duplicates_in_cycle"
                    ] += 1

                    continue

                seen_urls_in_cycle.add(
                    canonical_url
                )

                notification_count, is_new = (
                    await process_single_job(
                        db,
                        {
                            **job_data,
                            "url": canonical_url
                        }
                    )
                )

                if is_new:

                    stats[
                        "new_internships"
                    ] += 1

                else:

                    stats[
                        "existing_internships"
                    ] += 1

                stats[
                    "notifications_created"
                ] += notification_count

                stats[
                    "processed"
                ] += 1

            await db.commit()

            logger.info(
                "Job batch completed: %s",
                stats
            )

            return stats

        except Exception:

            await db.rollback()

            logger.exception(
                "Job batch processing failed."
            )

            raise


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

async def process_jobs(
    raw_jobs: List[Dict[str, Any]],
) -> Dict[str, int]:

    return await process_job_batch(
        raw_jobs
    )