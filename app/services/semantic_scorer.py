# ============================================================
# SEMANTIC AI RELEVANCE SCORER
# ============================================================

import logging

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)
# ============================================================
# LOAD MODEL ONCE
# ============================================================

logger.info("Loading semantic AI model")

model = SentenceTransformer(
    "all-MiniLM-L6-v2"
)
logger.info("Semantic AI model ready")


# ============================================================
# DOMAIN PROFILES
# ============================================================

DOMAIN_PROFILES = {

    "frontend": """
    Frontend web development.
    User interface development.
    React, Angular, Vue, JavaScript,
    TypeScript, HTML, CSS, Tailwind,
    web applications and UI engineering.
    """,

    "backend": """
    Backend software development.
    Server-side application development.
    APIs, databases and backend services.
    Python, Java, Node.js, Django,
    Flask, FastAPI, Spring and REST APIs.
    """,

    "full stack": """
    Full stack web application development.
    Frontend and backend development.
    React, JavaScript, Python, Node.js,
    APIs, databases and web applications.
    """,

    "data": """
    Data analysis and data engineering.
    Data analytics, SQL, Python,
    Pandas, NumPy, Power BI, Tableau,
    databases and business intelligence.
    """,

    "machine learning": """
    Machine learning and artificial intelligence.
    Deep learning, neural networks,
    NLP, computer vision, LLMs,
    TensorFlow, PyTorch and AI systems.
    """,

    "software": """
    General software engineering and software development.
    Programming, application development,
    software systems, Python, Java,
    C++, C# and software engineering.
    """,

    "embedded": """
    Embedded systems and firmware development.
    Microcontrollers, microprocessors,
    embedded software, firmware,
    ARM, STM32, Arduino, ESP32 and RTOS.
    """,

    "testing": """
    Software testing and quality assurance.
    QA engineering, test automation,
    Selenium, Cypress, Playwright,
    pytest and software quality.
    """,

    "hr": """
    Human resources, recruitment and talent acquisition.
    Hiring, recruiting, employee operations,
    talent management and people operations.
    """,

    "design": """
    UI UX and product design.
    User interface design,
    user experience design,
    Figma, product design and visual design.
    """
}


# ============================================================
# NORMALIZE DOMAIN
# ============================================================

def normalize_domain(domain):

    if not domain:
        return ""

    return domain.strip().lower()


# ============================================================
# DOMAIN PROFILE
# ============================================================

def get_domain_profile(domain):

    domain = normalize_domain(domain)

    if not domain:
        return ""

    if domain in DOMAIN_PROFILES:

        return DOMAIN_PROFILES[domain]

    return f"""
    Internship role related to:
    {domain}
    """


# ============================================================
# SEMANTIC TITLE SCORE
# ============================================================

def calculate_semantic_score(
    job_title,
    user_domain,
    job_description=""
):
    """
    Semantic AI primarily evaluates the JOB TITLE.

    Keyword logic is responsible for detailed
    description matching.

    job_description is intentionally NOT used
    for semantic scoring.
    """

    if not user_domain:
        return 50.0

    job_title = (
        job_title or ""
    ).strip()

    if not job_title:
        return 0.0

    domain_profile = get_domain_profile(
        user_domain
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Semantic AI sees the ROLE/TITLE only.
    # --------------------------------------------------------

    job_text = f"""
    Internship role title:
    {job_title}
    """

    embeddings = model.encode(
        [
            domain_profile,
            job_text
        ]
    )

    similarity = cosine_similarity(
        [embeddings[0]],
        [embeddings[1]]
    )[0][0]

    score = float(
        similarity * 100
    )

    return round(
        max(
            0.0,
            min(score, 100.0)
        ),
        2
    )