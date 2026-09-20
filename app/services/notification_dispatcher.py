
# ============================================================
# NOTIFICATION DISPATCHER
# File:
# app/services/notification_dispatcher.py
#
# PostgreSQL + asyncpg + AsyncSessionLocal
# ============================================================

import asyncio
import hashlib
import logging

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import (
    case,
    or_,
    select,
    update,
)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.database import AsyncSessionLocal
from app.models import (
    Subscription,
    Internship,
    Notification,
)


from app.models.notification import (
    
    NotificationStatus,
)

from app.services.email_service import (
    send_notification_email,
)


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

BATCH_SIZE = 100

MAX_INTERNSHIPS_PER_EMAIL = 15

MAX_RETRIES = 5

BASE_RETRY_DELAY_MINUTES = 5

PROCESSING_TIMEOUT_MINUTES = 15

MAX_CONCURRENT_EMAILS = 10

NEXT_DIGEST_DELAY_HOURS = 12

NEW_JOB_WINDOW_HOURS = 12

ZOMBIE_RECOVERY_INTERVAL_SECONDS = 300


# ============================================================
# UTC TIME
# ============================================================

def _utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    )


# ============================================================
# ENSURE UTC
# ============================================================

def _ensure_utc(value) -> datetime:
    """
    Convert datetime/string into timezone-aware UTC datetime.
    """

    if value is None:

        return _utc_now()

    if isinstance(value, str):

        try:

            value = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00"
                )
            )

        except ValueError:

            return _utc_now()

    if value.tzinfo is None:

        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


# ============================================================
# DETERMINE WHETHER INTERNSHIP IS NEW
# ============================================================

def _is_new_internship(
    internship
) -> bool:

    if not internship:

        return False

    created_at = getattr(
        internship,
        "created_at",
        None
    )

    if created_at is None:

        return False

    created_at = _ensure_utc(
        created_at
    )

    cutoff = (
        _utc_now()
        -
        timedelta(
            hours=NEW_JOB_WINDOW_HOURS
        )
    )

    return created_at >= cutoff


# ============================================================
# CREATED AT SORT VALUE
# ============================================================

def _created_sort_value(
    internship
) -> float:

    if not internship:

        return float("-inf")

    created_at = getattr(
        internship,
        "created_at",
        None
    )

    if created_at is None:

        return float("-inf")

    try:

        return _ensure_utc(
            created_at
        ).timestamp()

    except Exception:

        return float("-inf")


# ============================================================
# INTERNSHIP SORT KEY
# ============================================================

def _internship_sort_key(
    internship
) -> tuple:

    if not internship:

        return (
            0.0,
            float("-inf")
        )

    relevance = getattr(
        internship,
        "relevance_score",
        0
    ) or 0

    try:

        relevance = float(
            relevance
        )

    except (
        TypeError,
        ValueError
    ):

        relevance = 0.0

    return (
        relevance,
        _created_sort_value(
            internship
        )
    )


# ============================================================
# BUILD EMAIL ITEM
# ============================================================

def _build_email_item(
    notification: Notification
) -> Optional[dict]:

    internship = (
        notification.internship
    )

    if not internship:

        return None

    return {

        "id": internship.id,

        "company": (
            internship.company
            or ""
        ),

        "title": (
            internship.title
            or ""
        ),

        "location": (
            internship.location
            or "Location not specified"
        ),

        "url": (
            internship.url
            or ""
        ),

        "description": (
            internship.description
            or ""
        ),

        "relevance_score": (

            notification.relevance_score

            if notification.relevance_score
            is not None

            else (
                getattr(
                    internship,
                    "relevance_score",
                    0
                )
                or 0
            )
        ),

        "created_at": getattr(
            internship,
            "created_at",
            None
        ),

        "is_new": _is_new_internship(
            internship
        ),

        "notification_id": (
            notification.id
        ),
    }


# ============================================================
# ATOMICALLY CLAIM PENDING NOTIFICATIONS
# ============================================================

