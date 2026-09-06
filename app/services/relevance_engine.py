# ============================================================
# RELEVANCE ENGINE
# ============================================================

from app.services.semantic_scorer import (
    calculate_semantic_score,
    normalize_domain
)


# ============================================================
# DOMAIN KEYWORDS
# ============================================================

DOMAIN_KEYWORDS = {

    "frontend": {
        "frontend",
        "front end",
        "front-end",
        "react",
        "angular",
        "vue",
        "javascript",
        "typescript",
        "html",
        "css",
        "tailwind",
        "ui engineer",
        "ui developer",
        "web developer",
        "web development"
    },

    "backend": {
        "backend",
        "back end",
        "back-end",
        "api",
        "rest api",
        "python",
        "django",
        "flask",
        "fastapi",
        "node.js",
        "nodejs",
        "java",
        "spring",
        "server"
    },

    "full stack": {
        "full stack",
        "full-stack",
        "frontend",
        "backend",
        "react",
        "node.js",
        "nodejs",
        "web application"
    },

    "data": {
        "data analyst",
        "data analysis",
        "data scientist",
        "data science",
        "data engineering",
        "data engineer",
        "sql",
        "python",
        "pandas",
        "numpy",
        "power bi",
        "tableau",
        "business intelligence",
        "bi analyst",
        "analytics"
    },

    "machine learning": {
        "machine learning",
        "machine-learning",
        "ml engineer",
        "artificial intelligence",
        "ai engineer",
        "deep learning",
        "neural network",
        "nlp",
        "computer vision",
        "llm",
        "pytorch",
        "tensorflow"
    },

    "software": {
        "software engineer",
        "software engineering",
        "software developer",
        "software development",
        "software development intern",
        "programming",
        "application developer",
        "application development",
        "python",
        "java",
        "c++",
        "c#"
    },

    "embedded": {
        "embedded",
        "embedded systems",
        "embedded system",
        "firmware",
        "microcontroller",
        "microprocessor",
        "arm",
        "stm32",
        "arduino",
        "esp32",
        "rtos"
    },

    "testing": {
        "qa",
        "quality assurance",
        "software testing",
        "test engineer",
        "test automation",
        "qa automation",
        "selenium",
        "cypress",
        "playwright",
        "pytest"
    },

    "hr": {
        "human resources",
        "hr",
        "recruitment",
        "recruiter",
        "talent acquisition",
        "talent management",
        "people operations",
        "hr operations"
    },

    "design": {
        "ui design",
        "ux design",
        "ui/ux",
        "ui ux",
        "user interface",
        "user experience",
        "product design",
        "figma",
        "visual design",
        "ux designer",
        "ui designer",
        "ui ux designer"
    }
}


# ============================================================
# DOMAIN CONFLICTS
# ============================================================
# ============================================================
# DOMAIN CONFLICTS
# ============================================================

