from app.services.internship_service import internship_url_exists


if __name__ == "__main__":

    test_url = "https://example.com/test-internship"

    exists = internship_url_exists(test_url)

    if exists:

        print("⏭️ Duplicate internship found.")

    else:

        print("🆕 New internship URL.")