async def _claim_pending_notifications(
    db: AsyncSession,
    batch_size: int = BATCH_SIZE,
) -> List[int]:
    """
    Atomically claim ready PENDING notifications.

    PENDING
        ↓
    SELECT FOR UPDATE SKIP LOCKED
        ↓
    PROCESSING
        ↓
    COMMIT
    """

    now = _utc_now()

    target_ids = (

        select(
            Notification.id
        )

        .where(

            Notification.status
            == NotificationStatus.PENDING,

            or_(

                Notification.next_retry_at.is_(None),

                Notification.next_retry_at
                <= now,

            ),
        )

        .order_by(

            Notification.next_retry_at
            .asc()
            .nullsfirst(),

            Notification.created_at.asc(),

        )

        .limit(
            batch_size
        )

        .with_for_update(
            skip_locked=True
        )

        .cte(
            "target_notifications"
        )
    )

    statement = (

        update(
            Notification
        )

        .where(

            Notification.id.in_(
                select(
                    target_ids.c.id
                )
            )
        )

        .values(

            status=(
                NotificationStatus.PROCESSING
            ),

            processing_started_at=now,

            updated_at=now,

            next_retry_at=None,

        )

        .returning(
            Notification.id
        )
    )

    result = await db.execute(
        statement
    )

    claimed_ids = list(
        result.scalars().all()
    )

    await db.commit()

    if claimed_ids:

        logger.info(
            "🔒 Claimed %s pending notification(s).",
            len(claimed_ids)
        )

    return claimed_ids


# ============================================================
# FETCH CLAIMED NOTIFICATIONS
# ============================================================

async def _fetch_claimed_notifications(
    db: AsyncSession,
    notification_ids: List[int],
) -> List[Notification]:

    if not notification_ids:

        return []

    statement = (

        select(
            Notification
        )

        .options(

            joinedload(
                Notification.internship
            )

        )

        .where(

            Notification.id.in_(
                notification_ids
            ),

            Notification.status
            == NotificationStatus.PROCESSING,

        )
    )

    result = await db.execute(
        statement
    )

    return list(
        result.unique().scalars().all()
    )


# ============================================================
# ZOMBIE RECOVERY
# ============================================================

