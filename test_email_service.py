# ============================================================
# EMAIL SERVICE DIGEST TEST
# File: test_email_service.py
# ============================================================

import os
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


    fake_response = {
        "id": "fake-resend-email-id"
    }


    with patch(
        "app.services.email_service.resend.Emails.send",
        return_value=fake_response
    ) as mock_send:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )


    assert response == fake_response

    mock_send.assert_called_once()

    print("✅ Email function returned successfully.")
    print("✅ Resend API was called exactly once.")


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


    captured_payload = {}


    def fake_send(*args):

        captured_payload["args"] = args

        return {
            "id": "fake-id"
        }


    with patch(
        "app.services.email_service.resend.Emails.send",
        side_effect=fake_send
    ):

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )


    assert response["id"] == "fake-id"


    payload = captured_payload["args"][0]

    email_html = payload["html"]


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


    captured = {}


    def fake_send(*args):

        captured["payload"] = args[0]

        return {
            "id": "fake-id"
        }


    with patch(
        "app.services.email_service.resend.Emails.send",
        side_effect=fake_send
    ):

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )


    html = captured["payload"]["html"]


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


    captured = {}


    def fake_send(*args):

        captured["payload"] = args[0]

        return {
            "id": "fake-id"
        }


    with patch(
        "app.services.email_service.resend.Emails.send",
        side_effect=fake_send
    ):

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )


    html = captured["payload"]["html"]


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


    captured = {}


    def fake_send(*args):

        captured["args"] = args

        return {
            "id": "fake-id"
        }


    with patch(
        "app.services.email_service.resend.Emails.send",
        side_effect=fake_send
    ):

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )


    args = captured["args"]


    assert len(args) == 2


    options = args[1]


    assert (
        options["idempotencyKey"]
        == TEST_IDEMPOTENCY_KEY
    )


    print(
        "✅ Idempotency key passed correctly."
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


    captured = {}


    def fake_send(*args):

        captured["payload"] = args[0]

        return {
            "id": "fake-id"
        }


    with patch(
        "app.services.email_service.resend.Emails.send",
        side_effect=fake_send
    ):

        send_notification_email(
            TEST_EMAIL,
            internships,
            TEST_IDEMPOTENCY_KEY
        )


    html = captured["payload"]["html"]


    assert (
        "<script>"
        not in html
    )


    assert (
        "&lt;script&gt;"
        in html
    )


    assert (
        "Company &lt;Dangerous&gt;"
        in html
    )


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


    with patch(
        "app.services.email_service.resend.Emails.send"
    ) as mock_send:

        response = send_notification_email(
            TEST_EMAIL,
            internships,
            None
        )


    assert response is None

    mock_send.assert_not_called()


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
    print("🧪 TEST 8 — EMPTY INTERNSHIP LIST")
    print("=" * 70)


    with patch(
        "app.services.email_service.resend.Emails.send"
    ) as mock_send:

        response = send_notification_email(
            TEST_EMAIL,
            [],
            TEST_IDEMPOTENCY_KEY
        )


    assert response is None

    mock_send.assert_not_called()


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
        "⚠️ Resend API is MOCKED."
    )

    print(
        "⚠️ No real email will be sent."
    )


    # --------------------------------------------------------
    # Make sure production API key is not required.
    # --------------------------------------------------------

    with patch(
        "app.services.email_service._get_api_key",
        return_value="test-api-key"
    ):

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