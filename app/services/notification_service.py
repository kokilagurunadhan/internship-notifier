# ============================================================
# NOTIFICATION SERVICE
# File: app/services/notification_service.py
# ============================================================

from datetime import datetime, timedelta, timezone
import logging
from typing import Dict, List

from sqlalchemy import or_

from app.database.database import SessionLocal

from app.models.internship import Internship
from app.models.notification import Notification

from app.services.email_service import send_notification_email


# ============================================================
# LOGGER & CONFIGURATION
# ============================================================

logger = logging.getLogger(__name__)

MIN_RELEVANCE_SCORE = 50
MAX_RETRIES = 5
MAX_EMAIL_INTERNSHIPS = 15
RETRY_DELAY_MINUTES = 30


# ============================================================
# UTC HELPERS
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_utc(
    dt: datetime | None,
) -> datetime:
    """
    Ensure datetime is UTC-aware.
    """

    if dt is None:
        return _utc_now()

    if dt.tzinfo is None:
        return dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    )


# ============================================================
# SEND PENDING NOTIFICATIONS
# ============================================================

def send_pending_notifications() -> Dict[str, int]:
    """
    Find eligible PENDING notifications.

    Flow:

        PENDING notifications
                ↓
        Relevance >= 50
                ↓
        Retry window eligible
                ↓
        Group by user email
                ↓
        Priority sorting
                ↓
        Select top 15
                ↓
        Batch fetch internships
                ↓
        Send ONE grouped email per user
                ↓
        SUCCESS → SENT
                ↓
        FAILURE → retry / FAILED
    """

    db = SessionLocal()

    try:

        # ====================================================
        # CURRENT TIME
        # ====================================================

        now = _utc_now()


        # ====================================================
        # 1. FETCH ELIGIBLE PENDING NOTIFICATIONS
        # ====================================================

        notifications = (
            db.query(Notification)
            .filter(
                Notification.status == "PENDING",

                Notification.relevance_score
                >= MIN_RELEVANCE_SCORE,

                or_(
                    Notification.next_retry_at.is_(None),
                    Notification.next_retry_at <= now,
                ),
            )
            .order_by(
                Notification.created_at.asc()
            )
            .all()
        )


        logger.info(
            "📦 Pending notifications ready "
            "for processing: %d",
            len(notifications),
        )


        # ====================================================
        # NO PENDING NOTIFICATIONS
        # ====================================================

        if not notifications:

            logger.info(
                "✅ No pending notifications to send."
            )

            return {
                "pending": 0,
                "emails_sent": 0,
                "notifications_sent": 0,
                "notifications_failed": 0,
            }


        # ====================================================
        # 2. GROUP NOTIFICATIONS BY USER EMAIL
        # ====================================================

        grouped: Dict[
            str,
            List[Notification]
        ] = {}


        for notification in notifications:

            email = (
                notification.user_email
                or ""
            ).strip()


            # ------------------------------------------------
            # Invalid email
            # ------------------------------------------------

            if not email:

                logger.warning(
                    "⚠️ Notification %s has no email. "
                    "Skipping.",
                    notification.id,
                )

                continue


            # ------------------------------------------------
            # Add notification to user's group
            # ------------------------------------------------

            grouped.setdefault(
                email,
                []
            ).append(
                notification
            )


        # ====================================================
        # DELIVERY STATISTICS
        # ====================================================

        emails_sent = 0

        notifications_sent = 0

        notifications_failed = 0


        # ====================================================
        # 3. PROCESS EACH USER
        # ====================================================

        for (
            email,
            user_notifications
        ) in grouped.items():

            logger.info(
                "📧 Processing notification digest "
                "for: %s",
                email,
            )


            # =================================================
            # 4. CALCULATE PRIORITY
            # =================================================

            priority_items = []


            for notification in user_notifications:

                # ------------------------------------------------
                # Relevance score
                # ------------------------------------------------

                relevance = (
                    notification.relevance_score
                    or 0
                )


                # ------------------------------------------------
                # Notification age
                # ------------------------------------------------

                created_at = _ensure_utc(
                    notification.created_at
                )


                age_days = max(
                    0.0,
                    (
                        now
                        - created_at
                    ).total_seconds()
                    / 86400.0,
                )


                # ------------------------------------------------
                # Effective priority
                #
                # Relevance is primary.
                # Age provides a small anti-starvation bonus.
                # ------------------------------------------------

                effective_priority = (
                    relevance
                    + age_days
                )


                priority_items.append(
                    (
                        notification,
                        effective_priority,
                        created_at,
                    )
                )


            # =================================================
            # 5. SORT BY PRIORITY
            # =================================================

            priority_items.sort(
                key=lambda item: (
                    item[1],
                    item[2],
                ),
                reverse=True,
            )


            # =================================================
            # 6. SELECT TOP 15
            # =================================================

            selected_notifications = [
                item[0]
                for item in priority_items[
                    :MAX_EMAIL_INTERNSHIPS
                ]
            ]


            if not selected_notifications:

                continue


            logger.info(
                "📦 User %s has %d pending "
                "notifications; selected %d.",
                email,
                len(user_notifications),
                len(selected_notifications),
            )


            # =================================================
            # 7. BATCH FETCH INTERNSHIPS
            #
            # Avoid N+1 queries.
            # =================================================

            target_internship_ids = {
                notification.internship_id
                for notification
                in selected_notifications
            }


            internship_records = (
                db.query(Internship)
                .filter(
                    Internship.id.in_(
                        target_internship_ids
                    )
                )
                .all()
            )


            # ------------------------------------------------
            # Convert to dictionary:
            #
            # internship_id -> Internship
            # ------------------------------------------------

            internship_map = {
                internship.id: internship
                for internship
                in internship_records
            }


            # =================================================
            # 8. MATCH NOTIFICATIONS TO INTERNSHIPS
            # =================================================

            valid_notifications = []

            internships_to_send = []


            for notification in selected_notifications:

                internship = internship_map.get(
                    notification.internship_id
                )


                # ------------------------------------------------
                # Internship missing
                # ------------------------------------------------

                if not internship:

                    logger.warning(
                        "⚠️ Internship %s missing "
                        "for notification %s.",
                        notification.internship_id,
                        notification.id,
                    )

                    continue


                valid_notifications.append(
                    notification
                )

                internships_to_send.append(
                    internship
                )


            # =================================================
            # NO VALID INTERNSHIPS
            # =================================================

            if not internships_to_send:

                logger.warning(
                    "⚠️ No valid internships found "
                    "for %s.",
                    email,
                )

                continue


            selected = valid_notifications


            # =================================================
            # 9. CREATE IDEMPOTENCY KEY
            # =================================================

            notification_ids = sorted(
                notification.id
                for notification
                in selected
            )


            idempotency_key = (
                "internship-digest/"
                f"{email}/"
                f"{'-'.join(
                    map(
                        str,
                        notification_ids
                    )
                )}"
            )


            logger.info(
                "🔐 Email idempotency key: %s",
                idempotency_key,
            )


            # =================================================
            # 10. SEND GROUPED EMAIL
            # =================================================

            email_success = False

            email_error = None


            try:

                response = send_notification_email(
                    email,
                    internships_to_send,
                    idempotency_key,
                )


                if response:

                    email_success = True

                else:

                    email_success = False

                    email_error = (
                        "Email service returned "
                        "a non-truthy response."
                    )


            except Exception as error:

                email_success = False

                email_error = str(error)


                logger.exception(
                    "❌ Email exception thrown "
                    "for %s",
                    email,
                )


            # =================================================
            # 11. EMAIL SUCCESS
            # =================================================

            if email_success:

                logger.info(
                    "✅ Email successfully sent "
                    "to %s",
                    email,
                )


                now_utc = _utc_now()


                # ------------------------------------------------
                # MARK NOTIFICATIONS AS SENT
                # ------------------------------------------------

                for notification in selected:

                    notification.status = "SENT"

                    notification.sent_at = (
                        now_utc
                    )

                    notification.updated_at = (
                        now_utc
                    )

                    notification.error_message = None

                    notification.next_retry_at = None


                # ------------------------------------------------
                # MARK INTERNSHIPS AS EMAIL SENT
                # ------------------------------------------------

                for internship in internships_to_send:

                    internship.email_sent = True


                # ------------------------------------------------
                # COMMIT SUCCESS
                # ------------------------------------------------

                db.commit()


                emails_sent += 1

                notifications_sent += (
                    len(selected)
                )


                logger.info(
                    "✅ Marked %d notifications "
                    "SENT for %s.",
                    len(selected),
                    email,
                )


            # =================================================
            # 12. EMAIL FAILURE
            # =================================================

            else:

                logger.error(
                    "❌ Email failed for %s: %s",
                    email,
                    email_error,
                )


                retry_now = _utc_now()


                # ------------------------------------------------
                # UPDATE EACH NOTIFICATION
                # ------------------------------------------------

                for notification in selected:

                    current_retry_count = (
                        notification.retry_count
                        or 0
                    )


                    new_retry_count = (
                        current_retry_count
                        + 1
                    )


                    notification.retry_count = (
                        new_retry_count
                    )


                    notification.error_message = (
                        email_error
                        or "Email delivery failed."
                    )


                    notification.updated_at = (
                        retry_now
                    )


                    # =================================================
                    # MAX RETRIES REACHED
                    # =================================================

                    if (
                        new_retry_count
                        >= MAX_RETRIES
                    ):

                        notification.status = (
                            "FAILED"
                        )

                        notification.next_retry_at = (
                            None
                        )


                        logger.error(
                            "🚫 Notification %s "
                            "exceeded maximum retries "
                            "(%d). Marked FAILED.",
                            notification.id,
                            MAX_RETRIES,
                        )


                    # =================================================
                    # RETRY
                    # =================================================

                    else:

                        notification.status = (
                            "PENDING"
                        )


                        # ------------------------------------------------
                        # Exponential backoff
                        #
                        # Attempt 1 → 30 minutes
                        # Attempt 2 → 60 minutes
                        # Attempt 3 → 120 minutes
                        # Attempt 4 → 240 minutes
                        # ------------------------------------------------

                        backoff_minutes = (
                            RETRY_DELAY_MINUTES
                            * (
                                2
                                ** (
                                    new_retry_count
                                    - 1
                                )
                            )
                        )


                        notification.next_retry_at = (
                            retry_now
                            + timedelta(
                                minutes=backoff_minutes
                            )
                        )


                        logger.info(
                            "🔄 Notification %s "
                            "retry scheduled in %d "
                            "minutes "
                            "(attempt %d/%d).",
                            notification.id,
                            backoff_minutes,
                            new_retry_count,
                            MAX_RETRIES,
                        )


                # ------------------------------------------------
                # COMMIT FAILURE / RETRY STATE
                # ------------------------------------------------

                db.commit()


                notifications_failed += (
                    len(selected)
                )


        # ====================================================
        # 13. FINAL SUMMARY
        # ====================================================

        summary = {

            "pending": len(
                notifications
            ),

            "emails_sent": emails_sent,

            "notifications_sent": (
                notifications_sent
            ),

            "notifications_failed": (
                notifications_failed
            ),
        }


        logger.info(
            "📊 Notification delivery summary: %s",
            summary,
        )


        return summary


    # ========================================================
    # UNEXPECTED ERROR
    # ========================================================

    except Exception as error:

        db.rollback()


        logger.exception(
            "❌ Error inside "
            "send_pending_notifications: %s",
            error,
        )


        raise


    # ========================================================
    # CLOSE DATABASE SESSION
    # ========================================================

    finally:

        db.close()