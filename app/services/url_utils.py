from urllib.parse import (
    urlparse,
    parse_qsl,
    urlencode,
    urlunparse
)


# ============================================================
# URL TRACKING PARAMETERS
# ============================================================

TRACKING_BLACKLIST = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "refid",
    "trackingid",
    "ref",
    "spm",
    "click_id",
    "fbclid",
    "gclid"
}


# ============================================================
# CANONICALIZE JOB URL
# ============================================================

def canonicalize_job_url(raw_url: str) -> str:

    if not raw_url:
        return ""

    try:

        raw_url = raw_url.strip()

        parsed = urlparse(raw_url)

        scheme = parsed.scheme.lower()

        netloc = parsed.netloc.lower()

        if netloc.startswith("www."):
            netloc = netloc[4:]


        # ----------------------------------------------------
        # PATH
        # ----------------------------------------------------

        path = parsed.path.rstrip("/")


        # ----------------------------------------------------
        # QUERY PARAMETERS
        # ----------------------------------------------------

        query_params = parse_qsl(
            parsed.query,
            keep_blank_values=True
        )


        clean_params = [

            (key.lower(), value)

            for key, value
            in query_params

            if key.lower()
            not in TRACKING_BLACKLIST
        ]


        # ----------------------------------------------------
        # SORT PARAMETERS
        # ----------------------------------------------------

        clean_params.sort()

        query_string = urlencode(
            clean_params
        )


        # ----------------------------------------------------
        # REMOVE FRAGMENT
        # ----------------------------------------------------

        canonical_url = urlunparse((

            scheme,

            netloc,

            path,

            "",

            query_string,

            ""

        ))


        return canonical_url


    except Exception:

        return raw_url