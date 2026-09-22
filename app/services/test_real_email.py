# ============================================================
#  REAL GMAIL bervo EMAIL TEST
# File: app/services/test_real_email.py
# ============================================================

import os

from dotenv import load_dotenv

from app.services.email_service import (
    send_notification_email,
)


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# TEST EMAIL
# ============================================================

TEST_RECIPIENT = "kokilasudha9363@gmail.com"


# ============================================================
# CONTROLLED INTERNSHIP
# ============================================================

TEST_INTERNSHIP = {
    "title": "Software Engineering Intern",
    "company": "ControlledTest",
    "location": "Bangalore, India",
    "url": "https://controlled.test/e2e-001",
    "relevance_score": 91.5,
    "is_new": True,
}


# ============================================================
# TEST
# ============================================================

def main():

    print("=" * 65)
    print("REAL BREVO API EMAIL TEST")
    print("=" * 65)

    print()
    print("From:", os.getenv("FROM_EMAIL"))
    print("To:", TEST_RECIPIENT)

    print()
    print("Sending real email...")

    response = send_notification_email(
        recipient_email=TEST_RECIPIENT,
        internships=[
            TEST_INTERNSHIP
        ],
        idempotency_key=(
            "real-email-test-controlled-001"
        ),
    )

    print()

    if response is None:

        print(
            "❌ EMAIL TEST FAILED"
        )

        raise SystemExit(1)

    print(
        "✅ Brevo API accepted the email"
    )

    print()
    print(
        "Response:",
        response
    )

    print()
    print("=" * 65)
    print("🎉 REAL EMAIL TEST PASSED")
    print("=" * 65)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()