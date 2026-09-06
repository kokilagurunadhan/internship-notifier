from app.database.database import SessionLocal

from app.models.notification import Notification
from app.models.internship import Internship
from app.models.subscription import Subscription
import logging
logger = logging.getLogger(__name__)
from app.services.relevance_engine import (
    calculate_relevance_score
)


# ============================================================
# CALCULATE RELEVANCE SCORES
# ============================================================

def calculate_pending_notification_scores():

    db = SessionLocal()

    try:

        notifications = (
            db.query(Notification)
            .filter(
                Notification.status == "PENDING"
            )
            .all()
        )

        logger.info(
    "Calculating relevance for pending notifications",
    extra={
        "pending_notifications": len(notifications),
    },
)

        for notification in notifications:

            internship = (
                db.query(Internship)
                .filter(
                    Internship.id == notification.job_id
                )
                .first()
            )

            if not internship:

                logger.warning(
    "Internship not found for notification",
    extra={
        "notification_id": notification.id,
        "internship_id": notification.job_id,
    },
)

                continue

            subscription = (
    db.query(Subscription)
    .filter(
        Subscription.id
        == notification.subscription_id,

        Subscription.is_active == True
    )
    .first()
)
            if not subscription:

                logger.warning(
    "Active subscription not found for notification",
    extra={
        "notification_id": notification.id,
        "subscription_id": notification.subscription_id,
    },
)

                continue

            user_domain = subscription.domain

            result = calculate_relevance_score(

                job_title=internship.title,

                job_description=(
                    internship.description or ""
                ),

                user_domain=user_domain
            )

            notification.relevance_score = (
                result["final_score"]
            )

            logger.debug(
    "Notification relevance score calculated",
    extra={
        "notification_id": notification.id,
        "internship_id": internship.id,
        "relevance_score": round(
            float(result["final_score"]),
            2,
        ),
    },
)

        db.commit()

        logger.info(
    "Relevance scores calculated"
)

    except Exception as error:

        db.rollback()

        logger.exception(
            "Failed to calculate notification relevance"
        )

        raise

    finally:

        db.close()


# ============================================================
# GET TOP 15 PENDING NOTIFICATIONS
# ============================================================

# ============================================================
# GET TOP 15 PENDING NOTIFICATIONS
# WITH ANTI-STARVATION
# ============================================================

def get_top_pending_notifications(limit=15):

    db = SessionLocal()

    try:

        notifications = (
            db.query(Notification)
            .filter(
                Notification.status == "PENDING"
            )
            .all()
        )

        # ----------------------------------------------------
        # GROUP BY USER
        # ----------------------------------------------------

        grouped = {}

        for notification in notifications:

            email = notification.user_email

            if email not in grouped:
                grouped[email] = []

            grouped[email].append(notification)

        # ----------------------------------------------------
        # SORT EACH USER
        # ----------------------------------------------------

        results = {}

        for email, user_notifications in grouped.items():

            # ------------------------------------------------
            # NORMAL RELEVANCE + FRESHNESS SORT
            # ------------------------------------------------

            user_notifications.sort(
                key=lambda x: (
                    x.relevance_score or 0,
                    x.created_at
                ),
                reverse=True
            )

            # ------------------------------------------------
            # ANTI-STARVATION
            # ------------------------------------------------
            #
            # If a notification has been waiting for a long
            # time, move it into the selection pool.
            #
            # This prevents old jobs from being forgotten
            # forever.
            # ------------------------------------------------

            if len(user_notifications) > limit:

                oldest = min(
                    user_notifications,
                    key=lambda x: x.created_at
                )

                top_notifications = (
                    user_notifications[:limit]
                )

                # Check whether the oldest notification
                # is already inside the Top 15.

                if oldest not in top_notifications:

                    # Remove the lowest-ranked item.

                    top_notifications[-1] = oldest

                    # Sort again so the returned list remains
                    # properly ordered.

                    top_notifications.sort(
                        key=lambda x: (
                            x.relevance_score or 0,
                            x.created_at
                        ),
                        reverse=True
                    )

                results[email] = top_notifications

            else:

                results[email] = user_notifications

        return results

    finally:

        db.close()
# ============================================================
# PRINT TOP 15
# ============================================================

def print_top_pending_notifications():

    results = get_top_pending_notifications(
        limit=15
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "📦 TOP PENDING NOTIFICATIONS"
    )

    print(
        "=" * 70
    )

    for email, notifications in results.items():

        print(
            f"\n📧 User: {email}"
        )

        print(
            f"📦 Showing: "
            f"{len(notifications)} notification(s)"
        )

        for index, notification in enumerate(
            notifications,
            start=1
        ):

            print(
                f"{index}. "
                f"Job ID: {notification.job_id} | "
                f"Score: {notification.relevance_score} | "
                f"Created: {notification.created_at}"
            )

    print(
        "\n" + "=" * 70
    )


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    calculate_pending_notification_scores()

    print_top_pending_notifications()