# ============================================================
# EMAIL SERVICE
# File: app/services/email_service.py
# ============================================================

import os
import html
import logging

from datetime import datetime, timezone

import resend

from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

MAX_INTERNSHIPS_PER_EMAIL = 15


# ============================================================
# API KEY
# ============================================================

def _get_api_key() -> str:

    if not resend.api_key:

        resend.api_key = os.getenv(
            "RESEND_API_KEY"
        )

    return resend.api_key


# ============================================================
# HTML ESCAPE
# ============================================================

def _escape(value) -> str:

    if value is None:

        return ""

    return html.escape(
        str(value)
    )


# ============================================================
# OBJECT / DICT FIELD HELPER
# ============================================================

def _get_field(
    obj,
    key,
    default=None
):

    if isinstance(
        obj,
        dict
    ):

        return obj.get(
            key,
            default
        )

    return getattr(
        obj,
        key,
        default
    )


# ============================================================
# CREATED AT SORT VALUE
# ============================================================

def _created_sort_value(
    internship
) -> float:

    created_at = _get_field(
        internship,
        "created_at",
        None
    )

    if created_at is None:

        return float("-inf")


    # --------------------------------------------------------
    # Datetime
    # --------------------------------------------------------

    if isinstance(
        created_at,
        datetime
    ):

        try:

            if created_at.tzinfo is None:

                created_at = created_at.replace(
                    tzinfo=timezone.utc
                )

            return created_at.timestamp()

        except Exception:

            return float("-inf")


    # --------------------------------------------------------
    # Numeric timestamp
    # --------------------------------------------------------

    if isinstance(
        created_at,
        (int, float)
    ):

        return float(
            created_at
        )


    # --------------------------------------------------------
    # ISO string
    # --------------------------------------------------------

    if isinstance(
        created_at,
        str
    ):

        try:

            parsed = datetime.fromisoformat(
                created_at.replace(
                    "Z",
                    "+00:00"
                )
            )

            if parsed.tzinfo is None:

                parsed = parsed.replace(
                    tzinfo=timezone.utc
                )

            return parsed.timestamp()

        except Exception:

            return float("-inf")


    return float("-inf")


# ============================================================
# SORT KEY
# ============================================================

def _sort_key(
    internship
):

    relevance = (
        _get_field(
            internship,
            "relevance_score",
            0
        )
        or 0
    )

    try:

        relevance = float(
            relevance
        )

    except (
        TypeError,
        ValueError
    ):

        relevance = 0.0


    created_value = (
        _created_sort_value(
            internship
        )
    )


    return (
        relevance,
        created_value
    )


# ============================================================
# PRIORITIZE INTERNSHIPS
# ============================================================

def _prioritize_internships(
    internships,
    limit=MAX_INTERNSHIPS_PER_EMAIL
):

    if not internships:

        return []


    new_internships = []

    old_internships = []


    # ========================================================
    # SEPARATE NEW AND OLD
    # ========================================================

    for internship in internships:

        is_new = bool(
            _get_field(
                internship,
                "is_new",
                False
            )
        )

        if is_new:

            new_internships.append(
                internship
            )

        else:

            old_internships.append(
                internship
            )


    # ========================================================
    # SORT
    #
    # Higher relevance first.
    #
    # If relevance is equal:
    # newer internship first.
    #
    # ========================================================

    new_internships.sort(
        key=_sort_key,
        reverse=True
    )

    old_internships.sort(
        key=_sort_key,
        reverse=True
    )


    # ========================================================
    # NEW FIRST
    # ========================================================

    prioritized = (
        new_internships
        +
        old_internships
    )


    return prioritized[
        :limit
    ]


# ============================================================
# SEND SINGLE INTERNSHIP EMAIL
# ============================================================

