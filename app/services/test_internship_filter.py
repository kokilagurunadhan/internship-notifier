# ============================================================
# INTERNSHIP FILTER TEST
# ============================================================

from app.services.internship_filter import (
    is_internship
)


# ============================================================
# TEST CASES
# ============================================================

test_jobs = [

    {
        "title": "Software Engineer Intern",
        "description": "Work with a software engineering team.",
    },

    {
        "title": "Machine Learning Intern",
        "description": "Build machine learning models.",
    },

    {
        "title": "Summer Software Engineering Internship",
        "description": "A summer internship for students.",
    },

    {
        "title": "Graduate Trainee",
        "description": "Graduate trainee opportunity for students.",
    },

    {
        "title": "Industrial Trainee",
        "description": "Industrial training program.",
    },

    {
        "title": "Apprentice - Software Development",
        "description": "Apprenticeship opportunity.",
    },

    {
        "title": "Senior Software Engineer",
        "description": "Full-time senior engineering position.",
    },

    {
        "title": "Backend Developer",
        "description": "You will mentor interns on the team.",
    },

    {
        "title": "Software Engineer",
        "description": "This is a full-time engineering position.",
    },

    {
        "title": "Engineering Manager",
        "description": "Manage the engineering team.",
    },

]


# ============================================================
# RUN TEST
# ============================================================

print()
print("=" * 80)
print("STRICT INTERNSHIP FILTER TEST")
print("=" * 80)


for job in test_jobs:

    result = is_internship(
        job["title"],
        job["description"]
    )

    print()
    print("Job     :", job["title"])
    print("Result  :", "✅ INTERNSHIP" if result else "❌ NOT INTERNSHIP")


print()
print("=" * 80)
print("TEST COMPLETED")
print("=" * 80)