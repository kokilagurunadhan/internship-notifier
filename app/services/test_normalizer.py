from app.services.job_normalizer import normalize_serpapi_job


# Simulate one SerpApi result

raw_job = {
    "title": "Software Engineering Intern",
    "company_name": "Google",
    "location": "Hyderabad, Telangana, India",
    "description": "Software engineering internship.",
    "via": "Peerlist",
    "apply_options": [
        {
            "title": "Peerlist",
            "link": "https://example.com/google-internship"
        }
    ]
}


normalized = normalize_serpapi_job(raw_job)


print()
print("=" * 60)
print("NORMALIZED JOB")
print("=" * 60)

for key, value in normalized.items():

    print(f"{key}: {value}")

print()