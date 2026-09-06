from app.database.database import SessionLocal

from app.models.notification import Notification
from app.models.internship import Internship

import logging
logger = logging.getLogger(__name__)
# ============================================================
# BUILD ONE EMAIL FOR ONE USER
# ============================================================

def build_user_notification_email(
    user_email,
    notifications
):

    db = SessionLocal()

    try:

        jobs = []

        for notification in notifications:

            internship = (
                db.query(Internship)
                .filter(
                    Internship.id == notification.job_id
                )
                .first()
            )

            if not internship:
                continue

            jobs.append({
                "company": internship.company,
                "title": internship.title,
                "location": internship.location,
                "url": internship.url,
                "score": notification.relevance_score
            })

        total_jobs = len(jobs)

        # ----------------------------------------------------
        # EMAIL SUBJECT
        # ----------------------------------------------------

        subject = (
            f"🎓 {total_jobs} New Internship"
            f"{'s' if total_jobs != 1 else ''} "
            f"for You"
        )

        # ----------------------------------------------------
        # EMAIL BODY
        # ----------------------------------------------------

        body = []

        body.append(
            f"Hi,\n\n"
            f"We found {total_jobs} new internship"
            f"{'s' if total_jobs != 1 else ''} "
            f"matching your subscription.\n"
        )

        body.append(
            "\n" + "=" * 60 + "\n"
        )

        for index, job in enumerate(
            jobs,
            start=1
        ):

            body.append(
                f"\n{index}. {job['title']}\n"
                f"🏢 Company: {job['company']}\n"
                f"📍 Location: {job['location']}\n"
                f"📊 Relevance Score: "
                f"{job['score']}\n"
                f"🔗 Apply: {job['url']}\n"
            )

            body.append(
                "-" * 60 + "\n"
            )

        body.append(
            "\nGood luck with your applications! 🚀\n"
        )

        body.append(
            "\n— Internship Notifier"
        )

        return {
            "to": user_email,
            "subject": subject,
            "body": "".join(body)
        }

    finally:

        db.close()
# ============================================================
# TEST EMAIL BUILDER
# ============================================================

# ============================================================
# TEST TOP 15 EMAIL FLOW
# ============================================================

def test_email_builder():

    db = SessionLocal()

    try:

        notifications = (
            db.query(Notification)
            .filter(
                Notification.status == "PENDING"
            )
            .all()
        )

        if not notifications:

            logger.info(
    "No pending notifications found"
)

            return

        # ----------------------------------------------------
        # GROUP BY USER
        # ----------------------------------------------------

        grouped = {}

        for notification in notifications:

            email = notification.user_email

            if email not in grouped:
                grouped[email] = []

            grouped[email].append(
                notification
            )

        # ----------------------------------------------------
        # BUILD ONE EMAIL PER USER
        # ----------------------------------------------------

        for email, user_notifications in grouped.items():

            total_pending = len(
                user_notifications
            )

            # ------------------------------------------------
            # SORT
            # ------------------------------------------------
            #
            # Highest relevance first.
            # If relevance is equal, newest first.
            # ------------------------------------------------

            user_notifications.sort(
                key=lambda x: (
                    x.relevance_score or 0,
                    x.created_at
                ),
                reverse=True
            )

            # ------------------------------------------------
            # TOP 15
            # ------------------------------------------------

            top_notifications = (
                user_notifications[:15]
            )

            # ------------------------------------------------
            # BUILD EMAIL
            # ------------------------------------------------

            email_data = build_user_notification_email(
                email,
                top_notifications
            )

            print("\n" + "=" * 70)

            print(
                "📧 EMAIL PREVIEW"
            )

            print(
                "=" * 70
            )

            print(
                f"To: {email_data['to']}"
            )

            print(
                f"Subject: {email_data['subject']}"
            )

            print(
                f"\n📦 Pending internships: "
                f"{total_pending}"
            )

            print(
                f"📦 Selected for email: "
                f"{len(top_notifications)}"
            )

            if total_pending > 15:

                print(
                    f"\n⚠️ Showing "
                    f"{len(top_notifications)} "
                    f"of {total_pending} "
                    f"pending internships."
                )

            print(
                "\n" + email_data["body"]
            )

            print(
                "=" * 70
            )

    finally:

        db.close()


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    test_email_builder()
# ============================================================
# RUN DIRECTLY
# ============================================================

