# ============================================================
# STRICT INTERNSHIP FILTER
# ============================================================

import re


# ============================================================
# STRONG INTERNSHIP SIGNALS
# ============================================================

INTERNSHIP_KEYWORDS = [
    "intern",
    "internship",
    "summer intern",
    "winter intern",
    "research intern",
    "engineering intern",
    "software intern",
    "developer intern",
    "student intern",
    "graduate intern",
    "industrial trainee",
    "graduate trainee",
    "apprentice",
    "apprenticeship",
    "student trainee",
]


# ============================================================
# STRONG NON-INTERNSHIP SIGNALS
# ============================================================

NON_INTERNSHIP_KEYWORDS = [
    "senior",
    "lead",
    "principal",
    "staff engineer",
    "manager",
    "director",
    "vice president",
    "vp",
    "head of",
]


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# WORD / PHRASE MATCH
# ============================================================

def contains_keyword(text, keyword):

    text = normalize_text(text)
    keyword = normalize_text(keyword)

    if not text or not keyword:
        return False

    pattern = r"\b" + re.escape(keyword) + r"\b"

    return re.search(
        pattern,
        text
    ) is not None


# ============================================================
# COMPANY MATCHING
# ============================================================

def company_matches(
    job_company,
    requested_company
):

    job_company = normalize_text(
        job_company
    )

    requested_company = normalize_text(
        requested_company
    )

    if not job_company or not requested_company:
        return False

    if job_company == requested_company:
        return True

    if (
        requested_company in job_company
        or job_company in requested_company
    ):
        return True

    return False


# ============================================================
# CHECK INTERNSHIP
# ============================================================

def is_internship(
    job_title,
    job_description="",
    employment_type=None
):

    title = normalize_text(
        job_title
    )

    description = normalize_text(
        job_description
    )

    employment = normalize_text(
        employment_type
    )

    # --------------------------------------------------------
    # NO TITLE
    # --------------------------------------------------------

    if not title:
        return False

    # --------------------------------------------------------
    # 1. NON-INTERNSHIP TITLE
    # --------------------------------------------------------

    for keyword in NON_INTERNSHIP_KEYWORDS:

        if contains_keyword(
            title,
            keyword
        ):
            return False

    # --------------------------------------------------------
    # 2. EXPLICIT INTERNSHIP TITLE
    # --------------------------------------------------------

    for keyword in INTERNSHIP_KEYWORDS:

        if contains_keyword(
            title,
            keyword
        ):
            return True

    # --------------------------------------------------------
    # 3. EMPLOYMENT TYPE
    # --------------------------------------------------------

    if employment:

        internship_types = [
            "intern",
            "internship",
            "trainee",
            "apprentice"
        ]

        for keyword in internship_types:

            if contains_keyword(
                employment,
                keyword
            ):
                return True

    # --------------------------------------------------------
    # 4. DESCRIPTION SIGNAL
    # --------------------------------------------------------

    internship_description_signals = [

        "internship opportunity",

        "internship program",

        "as an intern",

        "intern position",

        "intern role",

        "interns will",

        "intern will",

        "student internship",

        "summer internship",

        "graduate trainee",

        "industrial trainee",

        "apprenticeship program",
    ]

    for keyword in internship_description_signals:

        if contains_keyword(
            description,
            keyword
        ):
            return True

    # --------------------------------------------------------
    # 5. NOT AN INTERNSHIP
    # --------------------------------------------------------

    return False


# ============================================================
# EXTRACT JOB TITLE
# ============================================================

def get_job_title(job):

    return (
        job.get("title")
        or job.get("text")
        or ""
    ).strip()


# ============================================================
# FILTER INTERNSHIPS
# ============================================================

def filter_internships(
    jobs,
    requested_company=None
):

    filtered_jobs = []

    for job in jobs:

        # ----------------------------------------------------
        # JOB TITLE
        # ----------------------------------------------------

        title = get_job_title(job)

        if not title:
            continue

        # ----------------------------------------------------
        # DESCRIPTION
        # ----------------------------------------------------

        description = (
            job.get("description")
            or job.get("content")
            or ""
        )

        # ----------------------------------------------------
        # EMPLOYMENT TYPE
        # ----------------------------------------------------

        employment_type = (
            job.get("employment_type")
            or job.get("employmentType")
            or ""
        )

        # ----------------------------------------------------
        # STRICT INTERNSHIP FILTER
        # ----------------------------------------------------

        if is_internship(
            title,
            description,
            employment_type
        ):

            filtered_jobs.append(job)

    return filtered_jobs
