import time
import requests
from bs4 import BeautifulSoup

from app.services.sources.lever_companies import LEVER_COMPANIES
from app.services.internship_filter import filter_internships

from app.services.internship_service import (
    save_internship
)




# ============================================================
# FETCH LEVER JOBS
# ============================================================

def fetch_lever_jobs(company_slug: str):

    url = f"https://api.lever.co/v0/postings/{company_slug}"

    for attempt in range(3):

        try:

            response = requests.get(
                url,
                params={"mode": "json"},
                timeout=15
            )

            response.raise_for_status()

            return response.json()

        except requests.RequestException as error:

            print(
                f"⚠️ Lever request failed "
                f"(attempt {attempt + 1}/3): {error}"
            )

            if attempt < 2:

                wait_time = 2 ** attempt

                print(
                    f"⏳ Retrying in {wait_time} seconds..."
                )

                time.sleep(wait_time)

            else:

                raise


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
# NORMALIZE LEVER JOB
# ============================================================

def normalize_lever_job(job, company):

    categories = job.get(
        "categories",
        {}
    )

    return {
        "company": company,

        "title": job.get(
            "text",
            "Internship"
        ),

        "location": categories.get(
            "location",
            "Location not specified"
        ),

        "source": "Lever",

        "url": job.get(
            "hostedUrl"
        ),

        "description": clean_description(
            job.get(
                "description",
                ""
            )
        )
    }


# ============================================================
# COLLECT LEVER INTERNSHIPS
# ============================================================

def collect_lever_internships(companies):

    all_internships = []

    for company in companies:

        company_name = company["name"]
        company_slug = company["slug"]

        print(
            f"🔎 Searching Lever: {company_name}..."
        )

        try:

            jobs = fetch_lever_jobs(
                company_slug
            )

        except Exception as error:

            print(
                f"❌ Failed to fetch "
                f"{company_name}: {error}"
            )

            continue

        print("   Sample Lever titles:")

        for job in jobs[:10]:

            print(
                f"      → {job.get('text')}"
            )

        internships = filter_internships(
            jobs
        )

        print(
            f"   Found {len(jobs)} jobs, "
            f"{len(internships)} internships"
        )

        seen = set()

        for job in internships:

            normalized = normalize_lever_job(
                job,
                company_name
            )

            title = (
                normalized["title"] or ""
            ).strip().lower()

            unique_key = (
                normalized["company"]
                .strip()
                .lower(),
                title
            )

            if unique_key in seen:
                continue

            seen.add(unique_key)

            all_internships.append(
                normalized
            )

    return all_internships


# ============================================================
# PROCESS LEVER INTERNSHIPS
# ============================================================

def process_lever_internships():

    internships = collect_lever_internships(
        LEVER_COMPANIES
    )

    print(
        f"\n🎯 Total Lever internships found: "
        f"{len(internships)}"
    )

    for internship in internships:

        try:

            saved, is_new = save_internship(
                internship
            )

        except Exception as error:

            print(
                f"❌ Error saving internship: "
                f"{error}"
            )

            continue

        if is_new:

            print(
                f"🆕 NEW Lever internship: "
                f"{saved.company} | "
                f"{saved.title} | "
                f"{saved.location}"
            )

            
            

                

            

# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    print(
        "\n🚀 Testing Lever internship collector..."
    )

    process_lever_internships()