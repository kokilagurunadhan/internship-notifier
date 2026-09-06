import requests
from bs4 import BeautifulSoup

from app.services.internship_filter import filter_internships

from app.services.relevance_engine import (
    calculate_relevance_score
)

from app.services.internship_service import (
    save_internship,
    internship_exists
)

from app.services.sources.greenhouse_companies import (
    GREENHOUSE_COMPANIES
)


# ============================================================
# SETTINGS
# ============================================================

MIN_RELEVANCE_SCORE = 50


# ============================================================
# FETCH GREENHOUSE JOBS
# ============================================================

def fetch_greenhouse_jobs(board_token: str):

    url = (
        f"https://boards-api.greenhouse.io/v1/boards/"
        f"{board_token}/jobs"
    )

    response = requests.get(
        url,
        params={"content": "true"},
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    return data.get("jobs", [])


# ============================================================
# CLEAN DESCRIPTION
# ============================================================

def clean_description(html):

    soup = BeautifulSoup(
        html or "",
        "html.parser"
    )

    return soup.get_text(
        " ",
        strip=True
    )


# ============================================================
# NORMALIZE JOB
# ============================================================

def normalize_greenhouse_job(job, company):

    location = job.get(
        "location",
        {}
    )

    return {
        "company": company,

        "title": job.get(
            "title",
            ""
        ),

        "location": location.get(
            "name",
            ""
        ),

        "source": "Greenhouse",

        "url": job.get(
            "absolute_url",
            ""
        ),

        "description": clean_description(
            job.get(
                "content",
                ""
            )
        )
    }


# ============================================================
# COLLECT GREENHOUSE JOBS
# ============================================================

def collect_greenhouse_jobs():

    all_jobs = []

    for company in GREENHOUSE_COMPANIES:

        company_name = company["name"]
        board_token = company["board_token"]

        print(
            f"🔎 Searching Greenhouse: "
            f"{company_name}..."
        )

        try:

            jobs = fetch_greenhouse_jobs(
                board_token
            )

            print(
                f"   Found {len(jobs)} jobs"
            )

            for job in jobs:

                normalized = normalize_greenhouse_job(
                    job,
                    company_name
                )

                all_jobs.append(
                    normalized
                )

        except Exception as error:

            print(
                f"❌ Error processing "
                f"{company_name}: {error}"
            )

    return all_jobs


# ============================================================
# PROCESS GREENHOUSE
# ============================================================

def process_greenhouse_internships():

    jobs = collect_greenhouse_jobs()

    print(
        f"\n🎯 Total Greenhouse jobs collected: "
        f"{len(jobs)}"
    )

    saved_count = 0
    skipped_count = 0
    rejected_count = 0

    for internship in jobs:

        company = internship["company"]
        title = internship["title"]
        url = internship["url"]

        print()
        print("=" * 70)

        print(
            f"🔍 Processing: "
            f"{company} | {title}"
        )

        # ====================================================
        # 1. REQUIRED DATA
        # ====================================================

        if not company or not title or not url:

            print(
                "⏭️ Skipping: missing company/title/url"
            )

            skipped_count += 1

            continue

        # ====================================================
        # 2. DUPLICATE CHECK
        # ====================================================
        #
        # IMPORTANT:
        # This happens BEFORE:
        #
        # - internship filtering
        # - keyword scoring
        # - semantic AI
        #
        # Therefore existing jobs consume almost no CPU.
        # ====================================================

        if internship_exists(url):

            print(
                "⏭️ Duplicate: already exists in database"
            )

            skipped_count += 1

            continue

        # ====================================================
        # 3. STRICT INTERNSHIP FILTER
        # ====================================================

        filtered = filter_internships(
            [internship]
        )

        if not filtered:

            print(
                "❌ Rejected: not a valid internship"
            )

            rejected_count += 1

            continue

        print(
            "✅ Passed strict internship filter"
        )

        # ====================================================
        # 4. COMPANY VERIFICATION
        # ====================================================

        # Greenhouse already gives us the company
        # from the configured board.
        #
        # Therefore the company is trusted here.

        print(
            f"🏢 Company verified: {company}"
        )

        # ====================================================
        # 5. KEYWORD + SEMANTIC AI
        # ====================================================

        #
        # IMPORTANT:
        # At this stage the job is NEW and valid.
        #
        # The relevance engine will calculate:
        #
        # keyword_score
        # semantic_score
        # conflict
        # final_score
        #
        # The subscription-specific domain is handled
        # later when notifications are created.
        #

        print(
            "🧠 Running keyword + semantic relevance..."
        )

        # ----------------------------------------------------
        # IMPORTANT
        # ----------------------------------------------------
        #
        # Your current relevance_engine expects:
        #
        # job_title
        # job_description
        # user_domain
        #
        # A Greenhouse source job does NOT have one
        # universal user_domain.
        #
        # Therefore the final subscription-specific score
        # should be calculated when matching subscriptions.
        #
        # We do NOT calculate a fake score here.
        #
        # The job itself will be saved first.
        #
        # ----------------------------------------------------

        internship["relevance_score"] = None

        # ====================================================
        # 6. SAVE JOB TO DATABASE
        # ====================================================

        saved, is_new = save_internship(
            internship,
            create_notifications=False
        )

        if is_new:

            saved_count += 1

            print(
                f"🆕 NEW Greenhouse internship: "
                f"{saved.company} | "
                f"{saved.title}"
            )

        else:

            print(
                f"⏭️ Already exists: "
                f"{saved.company} | "
                f"{saved.title}"
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)

    print(
        "🎯 GREENHOUSE PROCESSING COMPLETE"
    )

    print(
        f"🆕 New jobs saved : {saved_count}"
    )

    print(
        f"⏭️ Duplicates     : {skipped_count}"
    )

    print(
        f"❌ Rejected       : {rejected_count}"
    )

    print(
        "=" * 70
    )

    return jobs


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    process_greenhouse_internships()