# ============================================================
# JOB NORMALIZER
# ============================================================

def normalize_serpapi_job(job):
    """
    Convert a raw SerpApi Google Jobs result
    into our application's standard internship format.
    """

    title = (
        job.get("title") or ""
    ).strip()

    company = (
        job.get("company_name") or ""
    ).strip()

    location = (
        job.get("location")
        or "Location not specified"
    ).strip()

    description = (
        job.get("description")
        or ""
    ).strip()

    via = (
        job.get("via")
        or "Google Jobs"
    ).strip()

    # --------------------------------------------------------
    # FIND BEST APPLICATION URL
    # --------------------------------------------------------

    apply_options = (
        job.get("apply_options")
        or []
    )

    url = ""

    if apply_options:

        first_option = apply_options[0]

        url = (
            first_option.get("link")
            or ""
        ).strip()

    # --------------------------------------------------------
    # RETURN STANDARD FORMAT
    # --------------------------------------------------------

    return {
        "company": company,
        "title": title,
        "location": location,
        "description": description,
        "url": url,
        "source": "Google Jobs",
        "via": via,
    }