async def _recover_zombie_notifications(
    db: AsyncSession,
    timeout_minutes: int = PROCESSING_TIMEOUT_MINUTES,
    max_retries: int = MAX_RETRIES,
    batch_size: int = 50,
) -> List[int]:
    """
    Recover abandoned PROCESSING notifications.

    PROCESSING
        ↓
    timeout
        ↓
    retry_count + 1
        ↓
    retry_count < MAX_RETRIES
        ↓
    PENDING

    retry_count >= MAX_RETRIES
        ↓
    FAILED
    """

    now = _utc_now()

    stale_cutoff = (
        now
        -
        timedelta(
            minutes=timeout_minutes
        )
    )

    stale_ids = (

        select(
            Notification.id
        )

        .where(

            Notification.status
            == NotificationStatus.PROCESSING,

            Notification.processing_started_at
            <= stale_cutoff,

        )

        .order_by(

            Notification.processing_started_at.asc()

        )

        .limit(
            batch_size
        )

        .with_for_update(
            skip_locked=True
        )

        .cte(
            "stale_notifications"
        )
    )

    next_retry_count = (
        Notification.retry_count + 1
    )

    statement = (

        update(
            Notification
        )

        .where(

            Notification.id.in_(
                select(
                    stale_ids.c.id
                )
            )
        )

        .values(

            status=case(

                (
                    next_retry_count
                    >= max_retries,

                    NotificationStatus.FAILED,
                ),

                else_=NotificationStatus.PENDING,
            ),

            retry_count=next_retry_count,

            processing_started_at=None,

            next_retry_at=case(

                (
                    next_retry_count
                    >= max_retries,

                    None,
                ),

                else_=now,
            ),

            updated_at=now,

            error_message=case(

                (
                    next_retry_count
                    >= max_retries,

                    (
                        "Notification permanently failed "
                        "after exceeding the maximum number "
                        "of zombie recovery attempts."
                    ),
                ),

                else_=(
                    "Notification recovered after "
                    "worker processing timeout."
                ),
            ),
        )

        .returning(

            Notification.id,

            Notification.retry_count,

            Notification.status,

        )
    )

    result = await db.execute(
        statement
    )

    rows = list(
        result.all()
    )

    recovered_ids = []

    failed_ids = []

    for (
        notification_id,
        retry_count,
        status,
    ) in rows:

        if status == NotificationStatus.FAILED:

            failed_ids.append(
                notification_id
            )

            logger.error(

                "☠️ Notification %s permanently "
                "failed during zombie recovery. "
                "Retry count=%s/%s.",

                notification_id,

                retry_count,

                max_retries,
            )

            logger.critical(

                "🚨 POISON_NOTIFICATION | "
                "notification_id=%s | "
                "retry_count=%s | "
                "max_retries=%s",

                notification_id,

                retry_count,

                max_retries,
            )

        else:

            recovered_ids.append(
                notification_id
            )

            logger.warning(

                "♻️ Recovered zombie notification %s "
                "and returned it to PENDING. "
                "Retry count=%s/%s.",

                notification_id,

                retry_count,

                max_retries,
            )

    await db.commit()

    if recovered_ids:

        logger.warning(

            "♻️ Zombie recovery complete | "
            "Recovered=%s | Failed=%s",

            len(recovered_ids),

            len(failed_ids),

        )

    elif failed_ids:

        logger.error(

            "☠️ Zombie recovery found only "
            "poison notifications | Failed=%s",

            len(failed_ids),

        )

    return recovered_ids


# ============================================================
# GROUP NOTIFICATIONS BY USER
# ============================================================

def _group_by_user(
    notifications: List[Notification]
) -> Dict[str, List[Notification]]:

    groups: Dict[
        str,
        List[Notification]
    ] = {}

    for notification in notifications:

        email = (

            notification.user_email
            or ""

        ).strip().lower()

        if not email:

            logger.warning(

                "⚠️ Notification %s has no user email.",

                notification.id

            )

            continue

        groups.setdefault(
            email,
            []
        ).append(
            notification
        )

    return groups


# ============================================================
# PRIORITIZE USER NOTIFICATIONS
# ============================================================

def _prioritize_user_notifications(
    notifications: List[Notification]
) -> List[Notification]:

    new_notifications = []

    old_notifications = []

    for notification in notifications:

        internship = (
            notification.internship
        )

        if _is_new_internship(
            internship
        ):

            new_notifications.append(
                notification
            )

        else:

            old_notifications.append(
                notification
            )

    new_notifications.sort(

        key=lambda notification:

            _internship_sort_key(
                notification.internship
            ),

        reverse=True

    )

    old_notifications.sort(

        key=lambda notification:

            _internship_sort_key(
                notification.internship
            ),

        reverse=True

    )

    prioritized = (

        new_notifications
        +
        old_notifications

    )

    return prioritized[
        :MAX_INTERNSHIPS_PER_EMAIL
    ]


# ============================================================
# GENERATE DETERMINISTIC IDEMPOTENCY KEY
# ============================================================

def _generate_idempotency_key(
    user_email: str,
    notifications: List[Notification],
) -> str:
    """
    Same user + same notification IDs
= same deterministic email idempotency key.
    """

    safe_email = (

        user_email
        or ""

    ).strip().lower()

    sorted_ids = sorted(

        int(
            notification.id
        )

        for notification
        in notifications

    )

    raw_payload = (

        f"{safe_email}:"

        +

        "-".join(

            str(
                notification_id
            )

            for notification_id
            in sorted_ids

        )
    )

    digest_hash = hashlib.sha256(

        raw_payload.encode(
            "utf-8"
        )

    ).hexdigest()

    return (
        "internship-digest:"
        +
        digest_hash
    )


