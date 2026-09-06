from app.services.relevance_engine import (
    calculate_relevance_score
)


# ============================================================
# MANUAL TEST RELEVANCE ENGINE
# ============================================================

def run_job_test(
    title,
    description,
    domain
):

    result = calculate_relevance_score(

        job_title=title,

        job_description=description,

        user_domain=domain
    )

    print()
    print("=" * 60)

    print("TITLE:")
    print(title)

    print()
    print("DOMAIN:")
    print(domain)

    print()
    print("KEYWORD SCORE:")
    print(result["keyword_score"])

    print(
        "SEMANTIC SCORE:"
    )
    print(result["semantic_score"])

    print(
        "CONFLICT:"
    )
    print(result["conflict"])

    print(
        "FINAL SCORE:"
    )
    print(result["final_score"])

    print("=" * 60)


# ============================================================
# MANUAL TEST CASES
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "🧠 RELEVANCE ENGINE TEST"
    )

    # --------------------------------------------------------
    # TEST 1
    # --------------------------------------------------------

    run_job_test(

        title="Software Engineering Intern",

        description=(
            "Work on backend services, "
            "APIs and Python applications."
        ),

        domain="software"
    )

    # --------------------------------------------------------
    # TEST 2
    # --------------------------------------------------------

    run_job_test(

        title="Frontend Developer Intern",

        description=(
            "Build React and JavaScript "
            "web applications."
        ),

        domain="software"
    )

    # --------------------------------------------------------
    # TEST 3
    # --------------------------------------------------------

    run_job_test(

        title="Data Analyst Intern",

        description=(
            "Work with SQL, Python, "
            "Power BI and data analysis."
        ),

        domain="data"
    )

    # --------------------------------------------------------
    # TEST 4
    # --------------------------------------------------------

    run_job_test(

        title="HR Intern",

        description=(
            "Recruitment and talent acquisition."
        ),

        domain="software"
    )

    # --------------------------------------------------------
    # TEST 5
    # --------------------------------------------------------

    run_job_test(

        title="Software Engineering Intern",

        description=(
            "Build software applications."
        ),

        domain=None
    )