DOMAIN_CONFLICTS = {

    "frontend": {
        "backend",
        "data",
        "embedded",
        "hardware",
        "firmware",
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "electrical"
    },

    "backend": {
        "frontend",
        "ui",
        "ux",
        "embedded",
        "firmware",
        "hardware",
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "full stack": {
        "embedded",
        "firmware",
        "hardware",
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "data": {
        "frontend",
        "embedded",
        "firmware",
        "hardware",
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "machine learning": {
        "frontend",
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "software": {
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "embedded": {
        "frontend",
        "backend",
        "full stack",
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "testing": {
        "hr",
        "human resources",
        "recruitment",
        "marketing",
        "sales",
        "finance",
        "accounting",
        "legal",
        "mechanical",
        "civil",
        "design"
    },

    "hr": {
        "frontend",
        "backend",
        "full stack",
        "software",
        "embedded",
        "firmware",
        "machine learning",
        "data",
        "testing",
        "hardware",
        "design"
    },

    "design": {
        "backend",
        "embedded",
        "firmware",
        "hardware",
        "hr",
        "human resources",
        "recruitment",
        "finance",
        "accounting",
        "legal",
        "software",
        "data",
        "machine learning"
    }
}
# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    return (
        str(text)
        .lower()
        .replace("-", " ")
        .replace("/", " ")
        .replace(".", " ")
        .strip()
    )


# ============================================================
# KEYWORD MATCH
# ============================================================

def keyword_exists(
    keyword,
    text
):

    keyword = normalize_text(keyword)
    text = normalize_text(text)

    if not keyword or not text:
        return False

    return keyword in text


# ============================================================
# KEYWORD SCORE
# ============================================================

def calculate_keyword_score(
    job_title,
    job_description,
    user_domain
):

    if not user_domain:
        return 50.0

    domain = normalize_domain(
        user_domain
    )

    keywords = DOMAIN_KEYWORDS.get(
        domain,
        set()
    )

    if not keywords:
        return 50.0

    title = normalize_text(
        job_title
    )

    description = normalize_text(
        job_description
    )

    # --------------------------------------------------------
    # TITLE MATCHES
    # --------------------------------------------------------

    title_matches = 0

    for keyword in keywords:

        if keyword_exists(
            keyword,
            title
        ):

            title_matches += 1

    # --------------------------------------------------------
    # DESCRIPTION MATCHES
    # --------------------------------------------------------

    description_matches = 0

    for keyword in keywords:

        if keyword_exists(
            keyword,
            description
        ):

            description_matches += 1

    # --------------------------------------------------------
    # STRONG TITLE SIGNAL
    # --------------------------------------------------------

    if title_matches >= 2:

        title_score = 100.0

    elif title_matches == 1:

        title_score = 85.0

    else:

        title_score = 0.0

    # --------------------------------------------------------
    # DESCRIPTION SIGNAL
    # --------------------------------------------------------

    description_score = min(
        description_matches * 10.0,
        40.0
    )

    # --------------------------------------------------------
    # COMBINE
    #
    # Title is much more important than description.
    # --------------------------------------------------------

    if title_matches > 0:

        score = (
            title_score * 0.85
            +
            description_score * 0.15
        )

    else:

        score = (
            description_score * 0.50
        )

    return round(
        min(score, 100.0),
        2
    )


# ============================================================
# DOMAIN CONFLICT
# ============================================================

def has_domain_conflict(
    job_title,
    job_description,
    user_domain
):

    if not user_domain:
        return False

    domain = normalize_domain(
        user_domain
    )

    conflicts = DOMAIN_CONFLICTS.get(
        domain,
        set()
    )

    if not conflicts:
        return False

    # --------------------------------------------------------
    # IMPORTANT:
    # Conflict is primarily determined from TITLE.
    #
    # We intentionally do not scan the complete description
    # because descriptions frequently mention unrelated tools,
    # departments and technologies.
    # --------------------------------------------------------

    title = normalize_text(
        job_title
    )

    # --------------------------------------------------------
    # CHECK EACH CONFLICT CATEGORY
    # --------------------------------------------------------

    for conflict_domain in conflicts:

        conflict_keywords = DOMAIN_KEYWORDS.get(
            conflict_domain,
            set()
        )

        for keyword in conflict_keywords:

            if keyword_exists(
                keyword,
                title
            ):

                return True

    return False


# ============================================================
# FINAL RELEVANCE SCORE
# ============================================================

def calculate_relevance_score(
    job_title,
    job_description="",
    user_domain=None
):

    # --------------------------------------------------------
    # NO DOMAIN
    # --------------------------------------------------------

    if not user_domain:

        return {

            "keyword_score": 50.0,

            "semantic_score": 50.0,

            "conflict": False,

            "final_score": 50.0
        }

    # --------------------------------------------------------
    # DOMAIN CONFLICT FIRST
    # --------------------------------------------------------

    conflict = has_domain_conflict(
        job_title,
        job_description,
        user_domain
    )

    if conflict:

        return {

            "keyword_score": 0.0,

            "semantic_score": 0.0,

            "conflict": True,

            "final_score": 0.0
        }

    # --------------------------------------------------------
    # KEYWORD ENGINE
    # --------------------------------------------------------

    keyword_score = calculate_keyword_score(
        job_title,
        job_description,
        user_domain
    )

    # --------------------------------------------------------
    # SEMANTIC AI
    #
    # Semantic scorer primarily evaluates the job title.
    # --------------------------------------------------------

    semantic_score = calculate_semantic_score(
        job_title,
        user_domain
    )

    # --------------------------------------------------------
    # FINAL SCORE
    #
    # Keyword = 60%
    # Semantic = 40%
    # --------------------------------------------------------

    final_score = (
        keyword_score * 0.60
        +
        semantic_score * 0.40
    )

    final_score = max(
        0.0,
        min(
            final_score,
            100.0
        )
    )

    return {

        "keyword_score": round(
            keyword_score,
            2
        ),

        "semantic_score": round(
            semantic_score,
            2
        ),

        "conflict": False,

        "final_score": round(
            final_score,
            2
        )
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("🧪 RELEVANCE ENGINE TEST")
    print("=" * 70)

    tests = [

        (
            "software",
            "Software Engineering Intern",
            False
        ),

        (
            "backend",
            "Backend Engineering Intern",
            False
        ),

        (
            "frontend",
            "Frontend Developer Intern",
            False
        ),

        (
            "data",
            "Data Analyst Intern",
            False
        ),

        (
            "machine learning",
            "Machine Learning Intern",
            False
        ),

        (
            "embedded",
            "Embedded Systems Intern",
            False
        ),

        (
            "testing",
            "QA Automation Intern",
            False
        ),

        (
            "design",
            "UI UX Design Intern",
            False
        ),

        (
            "hr",
            "Human Resources Intern",
            False
        ),

        # ----------------------------------------------------
        # CONFLICT TESTS
        # ----------------------------------------------------

        (
            "frontend",
            "Backend Engineering Intern",
            True
        ),

        (
            "software",
            "Human Resources Intern",
            True
        ),

        (
            "data",
            "UI UX Designer Intern",
            True
        )
    ]

    passed = 0
    failed = 0

    for domain, title, expected_conflict in tests:

        result = calculate_relevance_score(
            job_title=title,
            job_description="",
            user_domain=domain
        )

        actual_conflict = result["conflict"]

        if actual_conflict == expected_conflict:

            passed += 1
            status = "✅ Test PASS"

        else:

            failed += 1
            status = "❌ Test FAIL"

        print()
        print("-" * 70)

        print(
            f"🎯 Domain: {domain}"
        )

        print(
            f"💼 Title: {title}"
        )

        print(
            f"📊 Keyword: "
            f"{result['keyword_score']}"
        )

        print(
            f"🧠 Semantic: "
            f"{result['semantic_score']}"
        )

        print(
            f"⚠️ Conflict: "
            f"{result['conflict']}"
        )

        print(
            f"⚖️ Final: "
            f"{result['final_score']}"
        )

        print(status)

    print()
    print("=" * 70)

    print(
        f"✅ Passed: {passed}"
    )

    print(
        f"❌ Failed: {failed}"
    )

    print(
        f"🧪 Total: {len(tests)}"
    )

    print("=" * 70)

    if failed == 0:

        print(
            "🎉 ALL RELEVANCE TESTS PASSED"
        )

    else:

        print(
            "⚠️ SOME RELEVANCE TESTS FAILED"
        )

    print("=" * 70)