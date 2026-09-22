# ============================================================
# EMAIL SERVICE DIGEST TEST
# File: test_email_service.py
# ============================================================

from datetime import datetime, timezone
import os
from unittest.mock import patch, MagicMock

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
# BREVO MOCK HELPER
# ============================================================

class BrevoPatcher:
    """Concrete patcher wrapper used to mock Brevo requests in tests."""

    def __init__(self):
        self._patcher = patch(
            "app.services.email_service.requests.post"
        )
        self.new = None

    def start(self):
        self.new = self._patcher.start()
        return self

    def stop(self):
        self._patcher.stop()

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.stop()
        return False


def brevo_mock():

    brevo_patcher = BrevoPatcher().start()

    env_patcher = patch.dict(
        os.environ,
        {
            "BREVO_API_KEY": "test-brevo-api-key",
            "FROM_EMAIL": "test@example.com",
        },
    )

    env_patcher.start()

    mock_post = brevo_patcher.new

    mock_response = MagicMock()

    mock_response.json.return_value = {
        "messageId": "test-brevo-message-id"
    }

    mock_response.raise_for_status.return_value = None

    mock_post.return_value = mock_response

    return brevo_patcher, env_patcher, mock_post
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

    brevo_patcher, env_patcher, mock_post = brevo_mock()
    try:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

    finally:

        brevo_patcher.stop()
        env_patcher.stop()

    assert response is True

    mock_post.assert_called_once()

    print("✅ Email function returned successfully.")
    print("✅ Brevo API was called exactly once.")


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

    brevo_patcher, env_patcher, mock_post = brevo_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        payload = mock_post.call_args.kwargs["json"]

    finally:

        brevo_patcher.stop()
        env_patcher.stop()
    assert response is True

    email_html = payload["htmlContent"]

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
    brevo_patcher, env_patcher, mock_post = brevo_mock()
    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        payload = mock_post.call_args.kwargs["json"]

    finally:

        brevo_patcher.stop()
        env_patcher.stop()
    html = payload["htmlContent"]

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

    brevo_patcher, env_patcher, mock_post = brevo_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        payload = mock_post.call_args.kwargs["json"]

    finally:

      brevo_patcher.stop()
      env_patcher.stop()
      html = payload["htmlContent"]

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

    brevo_patcher, env_patcher, mock_post = brevo_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        payload = mock_post.call_args.kwargs["json"]
        headers = mock_post.call_args.kwargs["headers"]

    finally:

        brevo_patcher.stop()
        env_patcher.stop()

    assert payload["to"][0]["email"] == TEST_EMAIL
    assert payload["subject"] is not None

    assert headers["idempotency-key"] == TEST_IDEMPOTENCY_KEY

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

    brevo_patcher, env_patcher, mock_post = brevo_mock()

    try:

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )

        payload = mock_post.call_args.kwargs["json"]

    finally:

        brevo_patcher.stop()
        env_patcher.stop()

    html = payload["htmlContent"]

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

    brevo_patcher, env_patcher, mock_post = brevo_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            None
        )

    finally:

        brevo_patcher.stop()
        env_patcher.stop()

    assert response is None

    mock_post.assert_not_called()

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

    brevo_patcher, env_patcher, mock_post = brevo_mock()

    try:

        response = send_notification_email(
            TEST_EMAIL,
            [],
            TEST_IDEMPOTENCY_KEY
        )

    finally:

        brevo_patcher.stop()
        env_patcher.stop()

    assert response is None

    mock_post.assert_not_called()

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
        "⚠️ Brevo API is MOCKED."
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