def send_internship_email(
    recipient_email: str,
    company: str,
    title: str,
    location: str,
    url: str
):

    # ========================================================
    # API KEY
    # ========================================================

    if not _get_api_key():

        logger.error(
            "❌ RESEND_API_KEY is missing."
        )

        return None


    # ========================================================
    # RECIPIENT
    # ========================================================

    if not recipient_email:

        logger.error(
            "❌ Recipient email is missing."
        )

        return None


    # ========================================================
    # ESCAPE INPUT
    # ========================================================

    safe_company = _escape(
        company
    )

    safe_title = _escape(
        title
    )

    safe_location = (
        _escape(location)
        or "Location not specified"
    )

    safe_url = _escape(
        url
    )


    # ========================================================
    # FROM EMAIL
    # ========================================================

    from_email = os.getenv(
        "FROM_EMAIL"
    )

    if not from_email:

        logger.error(
            "❌ FROM_EMAIL environment variable "
            "is not configured."
        )

        return None


    # ========================================================
    # SEND
    # ========================================================

    try:

        response = resend.Emails.send(

            {

                "from": from_email,

                "to": [
                    recipient_email
                ],

                "subject": (
                    f"New {safe_company} "
                    f"Internship Found!"
                ),

                "html": f"""
                <html>

                <body
                    style="
                        font-family:Arial,sans-serif;
                        line-height:1.6;
                    "
                >

                    <h2>
                        🎉 New Internship Found!
                    </h2>

                    <p>
                        A new internship matching
                        your subscription has been found.
                    </p>

                    <hr>

                    <p>
                        <strong>Company:</strong>
                        {safe_company}
                    </p>

                    <p>
                        <strong>Role:</strong>
                        {safe_title}
                    </p>

                    <p>
                        <strong>Location:</strong>
                        {safe_location}
                    </p>

                    <br>

                    <p>

                        <a
                            href="{safe_url}"
                            target="_blank"
                        >
                            👉 View Internship
                        </a>

                    </p>

                    <hr>

                    <p>
                        Internship Notifier 🤖
                    </p>

                </body>

                </html>
                """
            }
        )


        logger.info(
            "📧 Single internship email sent"
        )


        return response


    except Exception as error:

        logger.error(
            "❌ Failed to send single internship email: %s",
            error
        )

        return None


# ============================================================
# SEND COMBINED NOTIFICATION DIGEST
# ============================================================

