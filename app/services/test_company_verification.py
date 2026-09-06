from app.services.sources.serpapi import search_jobs

from app.services.company_verification import (
    verify_company
)


print()
print("=" * 60)
print("COMPANY VERIFICATION TEST")
print("=" * 60)


jobs = search_jobs(
    company="Microsoft",
    domain="software engineering"
)


print()


for index, job in enumerate(
    jobs,
    start=1
):

    result = verify_company(
        job,
        "Microsoft"
    )


    print(
        f"JOB {index}: "
        f"{job.get('title')}"
    )

    print(
        f"Company: "
        f"{job.get('company_name')}"
    )

    print(
        f"Verification: "
        f"{'✅ PASSED' if result else '❌ FAILED'}"
    )

    print("-" * 60)


print()
print(
    "✅ Company verification test completed!"
)