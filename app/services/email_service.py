# ============================================================
# EMAIL SERVICE
# File: app/services/email_service.py
# ============================================================

import os
import html
import logging


from datetime import datetime, timezone
import requests

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
# bervo  CONFIGURATION
# ============================================================

# ============================================================
# BREVO API CONFIGURATION
# ============================================================

def _get_brevo_config():

    api_key = os.getenv("BREVO_API_KEY")
    from_email = os.getenv("FROM_EMAIL")

    if not api_key:
        logger.error(
            "❌ BREVO_API_KEY environment variable is missing."
        )
        return None

    if not from_email:
        logger.error(
            "❌ FROM_EMAIL environment variable is missing."
        )
        return None

    return api_key, from_email
# ============================================================
# SEND EMAIL THROUGH BREVO HTTPS API
# ============================================================

def _send_via_brevo(
    api_key: str,
    from_email: str,
    recipient_email: str,
    subject: str,
    text_content: str,
    html_content: str,
    idempotency_key: str | None = None
):

    payload = {
        "sender": {
            "name": "Internship Notifier",
            "email": from_email
        },
        "to": [
            {
                "email": recipient_email
            }
        ],
        "subject": subject,
        "textContent": text_content,
        "htmlContent": html_content
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key
    }

    if idempotency_key:
        headers["idempotency-key"] = str(idempotency_key)

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers=headers,
        json=payload,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    logger.info(
        "✅ Brevo accepted email | messageId=%s",
        data.get("messageId")
    )

    return True
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
    # BREVO CONFIGURATION
    # ========================================================

    brevo_config = _get_brevo_config()

    if not brevo_config:
        return None

    (
        api_key,
        from_email
    ) = brevo_config

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

    safe_company = _escape(company)

    safe_title = _escape(title)

    safe_location = (
        _escape(location)
        or "Location not specified"
    )

    safe_url = _escape(url)

    # ========================================================
    # SUBJECT
    # ========================================================

    subject = (
        f"New {safe_company} "
        f"Internship Found!"
    )

    # ========================================================
    # PLAIN TEXT CONTENT
    # ========================================================

    text_content = (
        "A new internship matching "
        "your subscription has been found.\n\n"
        f"Company: {company}\n"
        f"Role: {title}\n"
        f"Location: {location or 'Location not specified'}\n"
        f"View Internship: {url}\n\n"
        "Internship Notifier 🤖"
    )

    # ========================================================
    # HTML CONTENT
    # ========================================================

    html_content = f"""
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

    # ========================================================
    # SEND THROUGH BREVO
    # ========================================================

    try:

        logger.info(
            "📧 Sending single internship email via Brevo"
        )

        return _send_via_brevo(
            api_key=api_key,
            from_email=from_email,
            recipient_email=recipient_email,
            subject=subject,
            text_content=text_content,
            html_content=html_content
        )

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
    # BREVO CONFIGURATION
    # ========================================================

    brevo_config = _get_brevo_config()

    if not brevo_config:
        return None

    (
        api_key,
        from_email
    ) = brevo_config

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
    #
    # Kept because the dispatcher passes it.
    # Actual application-level idempotency is handled
    # by the notification database state.
    #
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
    #
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
    # PLAIN TEXT CONTENT
    # ========================================================

    text_content = (
        f"We found {total_count} "
        f"internship {opportunity_word} "
        "matching your subscriptions.\n\n"
        "Please open the HTML version of this "
        "email to view the internship links.\n\n"
        "— Internship Notifier"
    )

    # ========================================================
    # SEND DIGEST THROUGH BREVO
    # ========================================================

    try:

        logger.info(
            "🔐 Sending digest email via Brevo | "
            "Idempotency=%s",
            idempotency_key
        )

        return _send_via_brevo(
            api_key=api_key,
            from_email=from_email,
            recipient_email=recipient_email,
            subject=subject,
            text_content=text_content,
            html_content=email_html,
            idempotency_key=idempotency_key
        )

    except Exception as error:

        logger.error(
            "❌ Failed to send digest email: %s",
            error
        )

        return None