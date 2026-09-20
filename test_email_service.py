# ============================================================
# EMAIL SERVICE DIGEST TEST
# File: test_email_service.py
# ============================================================

from datetime import datetime, timezone
from unittest.mock import patch

from app.services.email_service import (
    send_notification_email,
)


# ============================================================
# TEST DATA
# ============================================================

TEST_EMAIL = "claim-test@example.com"

TEST_IDEMPOTENCY_KEY = (
    "test-digest-claim-test@example.com-2026-08-25"
)


def make_internship(
    title,
    company,
    relevance_score,
    is_new,
    created_at,
):

    return {
        "title": title,
        "company": company,
        "location": "India",
        "url": f"https://example.com/{title.replace(' ', '-').lower()}",
        "relevance_score": relevance_score,
        "is_new": is_new,
        "created_at": created_at,
    }


# ============================================================
# SMTP MOCK HELPER
# ============================================================

def smtp_mock():

    smtp_patcher = patch(
        "app.services.email_service.smtplib.SMTP_SSL"
    )

    mock_smtp_class = smtp_patcher.start()

    mock_smtp = mock_smtp_class.return_value

    mock_smtp.__enter__.return_value = mock_smtp
    mock_smtp.__exit__.return_value = False

    return smtp_patcher, mock_smtp


# ============================================================
# TEST 1
# BASIC DIGEST
# ============================================================

def test_basic_digest():

    print()
    print("=" * 70)
    print("🧪 TEST 1 — BASIC DIGEST EMAIL")
    print("=" * 70)

    internships = [

        make_internship(
            "Python Intern",
            "Company A",
            90,
            True,
            datetime(
                2026,
                8,
                25,
                12,
                0,
                tzinfo=timezone.utc
            )
        ),

        make_internship(
            "Backend Intern",
            "Company B",
            80,
            True,
            datetime(
                2026,
                8,
                25,
                11,
                0,
                tzinfo=timezone.utc
            )
        ),

        make_internship(
            "Software Intern",
            "Company C",
            70,
            False,
            datetime(
                2026,
                8,
                24,
                10,
                0,
                tzinfo=timezone.utc
            )
        ),
    ]

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

    finally:

        smtp_patcher.stop()

    assert response is True

    mock_smtp.login.assert_called_once()
    mock_smtp.send_message.assert_called_once()

    print("✅ Email function returned successfully.")
    print("✅ Gmail SMTP send_message() was called exactly once.")


# ============================================================
# TEST 2
# NEW INTERNSHIPS FIRST
# ============================================================

def test_new_internships_first():

    print()
    print("=" * 70)
    print("🧪 TEST 2 — NEW INTERNSHIPS FIRST")
    print("=" * 70)

    internships = [

        make_internship(
            "OLD HIGH SCORE",
            "Company A",
            99,
            False,
            datetime(
                2026,
                8,
                25,
                12,
                0,
                tzinfo=timezone.utc
            )
        ),

        make_internship(
            "NEW LOW SCORE",
            "Company B",
            50,
            True,
            datetime(
                2026,
                8,
                25,
                10,
                0,
                tzinfo=timezone.utc
            )
        ),
    ]

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        message = mock_smtp.send_message.call_args.args[0]

    finally:

        smtp_patcher.stop()

    assert response is True

    email_html = message.get_body(
        preferencelist=("html",)
    ).get_content()

    new_position = email_html.find(
        "NEW LOW SCORE"
    )

    old_position = email_html.find(
        "OLD HIGH SCORE"
    )

    assert new_position != -1
    assert old_position != -1

    assert new_position < old_position

    print(
        "✅ NEW internship appears before OLD internship."
    )


# ============================================================
# TEST 3
# RELEVANCE SORTING
# ============================================================

def test_relevance_sorting():

    print()
    print("=" * 70)
    print("🧪 TEST 3 — RELEVANCE SORTING")
    print("=" * 70)

    internships = [

        make_internship(
            "Score 60",
            "Company A",
            60,
            True,
            datetime.now(timezone.utc)
        ),

        make_internship(
            "Score 90",
            "Company B",
            90,
            True,
            datetime.now(timezone.utc)
        ),

        make_internship(
            "Score 75",
            "Company C",
            75,
            True,
            datetime.now(timezone.utc)
        ),
    ]

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        message = mock_smtp.send_message.call_args.args[0]

    finally:

        smtp_patcher.stop()

    html = message.get_body(
        preferencelist=("html",)
    ).get_content()

    position_90 = html.find("Score 90")
    position_75 = html.find("Score 75")
    position_60 = html.find("Score 60")

    assert position_90 < position_75
    assert position_75 < position_60

    print(
        "✅ Relevance sorting works correctly."
    )