# ============================================================
# GET OR CREATE PERSISTENT IDEMPOTENCY KEY
# ============================================================

# ============================================================
# GET OR CREATE IDEMPOTENCY KEY
# ============================================================

# ============================================================
# GET OR CREATE IDEMPOTENCY KEY
# ============================================================

async def _get_or_create_idempotency_key(
    db: AsyncSession,
    user_email: str,
    notifications: List[Notification],
) -> str:
    """
    Get or create one persistent idempotency key for a digest.

    IMPORTANT:
    The notifications table has a UNIQUE constraint on
    idempotency_key.

    Therefore the digest key must NOT be assigned to every
    notification in the digest.

    One notification acts as the owner of the digest key.
    The remaining notifications keep idempotency_key=NULL.

    The dispatcher still uses the same digest key when calling
    the email provider.
    """

    # ========================================================
    # VALIDATION
    # ========================================================

    if not user_email:

        raise ValueError(
            "user_email is required for idempotency key."
        )

    if not notifications:

        raise ValueError(
            "notifications are required for idempotency key."
        )

    # ========================================================
    # FIND EXISTING DIGEST KEY
    # ========================================================

    existing_key = None

    for notification in notifications:

        if notification.idempotency_key:

            existing_key = str(
                notification.idempotency_key
            )

            break

    # ========================================================
    # IF EXISTING KEY EXISTS
    # ========================================================

    if existing_key:

        logger.info(
            "🔐 Reusing existing idempotency key | "
            "User=%s | Key=%s",
            user_email,
            existing_key,
        )

        return existing_key

    # ========================================================
    # MAKE SURE NOTIFICATION IDS EXIST
    # ========================================================

    notification_ids = sorted(

        notification.id

        for notification
        in notifications

        if notification.id is not None
    )

    if not notification_ids:

        raise ValueError(
            "Notifications must have database IDs "
            "before creating an idempotency key."
        )

    # ========================================================
    # BUILD DETERMINISTIC DIGEST INPUT
    # ========================================================

    raw_key = (
        f"{user_email}:"
        + ",".join(
            str(notification_id)
            for notification_id
            in notification_ids
        )
    )

    # ========================================================
    # HASH
    # ========================================================

    digest = hashlib.sha256(
        raw_key.encode("utf-8")
    ).hexdigest()

    idempotency_key = (
        f"internship-digest:{digest}"
    )

    # ========================================================
    # VALIDATE LENGTH
    # ========================================================

    if len(idempotency_key) > 256:

        raise ValueError(
            "Generated idempotency key exceeds "
            "256 characters."
        )

    # ========================================================
    # PERSIST ONLY ON ONE NOTIFICATION
    # ========================================================
    #
    # IMPORTANT:
    #
    # The database has:
    #
    # UNIQUE(idempotency_key)
    #
    # Therefore we store the digest key on ONLY ONE
    # notification.
    #
    # The first notification becomes the digest owner.
    #
    # ========================================================

    owner = notifications[0]

    owner.idempotency_key = (
        idempotency_key
    )

    owner.updated_at = _utc_now()

    # ========================================================
    # COMMIT
    # ========================================================

    await db.commit()

    # ========================================================
    # LOG
    # ========================================================

    logger.info(
        "🔐 Created digest idempotency key | "
        "User=%s | OwnerNotification=%s | Key=%s",
        user_email,
        owner.id,
        idempotency_key,
    )

    return idempotency_key
# ============================================================
# MARK NOTIFICATIONS SENT
# ============================================================

async def _mark_notifications_sent(
    db: AsyncSession,
    notifications: List[Notification],
) -> None:

    now = _utc_now()

    for notification in notifications:

        if (
            notification.status
            != NotificationStatus.PROCESSING
        ):

            continue

        notification.status = (
            NotificationStatus.SENT
        )

        notification.sent_at = now

        notification.updated_at = now

        notification.processing_started_at = (
            None
        )

        notification.error_message = (
            None
        )

        notification.next_retry_at = (
            None
        )

    await db.commit()


