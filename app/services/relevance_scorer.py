# ============================================================
# INTERNSHIP RELEVANCE SCORER
# ============================================================

import re


# ============================================================
# DOMAIN KEYWORDS
# ============================================================

DOMAIN_KEYWORDS = {

    "frontend": [
        "frontend",
        "front end",
        "react",
        "react.js",
        "angular",
        "vue",
        "javascript",
        "typescript",
        "html",
        "css",
        "tailwind",
        "next.js",
    ],

    "backend": [
        "backend",
        "back end",
        "python",
        "java",
        "node.js",
        "nodejs",
        "django",
        "flask",
        "fastapi",
        "spring",
        "api",
        "rest api",
    ],

    "full stack": [
        "full stack",
        "fullstack",
        "frontend",
        "backend",
        "react",
        "node.js",
        "django",
        "flask",
    ],

    "data": [
        "data analyst",
        "data analytics",
        "data analysis",
        "data science",
        "data engineer",
        "sql",
        "pandas",
        "numpy",
        "power bi",
        "tableau",
        "machine learning",
    ],

    "machine learning": [
        "machine learning",
        "ml",
        "artificial intelligence",
        "ai",
        "deep learning",
        "tensorflow",
        "pytorch",
        "nlp",
        "computer vision",
        "llm",
    ],

    "software": [
        "software engineer",
        "software developer",
        "software engineering",
        "programming",
        "developer",
        "python",
        "java",
        "c++",
        "c#",
    ],

    "embedded": [
        "embedded",
        "embedded systems",
        "firmware",
        "microcontroller",
        "microprocessor",
        "rtos",
        "arm",
        "stm32",
        "arduino",
        "esp32",
    ],

    "testing": [
        "software testing",
        "qa",
        "quality assurance",
        "test engineer",
        "automation testing",
        "selenium",
        "cypress",
        "playwright",
        "pytest",
    ],

    "hr": [
        "human resources",
        "hr",
        "recruitment",
        "talent acquisition",
        "people operations",
    ],

    "design": [
        "ui design",
        "ux design",
        "ui/ux",
        "product design",
        "figma",
        "user experience",
        "user interface",
    ],
}


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):
    """
    Convert text into a predictable lowercase format.
    """

    if not text:
        return ""

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9+#./ -]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# GET DOMAIN KEYWORDS
# ============================================================

def get_domain_keywords(domain):

    if not domain:
        return []

    domain = normalize_text(domain)

    # Direct domain match
    if domain in DOMAIN_KEYWORDS:

        return DOMAIN_KEYWORDS[domain]

    # Otherwise treat user's input as keywords
    return [
        keyword.strip()
        for keyword in domain.split(",")
        if keyword.strip()
    ]


# ============================================================
# CALCULATE RELEVANCE SCORE
# ============================================================

def calculate_relevance_score(
    job,
    user_domain=None
):
    """
    Calculate a transparent relevance score.

    Title matches receive much more weight than
    description matches.
    """

    # --------------------------------------------------------
    # NO DOMAIN
    # --------------------------------------------------------

    if not user_domain:

        return 50.0

    title = normalize_text(
        job.get("title")
    )

    description = normalize_text(
        job.get("description")
    )

    keywords = get_domain_keywords(
        user_domain
    )

    if not keywords:

        return 50.0

    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    score = 0.0

    for keyword in keywords:

        keyword = normalize_text(keyword)

        if not keyword:
            continue

        # Strong signal: title
        if keyword in title:

            score += 15

        # Supporting signal: description
        elif keyword in description:

            score += 3

    # --------------------------------------------------------
    # CAP SCORE
    # --------------------------------------------------------

    return min(score, 100.0)