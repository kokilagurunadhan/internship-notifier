import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from app.services.internship_filter import filter_internships
import logging

logger = logging.getLogger(__name__)
# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")

# ============================================================
# FETCH ADZUNA JOBS
# ============================================================

def fetch_adzuna_jobs(
    keyword="intern",
    country="in",
    page=1
):

    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise ValueError(
            "ADZUNA_APP_ID or ADZUNA_APP_KEY is missing from .env"
        )

    url = (
        f"https://api.adzuna.com/v1/api/jobs/"
        f"{country}/search/{page}"
    )

    params = {
        "app_id": ADZUNA_APP_ID,
        "app_key": ADZUNA_APP_KEY,
        "results_per_page": 50,
        "what": keyword,
        "content-type": "application/json"
    }

    response = requests.get(
        url,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    return data.get("results", [])


# ============================================================
# CLEAN DESCRIPTION
# ============================================================

def clean_description(description):

    soup = BeautifulSoup(
        description or "",
        "html.parser"
    )

    return soup.get_text(
        " ",
        strip=True
    )


# ============================================================
# NORMALIZE ADZUNA JOB
# ============================================================

def normalize_adzuna_job(job):

    company = job.get(
        "company",
        {}
    )

    location = job.get(
        "location",
        {}
    )

    return {
        "company": company.get(
            "display_name",
            "Unknown Company"
        ),

        "title": job.get(
            "title",
            "Internship"
        ),

        "location": location.get(
            "display_name",
            "India"
        ),

        "source": "Adzuna",

        "url": job.get(
            "redirect_url"
        ),

        "description": clean_description(
            job.get(
                "description",
                ""
            )
        )
    }


# ============================================================
# COLLECT ADZUNA INTERNSHIPS
# ============================================================

def collect_adzuna_internships():

    all_internships = []

    keywords = [
        "intern",
        "internship",
        "co-op"
    ]

    seen = set()

    for keyword in keywords:

        logger.info(
    "Searching Adzuna",
    extra={
        "keyword": keyword,
    },
)

        try:

            jobs = fetch_adzuna_jobs(
                keyword=keyword
            )

            internships = filter_internships(
                jobs
            )

            logger.info(
    "Adzuna search completed",
    extra={
        "jobs_found": len(jobs),
        "internships_found": len(internships),
    },
)

            for job in internships:

                normalized = normalize_adzuna_job(
                    job
                )

                unique_key = (
                    normalized["company"],
                    normalized["title"],
                    normalized["location"],
                    normalized["url"]
                )

                if unique_key in seen:
                    continue

                seen.add(unique_key)

                all_internships.append(
                    normalized
                )

        except Exception as error:

            logger.exception(
               "Adzuna search failed"
    )

    return all_internships


# ============================================================
# TEST ADZUNA
# ============================================================

if __name__ == "__main__":

    print(
        "\n🚀 Testing Adzuna..."
    )

    internships = (
        collect_adzuna_internships()
    )

    print(
        f"\n🎯 Total Adzuna internships: "
        f"{len(internships)}"
    )

    for internship in internships:

        print(
            f"\n🏢 {internship['company']}"
        )

        print(
            f"💼 {internship['title']}"
        )

        print(
            f"📍 {internship['location']}"
        )

        print(
            f"🔗 {internship['url']}"
        )