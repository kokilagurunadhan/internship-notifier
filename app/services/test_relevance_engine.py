from app.services.relevance_engine import (
    calculate_relevance_score
)


# ============================================================
# TEST CASES
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
        Work on user interfaces and web applications.
        """
    },

    {
        "domain": "Frontend",
        "title": "Backend Engineer Intern",
        "description": """
        Build APIs using Python, FastAPI and PostgreSQL.
        """
    },

    {
        "domain": "Frontend",
        "title": "Data Analyst Intern",
        "description": """
        Analyze business data using SQL,
        Python and Power BI.
        """
    },

    {
        "domain": "Frontend",
        "title": "HR Recruitment Intern",
        "description": """
        Support recruitment and talent acquisition.
        """
    },

    {
        "domain": "Backend",
        "title": "Python Backend Developer Intern",
        "description": """
        Build REST APIs using Python and FastAPI.
        """
    },

    {
        "domain": "Machine Learning",
        "title": "Machine Learning Intern",
        "description": """
        Build ML models using Python and PyTorch.
        """
    },

    {
        "domain": "Embedded",
        "title": "Embedded Systems Intern",
        "description": """
        Develop firmware using C and microcontrollers.
        """
    }

]


# ============================================================
# RUN TEST
# ============================================================

print()
print("=" * 80)
print("FINAL RELEVANCE ENGINE TEST")
print("=" * 80)


for test in tests:

    result = calculate_relevance_score(
        job_title=test["title"],
        job_description=test["description"],
        user_domain=test["domain"]
    )

    print()
    print(f"Domain  : {test['domain']}")
    print(f"Job     : {test['title']}")
    print(
        f"Keyword : {result['keyword_score']:.2f}"
    )
    print(
        f"Semantic: {result['semantic_score']:.2f}"
    )
    print(
        f"Conflict: {result['conflict']}"
    )
    print(
        f"FINAL   : {result['final_score']:.2f}"
    )


print()
print("=" * 80)
print("TEST COMPLETED")
print("=" * 80)