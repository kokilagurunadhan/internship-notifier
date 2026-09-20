import os
import requests

from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

API_KEY = os.getenv("SERPAPI_API_KEY")


# ============================================================
# SEARCH GOOGLE JOBS THROUGH SERPAPI
# ============================================================

def search_jobs(company, domain=None, location="India"):
    if not API_KEY:
        raise ValueError("SERPAPI_API_KEY is missing from .env")

    query = f"{company} internship"
    if domain:
        query += f" {domain}"

    print(f"🔎 SerpAPI search: {query}")

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "hl": "en",
        "api_key": API_KEY
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()
    jobs = data.get("jobs_results", [])

    print(f"   🎯 SerpAPI returned {len(jobs)} jobs")
    return jobs
# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("RAW SERPAPI JOB SEARCH TEST")
    print("=" * 70)


    jobs = search_jobs(
        company="Microsoft",
        domain="software engineering"
    )


    print()
    print(
        f"📦 Raw jobs received: {len(jobs)}"
    )


    for index, job in enumerate(
        jobs[:10],
        start=1
    ):

        print()
        print(
            f"JOB {index}"
        )

        print(
            "-" * 70
        )

        print(
            "Title:",
            job.get("title")
        )

        print(
            "Company:",
            job.get("company_name")
        )

        print(
            "Location:",
            job.get("location")
        )

        print(
            "Via:",
            job.get("via")
        )

        print(
            "Description:",
            (job.get("description") or "")[:300]
        )

        print(
            "Apply:",
            job.get("apply_options")
        )

        print(
            "-" * 70
        )


    print()
    print(
        "✅ Raw SerpAPI search completed!"
    )