def send_notification_email(
    recipient_email: str,
    internships: list,
    idempotency_key: str
):

    # ========================================================
    # API KEY
    # ========================================================

    if not _get_api_key():

        logger.error(
            "❌ RESEND_API_KEY is missing."
        )

        return None


    # ========================================================
    # RECIPIENT
    # ========================================================

    if not recipient_email:

        logger.error(
            "❌ Recipient email is missing."
        )

        return None


    # ========================================================
    # IDEMPOTENCY KEY
    # ========================================================

    if not idempotency_key:

        logger.error(
            "❌ Idempotency key is missing."
        )

        return None


    idempotency_key = str(
        idempotency_key
    )


    if len(
        idempotency_key
    ) > 256:

        logger.error(
            "❌ Idempotency key is longer "
            "than 256 characters."
        )

        return None


    # ========================================================
    # INPUT
    # ========================================================

    if not internships:

        logger.warning(
            "⚠️ No internships to send."
        )

        return None


    # ========================================================
    # PRIORITIZE
    #
    # NEW FIRST
    # THEN OLD
    # MAX 15
    # ========================================================

    selected_internships = (
        _prioritize_internships(
            internships,
            MAX_INTERNSHIPS_PER_EMAIL
        )
    )


    if not selected_internships:

        logger.warning(
            "⚠️ No eligible internships "
            "after prioritization."
        )

        return None


    # ========================================================
    # COUNTS
    # ========================================================

    new_count = sum(

        1

        for internship
        in selected_internships

        if bool(
            _get_field(
                internship,
                "is_new",
                False
            )
        )
    )


    old_count = (
        len(
            selected_internships
        )
        - new_count
    )


    total_count = len(
        selected_internships
    )


    logger.info(
        "📧 Preparing digest | "
        "Total=%s | New=%s | Old=%s",
        total_count,
        new_count,
        old_count
    )


    # ========================================================
    # SUBJECT
    # ========================================================

    if new_count > 0:

        subject = (
            f"🎓 {new_count} New Internship"
            f"{'s' if new_count != 1 else ''}"
            f" + More Opportunities"
        )

    else:

        subject = (
            f"🎓 {total_count} Internship"
            f"{'s' if total_count != 1 else ''}"
            f" for You"
        )


    # ========================================================
    # BUILD HTML
    # ========================================================

    internship_html = []


    for index, internship in enumerate(
        selected_internships,
        start=1
    ):

        title = _escape(
            _get_field(
                internship,
                "title",
                ""
            )
        )


        company = _escape(
            _get_field(
                internship,
                "company",
                ""
            )
        )


        location = (
            _escape(
                _get_field(
                    internship,
                    "location",
                    ""
                )
            )
            or "Location not specified"
        )


        url = _escape(
            _get_field(
                internship,
                "url",
                ""
            )
        )


        relevance_score = (
            _get_field(
                internship,
                "relevance_score",
                0
            )
            or 0
        )


        is_new = bool(
            _get_field(
                internship,
                "is_new",
                False
            )
        )


        # ====================================================
        # BADGE
        # ====================================================

        if is_new:

            badge = """
            <span
                style="
                    background:#16a34a;
                    color:white;
                    padding:4px 8px;
                    border-radius:5px;
                    font-size:12px;
                    font-weight:bold;
                "
            >
                🆕 NEW
            </span>
            """

        else:

            badge = """
            <span
                style="
                    background:#6b7280;
                    color:white;
                    padding:4px 8px;
                    border-radius:5px;
                    font-size:12px;
                "
            >
                Previous
            </span>
            """


        internship_html.append(
            f"""
            <div
                style="
                    margin-bottom:25px;
                    padding:18px;
                    border:1px solid #ddd;
                    border-radius:8px;
                "
            >

                <h3>
                    {index}. {title}
                    &nbsp;
                    {badge}
                </h3>

                <p>
                    🏢
                    <strong>Company:</strong>
                    {company}
                </p>

                <p>
                    📍
                    <strong>Location:</strong>
                    {location}
                </p>

                <p>
                    📊
                    <strong>Relevance Score:</strong>
                    {relevance_score}
                </p>

                <p>

                    <a
                        href="{url}"
                        target="_blank"
                    >
                        👉 View Internship
                    </a>

                </p>

            </div>
            """
        )


    internship_html = "".join(
        internship_html
    )


    # ========================================================
    # NEW JOB MESSAGE
    # ========================================================

    if new_count > 0:

        new_header = """
        <p>
            <strong>
                🆕 New internships are shown first.
            </strong>
        </p>
        """

    else:

        new_header = ""


    # ========================================================
    # FINAL EMAIL HTML
    # ========================================================

    opportunity_word = (
        "opportunities"
        if total_count != 1
        else "opportunity"
    )


    email_html = f"""
    <html>

    <body
        style="
            font-family:Arial,sans-serif;
            line-height:1.6;
            color:#222;
        "
    >

        <h2>
            🎓 Internship Notifier
        </h2>

        <p>
            Hi,
        </p>

        <p>
            We found
            <strong>{total_count}</strong>
            internship
            {opportunity_word}
            matching your subscriptions.
        </p>

        {new_header}

        <hr>

        {internship_html}

        <p>
            Good luck with your applications! 🚀
        </p>

        <p>
            — Internship Notifier
        </p>

    </body>

    </html>
    """


    # ========================================================
    # FROM EMAIL
    # ========================================================

    from_email = os.getenv(
        "FROM_EMAIL"
    )

    if not from_email:

        logger.error(
            "❌ FROM_EMAIL environment variable "
            "is not configured."
        )

        return None


    # ========================================================
    # SEND DIGEST
    # ========================================================

    try:

        logger.info(
            "🔐 Sending digest email"
        )


        response = resend.Emails.send(

            {

                "from": from_email,

                "to": [
                    recipient_email
                ],

                "subject": subject,

                "html": email_html,

            },

            {

                "idempotencyKey":
                    idempotency_key

            }
        )


        logger.info(
            "✅ Digest email accepted by Resend"
        )


        return response


    except Exception as error:

        logger.error(
            "❌ Failed to send digest email: %s",
            error
        )

        return None