import os
import requests

from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(BASE_DIR / ".env")


def test_real_serpapi_raw():
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is missing")

    params = {
        "engine": "google_jobs",
        "q": "Microsoft internship",
        "location": "India",
        "hl": "en",
        "api_key": api_key,
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=120,
    )

    print("\nSTATUS:", response.status_code)
    print("\nRAW RESPONSE:")
    print(response.text[:10000])

    assert response.status_code == 200
def test_serpapi_extract_jobs():
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY is missing")

    params = {
        "engine": "google_jobs",
        "q": "Microsoft internship",
        "location": "India",
        "hl": "en",
        "api_key": api_key,
    }

    response = requests.get(
        "https://serpapi.com/search.json",
        params=params,
        timeout=120,
    )

    assert response.status_code == 200

    data = response.json()

    jobs = data.get("jobs_results", [])

    print("\n================ JOB EXTRACTION ================")
    print("Number of jobs:", len(jobs))

    assert len(jobs) > 0

    for i, job in enumerate(jobs[:5], 1):
        print(f"\n--- JOB {i} ---")
        print("Title:", job.get("title"))
        print("Company:", job.get("company_name"))
        print("Location:", job.get("location"))
        print("Via:", job.get("via"))
        print("Job ID:", job.get("job_id"))
        print("Share link:", job.get("share_link"))
        print("Description:", job.get("description", "")[:200])