# ============================================================
# DEFER UNSELECTED NOTIFICATIONS
# ============================================================

async def _defer_unselected_notifications(
    db: AsyncSession,
    notifications: List[Notification],
) -> None:

    if not notifications:

        return

    now = _utc_now()

    next_digest_time = (

        now
        +
        timedelta(
            hours=NEXT_DIGEST_DELAY_HOURS
        )
    )

    deferred_count = 0

    for notification in notifications:

        if (
            notification.status
            != NotificationStatus.PROCESSING
        ):

            continue

        notification.status = (
            NotificationStatus.PENDING
        )

        notification.updated_at = now

        notification.next_retry_at = (
            next_digest_time
        )

        notification.processing_started_at = (
            None
        )

        deferred_count += 1

    await db.commit()

    logger.info(

        "↩️ Deferred %s notification(s) "
        "until next digest cycle at %s.",

        deferred_count,

        next_digest_time,
    )


# ============================================================
# MARK NOTIFICATIONS FAILED
# ============================================================

async def _mark_notifications_failed(
    db: AsyncSession,
    notifications: List[Notification],
    error: Exception,
) -> None:

    now = _utc_now()

    for notification in notifications:

        if (
            notification.status
            != NotificationStatus.PROCESSING
        ):

            continue

        retry_count = (

            notification.retry_count
            or 0

        ) + 1

        notification.retry_count = (
            retry_count
        )

        notification.error_message = (
            str(error)[:1000]
        )

        notification.updated_at = now

        notification.processing_started_at = (
            None
        )

        if retry_count >= MAX_RETRIES:

            notification.status = (
                NotificationStatus.FAILED
            )

            notification.next_retry_at = (
                None
            )

            logger.error(

                "❌ Notification %s permanently failed "
                "(%s/%s).",

                notification.id,

                retry_count,

                MAX_RETRIES,
            )

        else:

            backoff_minutes = (

                BASE_RETRY_DELAY_MINUTES
                *
                (
                    2
                    **
                    (
                        retry_count - 1
                    )
                )
            )

            notification.status = (
                NotificationStatus.PENDING
            )

            notification.next_retry_at = (

                now
                +
                timedelta(
                    minutes=backoff_minutes
                )
            )

            logger.warning(

                "⚠️ Notification %s failed. "
                "Retry %s/%s in %s minute(s).",

                notification.id,

                retry_count,

                MAX_RETRIES,

                backoff_minutes,
            )

    await db.commit()


# ============================================================
# PROCESS ONE USER DIGEST
# ============================================================

