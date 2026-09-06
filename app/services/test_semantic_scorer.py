from app.services.semantic_scorer import (
    calculate_semantic_score
)


# ============================================================
# TEST JOBS
# ============================================================

tests = [

    {
        "domain": "Frontend",
        "title": "React Developer Intern",
        "description": """
        Build modern web interfaces using React,
        JavaScript, HTML and CSS.
        """
    },

    {
        "domain": "Frontend",
        "title": "UI Engineer Intern",
        "description": """
        Work on user interfaces and web applications
        using modern frontend technologies.
        """
    },

    {
        "domain": "Frontend",
        "title": "Backend Engineer Intern",
        "description": """
        Develop APIs and backend services using
        Python, FastAPI and PostgreSQL.
        """
    },

    {
        "domain": "Frontend",
        "title": "Data Analyst Intern",
        "description": """
        Analyze business data using SQL,
        Python, Pandas and Power BI.
        """
    },

    {
        "domain": "Frontend",
        "title": "HR Recruitment Intern",
        "description": """
        Support recruitment, hiring and
        talent acquisition activities.
        """
    },

    {
        "domain": "Artificial Intelligence",
        "title": "Machine Learning Intern",
        "description": """
        Build machine learning models using
        Python, PyTorch and artificial intelligence.
        """
    },

    {
        "domain": "Backend",
        "title": "Python Backend Developer Intern",
        "description": """
        Build REST APIs and backend services
        using Python and FastAPI.
        """
    },

    {
        "domain": "Embedded",
        "title": "Embedded Systems Intern",
        "description": """
        Develop firmware for microcontrollers
        using C and embedded systems technologies.
        """
    }
]


# ============================================================
# RUN TEST
# ============================================================

print()
print("=" * 75)
print("SEMANTIC AI RELEVANCE TEST")
print("=" * 75)


for test in tests:

    score = calculate_semantic_score(
        job_title=test["title"],
        user_domain=test["domain"],
        job_description=test["description"]
    )

    print()
    print(
        f"Domain : {test['domain']}"
    )

    print(
        f"Job    : {test['title']}"
    )

    print(
        f"Score  : {score:.2f}"
    )


print()
print("=" * 75)
print("TEST COMPLETED")
print("=" * 75)