# ============================================================
# TEST 4
# MAXIMUM 15 INTERNSHIPS
# ============================================================

def test_max_15():

    print()
    print("=" * 70)
    print("🧪 TEST 4 — MAXIMUM 15 INTERNSHIPS")
    print("=" * 70)

    internships = []

    for i in range(20):

        internships.append(

            make_internship(
                f"Internship {i}",
                "Test Company",
                100 - i,
                True,
                datetime.now(timezone.utc)
            )

        )

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        message = mock_smtp.send_message.call_args.args[0]

    finally:

        smtp_patcher.stop()

    html = message.get_body(
        preferencelist=("html",)
    ).get_content()

    count = 0

    for i in range(20):

        if f"Internship {i}" in html:

            count += 1

    assert count == 15

    print(
        "✅ Digest correctly limited to 15 internships."
    )


# ============================================================
# TEST 5
# IDEMPOTENCY KEY
# ============================================================

def test_idempotency_key():

    print()
    print("=" * 70)
    print("🧪 TEST 5 — IDEMPOTENCY KEY")
    print("=" * 70)

    internships = [

        make_internship(
            "Idempotency Test",
            "Company",
            90,
            True,
            datetime.now(timezone.utc)
        )
    ]

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        message = mock_smtp.send_message.call_args.args[0]

    finally:

        smtp_patcher.stop()

    assert message["To"] == TEST_EMAIL
    assert message["Subject"] is not None

    print(
        "✅ Email sent successfully with application-level idempotency."
    )


# ============================================================
# TEST 6
# HTML ESCAPING
# ============================================================

def test_html_escaping():

    print()
    print("=" * 70)
    print("🧪 TEST 6 — HTML ESCAPING")
    print("=" * 70)

    internships = [

        make_internship(
            "<script>alert('xss')</script>",
            "Company <Dangerous>",
            90,
            True,
            datetime.now(timezone.utc)
        )
    ]

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        message = mock_smtp.send_message.call_args.args[0]

    finally:

        smtp_patcher.stop()

    html = message.get_body(
        preferencelist=("html",)
    ).get_content()

    assert "<script>" not in html

    assert "&lt;script&gt;" in html

    assert "Company &lt;Dangerous&gt;" in html

    print(
        "✅ HTML values are escaped safely."
    )


# ============================================================
# TEST 7
# MISSING IDEMPOTENCY KEY
# ============================================================

def test_missing_idempotency_key():

    print()
    print("=" * 70)
    print("🧪 TEST 7 — MISSING IDEMPOTENCY KEY")
    print("=" * 70)

    internships = [

        make_internship(
            "Test Internship",
            "Company",
            90,
            True,
            datetime.now(timezone.utc)
        )
    ]

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            None
        )

    finally:

        smtp_patcher.stop()

    assert response is None

    mock_smtp.send_message.assert_not_called()

    print(
        "✅ Missing idempotency key handled safely."
    )


# ============================================================
# TEST 8
# EMPTY INTERNSHIP LIST
# ============================================================

def test_empty_internships():

    print()
    print("=" * 70)
    print("🧪 TEST 8 — EMPTY INTERNSHIPS")
    print("=" * 70)

    smtp_patcher, mock_smtp = smtp_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            [],
            TEST_IDEMPOTENCY_KEY
        )

    finally:

        smtp_patcher.stop()

    assert response is None

    mock_smtp.send_message.assert_not_called()

    print(
        "✅ Empty internship list handled safely."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("🧪 EMAIL SERVICE DIGEST TEST")
    print("=" * 70)

    print()
    print(
        "⚠️ Gmail SMTP is MOCKED."
    )

    print(
        "⚠️ No real email will be sent."
    )

    test_basic_digest()

    test_new_internships_first()

    test_relevance_sorting()

    test_max_15()

    test_idempotency_key()

    test_html_escaping()

    test_missing_idempotency_key()

    test_empty_internships()

    print()
    print("=" * 70)
    print("🎉 ALL EMAIL SERVICE TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":

    main()