async def _process_user_digest(
    user_email: str,
    notification_ids: List[int],
) -> bool:

    async with AsyncSessionLocal() as db:

        try:

            # =================================================
            # FETCH CLAIMED NOTIFICATIONS
            # =================================================

            notifications = (
                await _fetch_claimed_notifications(
                    db,
                    notification_ids
                )
            )

            if not notifications:

                logger.warning(

                    "⚠️ No PROCESSING notifications "
                    "found for %s.",

                    user_email
                )

                return False

            # =================================================
            # PRIORITIZE
            # =================================================

            selected = (
                _prioritize_user_notifications(
                    notifications
                )
            )

            # =================================================
            # BUILD EMAIL ITEMS
            # =================================================

            internships = []

            selected_valid_notifications = []

            for notification in selected:

                item = _build_email_item(
                    notification
                )

                if item is None:

                    continue

                internships.append(
                    item
                )

                selected_valid_notifications.append(
                    notification
                )

            # =================================================
            # NO VALID INTERNSHIPS
            # =================================================

            if not internships:

                logger.warning(

                    "⚠️ No valid internships found "
                    "for %s.",

                    user_email
                )

                await _mark_notifications_failed(

                    db,

                    notifications,

                    ValueError(
                        "No valid associated "
                        "internships found."
                    )
                )

                return False

            # =================================================
            # IDEMPOTENCY KEY
            # =================================================

            idempotency_key = (

                await _get_or_create_idempotency_key(

                    db,

                    user_email,

                    selected_valid_notifications
                )
            )

            logger.info(

                "📨 Preparing digest | "
                "User=%s | "
                "Selected=%s/%s | "
                "Idempotency=%s",

                user_email,

                len(
                    selected_valid_notifications
                ),

                len(
                    notifications
                ),

                idempotency_key,
            )

            

            response = await asyncio.to_thread(

                send_notification_email,

                user_email,

                internships,

                idempotency_key,
            )

            # =================================================
            # PROVIDER FAILURE
            # =================================================

            if response is None:

                raise RuntimeError(

                    "Email provider returned "
                    "empty response."
                )

            # =================================================
            # MARK SELECTED AS SENT
            # =================================================

            await _mark_notifications_sent(

                db,

                selected_valid_notifications
            )

            logger.info(

                "✅ Digest sent successfully | "
                "User=%s | Jobs=%s",

                user_email,

                len(
                    selected_valid_notifications
                ),
            )

            # =================================================
            # FIND UNSELECTED
            # =================================================

            selected_ids = {

                notification.id

                for notification
                in selected_valid_notifications
            }

            unselected = [

                notification

                for notification
                in notifications

                if notification.id
                not in selected_ids
            ]

            # =================================================
            # DEFER REMAINING
            # =================================================

            if unselected:

                await _defer_unselected_notifications(

                    db,

                    unselected
                )

                logger.info(

                    "↩️ %s notification(s) deferred "
                    "for user %s.",

                    len(
                        unselected
                    ),

                    user_email,
                )

            return True

        except Exception as error:

            logger.exception(

                "❌ Digest failed for %s.",

                user_email
            )

            await db.rollback()

            try:

                failed_notifications = (

                    await _fetch_claimed_notifications(

                        db,

                        notification_ids
                    )
                )

                if failed_notifications:

                    await _mark_notifications_failed(

                        db,

                        failed_notifications,

                        error
                    )

            except Exception:

                await db.rollback()

                logger.exception(

                    "❌ Failed to update failure state "
                    "for %s.",

                    user_email
                )

            return False


# ============================================================
# MAIN DISPATCHER BATCH
# ============================================================

