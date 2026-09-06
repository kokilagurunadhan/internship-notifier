import os
import requests
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

API_KEY = os.getenv("SERPAPI_API_KEY")


# ============================================================
# CHECK API KEY
# ============================================================

if not API_KEY:
    raise ValueError(
        "SERPAPI_API_KEY is missing from .env"
    )


print("✅ SerpApi key loaded successfully")


# ============================================================
# GOOGLE JOBS SEARCH
# ============================================================

params = {
    "engine": "google_jobs",
    "q": "software engineering internship",
    "location": "India",
    "hl": "en",
    "api_key": API_KEY
}


# ============================================================
# SEND REQUEST
# ============================================================

print("🔎 Searching Google Jobs through SerpApi...")

response = requests.get(
    "https://serpapi.com/search.json",
    params=params,
    timeout=30
)


# ============================================================
# CHECK RESPONSE
# ============================================================

response.raise_for_status()

data = response.json()

jobs = data.get("jobs_results", [])


# ============================================================
# DISPLAY RESULTS
# ============================================================

print()
print("=" * 60)
print("SERPAPI GOOGLE JOBS TEST")
print("=" * 60)

print(f"🎯 Jobs received: {len(jobs)}")
print()


for index, job in enumerate(jobs[:10], start=1):

    print(f"JOB {index}")
    print("-" * 60)

    print("Title:", job.get("title"))

    print("Company:", job.get("company_name"))

    print("Location:", job.get("location"))

    print("Via:", job.get("via"))

    print("Description:")
    print(
        (job.get("description") or "")[:300]
    )

    print()

    print("Apply options:")
    print(job.get("apply_options"))

    print("=" * 60)


print()
print("✅ SerpApi test completed!")