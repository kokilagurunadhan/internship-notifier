from app.services.relevance_scorer import (
    calculate_relevance_score
)


# ============================================================
# TEST JOBS
# ============================================================

jobs = [

    {
        "title": "Frontend React Developer Intern",
        "description": (
            "Build web applications using React, "
            "JavaScript and modern frontend technologies."
        )
    },

    {
        "title": "Software Engineer Intern",
        "description": (
            "Work with React and JavaScript "
            "to build web applications."
        )
    },

    {
        "title": "Backend Engineer Intern",
        "description": (
            "Work with Python, FastAPI and PostgreSQL."
        )
    },

    {
        "title": "HR Recruitment Intern",
        "description": (
            "Support recruitment and talent acquisition."
        )
    }
]


# ============================================================
# TEST FRONTEND
# ============================================================

print()
print("=" * 60)
print("FRONTEND RELEVANCE")
print("=" * 60)

for job in jobs:

    score = calculate_relevance_score(
        job,
        "Frontend"
    )

    print(
        f"{score:5.1f} | "
        f"{job['title']}"
    )


# ============================================================
# TEST WITHOUT DOMAIN
# ============================================================

print()
print("=" * 60)
print("NO DOMAIN")
print("=" * 60)

for job in jobs:

    score = calculate_relevance_score(
        job,
        None
    )

    print(
        f"{score:5.1f} | "
        f"{job['title']}"
    )