async def dispatch_pending_notifications_batch() -> int:
    """
    Process one notification batch.

    Pipeline:

        PENDING
           ↓
        ATOMIC CLAIM
           ↓
        PROCESSING
           ↓
        GROUP BY USER
           ↓
        NEW FIRST
           ↓
        MAX 15
           ↓
        GMAIL SMTP
           ↓
        SENT
    """

    # ========================================================
    # PHASE 1 — CLAIM
    # ========================================================

    async with AsyncSessionLocal() as claim_db:

        try:

            claimed_ids = (

                await _claim_pending_notifications(

                    claim_db
                )
            )

        except Exception:

            await claim_db.rollback()

            logger.exception(

                "❌ Failed to claim notification batch."
            )

            raise

    # ========================================================
    # NOTHING TO PROCESS
    # ========================================================

    if not claimed_ids:

        logger.debug(

            "No notifications ready for "
            "digest dispatch."
        )

        return 0

    # ========================================================
    # PHASE 2 — FETCH + GROUP
    # ========================================================

    async with AsyncSessionLocal() as grouping_db:

        try:

            notifications = (

                await _fetch_claimed_notifications(

                    grouping_db,

                    claimed_ids
                )
            )

            groups = (

                _group_by_user(
                    notifications
                )
            )

        except Exception:

            await grouping_db.rollback()

            logger.exception(

                "❌ Failed to group "
                "claimed notifications."
            )

            raise

    # ========================================================
    # INVALID GROUPS
    # ========================================================

    if not groups:

        logger.warning(

            "⚠️ Claimed notifications but "
            "no valid user groups found."
        )

        async with AsyncSessionLocal() as recovery_db:

            try:

                claimed_notifications = (

                    await _fetch_claimed_notifications(

                        recovery_db,

                        claimed_ids
                    )
                )

                if claimed_notifications:

                    await _mark_notifications_failed(

                        recovery_db,

                        claimed_notifications,

                        ValueError(
                            "No valid user email found."
                        )
                    )

            except Exception:

                await recovery_db.rollback()

                logger.exception(

                    "❌ Failed to recover "
                    "ungrouped notifications."
                )

        return 0

    # ========================================================
    # PHASE 3 — CONCURRENT USER DIGESTS
    # ========================================================

    semaphore = asyncio.Semaphore(
        MAX_CONCURRENT_EMAILS
    )

    async def process_user(
        user_email: str,
        user_notifications: List[Notification],
    ) -> bool:

        async with semaphore:

            notification_ids = [

                notification.id

                for notification
                in user_notifications
            ]

            try:

                return await _process_user_digest(

                    user_email,

                    notification_ids
                )

            except Exception:

                logger.exception(

                    "❌ User digest task crashed "
                    "for %s.",

                    user_email
                )

                return False

    # ========================================================
    # RUN CONCURRENT DIGESTS
    # ========================================================

    results = await asyncio.gather(

        *[

            process_user(

                email,

                user_notifications
            )

            for (
                email,
                user_notifications
            )
            in groups.items()
        ],

        return_exceptions=False,
    )

    # ========================================================
    # RESULTS
    # ========================================================

    successful_digests = sum(

        1

        for result
        in results

        if result is True
    )

    failed_digests = (

        len(results)
        -
        successful_digests
    )

    # ========================================================
    # FINAL LOG
    # ========================================================

    logger.info(

        "📨 Digest cycle complete | "
        "Claimed=%s | "
        "Users=%s | "
        "Sent=%s | "
        "Failed=%s",

        len(
            claimed_ids
        ),

        len(
            groups
        ),

        successful_digests,

        failed_digests,
    )

    return successful_digests


# ============================================================
# CONTINUOUS DISPATCH LOOP
# ============================================================

async def run_notification_dispatcher(
    interval_seconds: int = 30,
):
    """
    Continuous notification dispatcher.

    HOT PATH:
        Every 30 seconds
        → process ready PENDING notifications

    COLD PATH:
        Every 5 minutes
        → recover zombie PROCESSING notifications
    """

    logger.info(
        "🚀 Notification digest dispatcher started."
    )

    recovery_counter = 0

    while True:

        try:

            # =================================================
            # HOT PATH
            # =================================================

            await dispatch_pending_notifications_batch()

            # =================================================
            # ZOMBIE RECOVERY TIMER
            # =================================================

            recovery_counter += (
                interval_seconds
            )

            if (

                recovery_counter
                >= ZOMBIE_RECOVERY_INTERVAL_SECONDS
            ):

                recovery_counter = 0

                async with AsyncSessionLocal() as recovery_db:

                    try:

                        recovered_ids = (

                            await _recover_zombie_notifications(

                                recovery_db
                            )
                        )

                        if recovered_ids:

                            logger.info(

                                "♻️ Zombie recovery returned "
                                "%s notification(s) for "
                                "continued processing.",

                                len(
                                    recovered_ids
                                )
                            )

                    except Exception:

                        await recovery_db.rollback()

                        logger.exception(

                            "❌ Zombie recovery failed."
                        )

        except Exception:

            logger.exception(

                "❌ Notification dispatcher "
                "cycle failed."
            )

        await asyncio.sleep(
            interval_seconds
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(

        level=logging.INFO,

        format=(

            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        )
    )

    asyncio.run(

        run_notification_dispatcher()
    )

