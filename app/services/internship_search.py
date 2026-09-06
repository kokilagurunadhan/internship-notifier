
# ============================================================
# INTERNSHIP SEARCH SERVICE
# File: app/services/internship_search.py
# ============================================================

import logging
import os
import random
import re
import time

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urlparse,
    urlunparse,
)

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================
# ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"

DEFAULT_MAX_PAGES = 3
MAX_ALLOWED_PAGES = 5

DEFAULT_MAX_WORKERS = 5

DEFAULT_TIMEOUT = 10.0

DEFAULT_LOCATION = "India"
DEFAULT_LANGUAGE = "en"

REQUEST_DELAY_SECONDS = 0.5

MAX_RETRIES = 3

MAX_SEEN_URLS = 10000
MAX_SEEN_IDENTITIES = 10000

MAX_SEARCH_CACHE_ENTRIES = 500
CACHE_TTL_SECONDS = 3600

USER_AGENT = (
    "InternshipNotifier/1.0 "
    "(internship-search-service)"
)


# ============================================================
# DIRECT CAREER SITE FALLBACK
# ============================================================

ENABLE_DIRECT_CAREER_FALLBACK = True

CAREER_FALLBACK_MAX_RESULTS = 20

MICROSOFT_ALTERNATE_JOB_DOMAIN = (
    "jobs.careers.microsoft.com"
)


# ============================================================
# CAREER DOMAIN ALIASES
# ============================================================

CAREER_DOMAIN_ALIASES = {
    "careers.microsoft.com": {
        "careers.microsoft.com",
        "jobs.careers.microsoft.com",
        "microsoft.wd5.myworkdayjobs.com",
    },
    "amazon.jobs": {
        "amazon.jobs",
    },
    "careers.google.com": {
        "careers.google.com",
    },
}


# ============================================================
# OUTDATED YEAR FILTER
# ============================================================

OUTDATED_YEARS = {
    "2021",
    "2022",
    "2023",
    "2024",
}


# ============================================================
# URL TRACKING PARAMETERS
# ============================================================

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "fbclid",
    "gclid",
}


# ============================================================
# STEP 7: INTERNSHIP + REQUISITION GATEKEEPER
# ============================================================


# ============================================================
# 7A. INTERNSHIP TITLE PATTERNS
# ============================================================

INTERNSHIP_TITLE_PATTERNS = (
    re.compile(
        r"\binternship\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bintern\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bco[- ]?op\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bstudent\s+"
        r"(software|engineering|developer|technology|"
        r"technical|research|data|machine learning|"
        r"ai|computer)",
        re.IGNORECASE,
    ),
)


# ============================================================
# 7B. NON-JOB TITLE PATTERNS
# ============================================================

NON_JOB_TITLE_PATTERNS = (
    re.compile(
        r"\b(internship|intern)\s+"
        r"(eligibility|faq|faqs|policy|policies|"
        r"overview|guidelines|information|resources)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(intern|internship)\s+"
        r"(pay|salary|compensation|benefits)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(careers?|locations?|about|culture|"
        r"benefits|faq|faqs|policy|policies|"
        r"portal|home|teams)\s*$",
        re.IGNORECASE,
    ),
)


# ============================================================
# 7C. EXACT NON-JOB PATH SEGMENTS
# ============================================================
#
# IMPORTANT:
#
# "students" and "student" are intentionally NOT here.
#
# They are handled by ROOT_LANDING_SEGMENTS.
#
# /students
#       -> REJECT
#
# /students/jobs/swe-intern-123
#       -> ALLOW
#
# ============================================================

EXACT_NON_JOB_SEGMENTS = {
    "eligibility",
    "internship-eligibility",
    "internship_eligibility",
    "intern-pay",
    "internship-pay",
    "salary",
    "pay",
    "benefits",
    "faq",
    "faqs",
    "policy",
    "policies",
    "culture",
}


# ============================================================
# 7D. EXACT NON-JOB PATH SLUGS
# ============================================================

NON_JOB_PATH_SLUGS = {
    "us-intern-pay-ranges",
    "us-intern-pay",
    "internship-faq",
}


# ============================================================
# 7E. ROOT LANDING SEGMENTS
# ============================================================

ROOT_LANDING_SEGMENTS = {
    "search",
    "teams",
    "locations",
    "about",
    "students",
    "student",
}


# ============================================================
# STEP 9: LOCATION NORMALIZATION
# ============================================================

STATE_ABBR_MAP = {
    # United States
    "al": "alabama",
    "ak": "alaska",
    "az": "arizona",
    "ar": "arkansas",
    "ca": "california",
    "co": "colorado",
    "ct": "connecticut",
    "de": "delaware",
    "fl": "florida",
    "ga": "georgia",
    "hi": "hawaii",
    "id": "idaho",
    "il": "illinois",
    "in": "indiana",
    "ia": "iowa",
    "ks": "kansas",
    "ky": "kentucky",
    "la": "louisiana",
    "me": "maine",
    "md": "maryland",
    "ma": "massachusetts",
    "mi": "michigan",
    "mn": "minnesota",
    "ms": "mississippi",
    "mo": "missouri",
    "mt": "montana",
    "ne": "nebraska",
    "nv": "nevada",
    "nh": "new hampshire",
    "nj": "new jersey",
    "nm": "new mexico",
    "ny": "new york",
    "nc": "north carolina",
    "nd": "north dakota",
    "oh": "ohio",
    "ok": "oklahoma",
    "or": "oregon",
    "pa": "pennsylvania",
    "ri": "rhode island",
    "sc": "south carolina",
    "sd": "south dakota",
    "tn": "tennessee",
    "tx": "texas",
    "ut": "utah",
    "vt": "vermont",
    "va": "virginia",
    "wa": "washington",
    "wv": "west virginia",
    "wi": "wisconsin",
    "wy": "wyoming",
}


LOCATION_ABBR_MAP = {
    **STATE_ABBR_MAP,

    # India
    "ka": "karnataka",
    "mh": "maharashtra",
    "dl": "delhi",
    "tn": "tamil nadu",
    "ts": "telangana",
    "tg": "telangana",
    "wb": "west bengal",
    "gj": "gujarat",
    "up": "uttar pradesh",
    "hr": "haryana",
    "pb": "punjab",
    "kl": "kerala",
    "ap": "andhra pradesh",
    "rj": "rajasthan",
    "mp": "madhya pradesh",
    "or": "odisha",
    "jh": "jharkhand",
    "uk": "uttarakhand",
}


# ============================================================
# SEARCH RESPONSE CACHE
# ============================================================

_SEARCH_CACHE: OrderedDict[
    str,
    Tuple[Dict[str, Any], float],
] = OrderedDict()

_CACHE_LOCK = Lock()


# ============================================================
# CUSTOM EXCEPTIONS
# ============================================================

class SerpAPIError(Exception):
    """Base exception for SerpAPI errors."""


class SerpAPIAuthError(SerpAPIError):
    """Raised when SerpAPI authentication fails."""


class SerpAPIQuotaExceeded(SerpAPIError):
    """Raised when SerpAPI quota or rate limits are exceeded."""


# ============================================================
# API KEY
# ============================================================

def _get_api_key(
    api_key: Optional[str] = None,
) -> str:
    key = (
        api_key
        or os.getenv("SERPAPI_API_KEY")
        or os.getenv("SERPAPI_KEY")
        or ""
    ).strip()

    if not key:
        raise SerpAPIAuthError(
            "SERPAPI_API_KEY is missing."
        )

    logger.info(
        "SerpAPI API key loaded successfully."
    )

    return key


# ============================================================
# REQUEST SESSION
# ============================================================

def _create_session() -> requests.Session:
    """
    Creates a reusable HTTP session.

    The actual SerpAPI retry logic is handled explicitly by
    _request_serpapi(), so urllib3 retries are disabled here.
    """

    session = requests.Session()

    retry_strategy = Retry(
        total=0,
        connect=0,
        read=0,
        redirect=3,
        status=0,
    )

    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,
        pool_maxsize=20,
    )

    session.mount(
        "http://",
        adapter,
    )

    session.mount(
        "https://",
        adapter,
    )

    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
    )

    return session


# ============================================================
# SEARCH TERM
# ============================================================

def _quote_search_term(
    value: str,
) -> str:
    value = (
        value or ""
    ).strip()

    if not value:
        return ""

    return value.strip('"').strip()


# ============================================================
# STEP 8: URL NORMALIZATION
# ============================================================

# ============================================================
# STEP 8: URL NORMALIZATION
# ============================================================

def _normalize_url(
    url: str,
) -> str:
    """
    Canonicalizes a URL for duplicate detection.

    Removes:
        - URL fragments
        - tracking parameters
        - trailing slash
        - default HTTP/HTTPS ports

    Preserves:
        - legitimate query parameters
        - non-default ports
        - path case
        - HTTP vs HTTPS
    """

    if not url:
        return ""

    url = url.strip()

    if not url:
        return ""

    try:
        parsed = urlparse(url)

        if not parsed.scheme or not parsed.netloc:
            return ""

        scheme = parsed.scheme.lower()

        # ----------------------------------------------------
        # HOST + PORT NORMALIZATION
        # ----------------------------------------------------

        hostname = (
            parsed.hostname or ""
        ).lower().rstrip(".")

        if not hostname:
            return ""

        port = parsed.port

        # Remove only the default port for the scheme.
        if (
            (scheme == "https" and port == 443)
            or
            (scheme == "http" and port == 80)
        ):
            netloc = hostname

        elif port is not None:
            netloc = f"{hostname}:{port}"

        else:
            netloc = hostname

        # ----------------------------------------------------
        # QUERY PARAMETER NORMALIZATION
        # ----------------------------------------------------

        query_params = parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )

        filtered_params = []

        for key, value in query_params:

            key_lower = key.lower()

            if key_lower in TRACKING_PARAMS:
                continue

            if key_lower.startswith("utm_"):
                continue

            filtered_params.append(
                (key, value)
            )

        clean_query = urlencode(
            filtered_params,
            doseq=True,
        )

        # ----------------------------------------------------
        # PATH NORMALIZATION
        # ----------------------------------------------------

        path = (
            parsed.path.rstrip("/")
            or "/"
        )

        # ----------------------------------------------------
        # FINAL CANONICAL URL
        # ----------------------------------------------------

        return urlunparse(
            (
                scheme,
                netloc,
                path,
                "",
                clean_query,
                "",
            )
        )

    except Exception as error:

        logger.warning(
            "Failed to normalize URL | "
            "url=%s | error=%s",
            url,
            error,
        )

        return ""
# ============================================================
# DOMAIN NORMALIZATION
# ============================================================

def _normalize_domain(
    domain: Optional[str],
) -> str:
    if not domain:
        return ""

    value = (
        str(domain)
        .strip()
        .lower()
    )

    value = value.replace(
        "https://",
        "",
    ).replace(
        "http://",
        "",
    )

    value = value.split("/")[0]

    return value.strip().rstrip(".")


# ============================================================
# DISPLAY URL CLEANUP
# ============================================================

def _clean_display_url(
    url: str,
) -> str:
    """
    Cleans URLs before validation.

    Handles:
        - schemeless URLs
        - percent encoding
        - escaped Unicode sequences such as \\u003d
        - Google redirect URLs
        - Google international domains
        - nested encoded redirect targets
    """

    if not url:
        return ""

    value = str(url).strip()

    if not value:
        return ""

    # --------------------------------------------------------
    # DECODE PERCENT / URL ENCODING
    # --------------------------------------------------------

    for _ in range(3):
        decoded = unquote(value)

        if decoded == value:
            break

        value = decoded

    # --------------------------------------------------------
    # DECODE JAVASCRIPT / JSON STYLE UNICODE ESCAPES
    # Example:
    #
    # \u003d  -> =
    # \u0026  -> &
    # --------------------------------------------------------

    try:
        value = re.sub(
            r"\\u([0-9a-fA-F]{4})",
            lambda match: chr(
                int(match.group(1), 16)
            ),
            value,
        )
    except Exception:
        pass

    # --------------------------------------------------------
    # PREPEND SCHEME
    # --------------------------------------------------------

    if not value.startswith(
        (
            "http://",
            "https://",
        )
    ):
        value = (
            "https://"
            + value.lstrip("/")
        )

    # --------------------------------------------------------
    # GOOGLE REDIRECT UNWRAPPING
    # --------------------------------------------------------

    try:
        parsed = urlparse(value)

        hostname = (
            parsed.hostname
            or ""
        ).lower().rstrip(".")

        is_google_host = (
            hostname == "google.com"
            or hostname.startswith("www.google.")
            or hostname.startswith("google.")
        )

        if (
            is_google_host
            and parsed.path.rstrip("/") == "/url"
        ):
            query_params = parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )

            query_dict = dict(query_params)

            target = (
                query_dict.get("q")
                or query_dict.get("url")
                or query_dict.get("u")
            )

            if target:
                target = unquote(
                    target
                ).strip()

                try:
                    target = re.sub(
                        r"\\u([0-9a-fA-F]{4})",
                        lambda match: chr(
                            int(match.group(1), 16)
                        ),
                        target,
                    )
                except Exception:
                    pass

                if not target.startswith(
                    (
                        "http://",
                        "https://",
                    )
                ):
                    target = (
                        "https://"
                        + target.lstrip("/")
                    )

                value = target

    except Exception as error:
        logger.warning(
            "Failed to clean display URL | "
            "url=%s | error=%s",
            url,
            error,
        )

        return ""

    return value.strip()

# ============================================================
# CAREER DOMAIN ALIASES
# ============================================================

def _allowed_career_domains(
    domain: Optional[str],
) -> Set[str]:
    clean = _normalize_domain(domain)

    if not clean:
        return set()

    return set(
        CAREER_DOMAIN_ALIASES.get(
            clean,
            {clean},
        )
    )


# ============================================================
# STEP 6: CAREER DOMAIN VALIDATION
# ============================================================

def _is_career_domain_url(
    url: str,
    domain: Optional[str],
) -> bool:
    """
    Validates the final target hostname.

    Example:

        careers.microsoft.com
        jobs.careers.microsoft.com

    are allowed for:

        careers.microsoft.com

    But:

        careers.microsoft.com.attacker.com

    is rejected.
    """

    clean_url = _clean_display_url(url)

    if not clean_url or not domain:
        return False

    allowed_domains = _allowed_career_domains(domain)

    if not allowed_domains:
        return False

    try:
        parsed = urlparse(clean_url)

        hostname = (
            parsed.hostname
            or ""
        ).lower().rstrip(".")

        if not hostname:
            return False

        for allowed in allowed_domains:
            allowed = (
                allowed.lower().rstrip(".")
            )

            if (
                hostname == allowed
                or hostname.endswith(
                    "." + allowed
                )
            ):
                return True

        return False

    except Exception as error:
        logger.warning(
            "Career domain validation failed | "
            "url=%s | domain=%s | error=%s",
            url,
            domain,
            error,
        )

        return False


# ============================================================
# STEP 7A: INTERNSHIP TITLE VALIDATION
# ============================================================

def _is_valid_internship_title(
    title: str,
) -> bool:

    if not title:
        return False

    title = title.strip()

    if not title:
        return False

    # --------------------------------------------------------
    # NON-JOB TITLE CHECK
    # --------------------------------------------------------

    if any(
        pattern.search(title)
        for pattern in NON_JOB_TITLE_PATTERNS
    ):
        return False

    # --------------------------------------------------------
    # ADDITIONAL PAY / COMPENSATION TITLES
    # --------------------------------------------------------

    lowered = title.lower()

    if (
        "base pay" in lowered
        or "pay ranges" in lowered
        or "salary range" in lowered
        or "salary information" in lowered
        or "compensation information" in lowered
        or "benefits information" in lowered
    ):
        return False

    # --------------------------------------------------------
    # INTERNSHIP TITLE
    # --------------------------------------------------------

    return any(
        pattern.search(title)
        for pattern in INTERNSHIP_TITLE_PATTERNS
    )

# ============================================================
# STEP 7B: ACTUAL JOB URL VALIDATION
# ============================================================

def _is_actual_job_url(
    url: str,
) -> bool:
    if not url:
        return False

    clean_url = _clean_display_url(url)

    if not clean_url:
        return False

    try:
        parsed = urlparse(clean_url)

        path = (
            parsed.path
            or ""
        ).lower().strip("/")

        if not path:
            return False

        segments = [
            segment
            for segment in path.split("/")
            if segment
        ]

        # ----------------------------------------------------
        # EXACT NON-JOB SEGMENTS
        # ----------------------------------------------------

        if any(
            segment in EXACT_NON_JOB_SEGMENTS
            for segment in segments
        ):
            return False

        # ----------------------------------------------------
        # EXACT NON-JOB SLUGS
        # ----------------------------------------------------

        if any(
            segment in NON_JOB_PATH_SLUGS
            for segment in segments
        ):
            return False

        # ----------------------------------------------------
        # ROOT LANDING CHECK
        # ----------------------------------------------------

        if (
            len(segments) == 1
            and segments[0]
            in ROOT_LANDING_SEGMENTS
        ):
            return False

        return True

    except Exception as error:
        logger.warning(
            "STEP 7 URL validation failed | "
            "url=%s | error=%s",
            url,
            error,
        )

        return False


# ============================================================
# STEP 7: FINAL INTERNSHIP REQUISITION GATEKEEPER
# ============================================================

def _is_valid_internship_posting(
    title: str,
    url: str,
) -> bool:
    if not _is_valid_internship_title(title):
        return False

    if not _is_actual_job_url(url):
        return False

    return True


# ============================================================
# FALLBACK JOB URL CHECK
# ============================================================

def _looks_like_job_posting_url(
    url: str,
    domain: str,
) -> bool:
    """
    Validate whether a career-site URL looks like an actual
    job posting rather than a search, landing, FAQ, policy,
    salary, or other informational page.
    """

    clean_url = _clean_display_url(url)

    if not clean_url:
        return False

    try:
        parsed = urlparse(clean_url)

        hostname = (
            parsed.hostname or ""
        ).lower().rstrip(".")

        path = (
            parsed.path or ""
        ).lower()

        if not hostname:
            return False

        clean_domain = _normalize_domain(domain)

        path_segments = [
            segment
            for segment in path.strip("/").split("/")
            if segment
        ]

        # ----------------------------------------------------
        # UNIVERSAL NON-JOB PATHS
        # ----------------------------------------------------

        if any(
            segment in EXACT_NON_JOB_SEGMENTS
            for segment in path_segments
        ):
            return False

        if any(
            segment in NON_JOB_PATH_SLUGS
            for segment in path_segments
        ):
            return False

        if (
            len(path_segments) == 1
            and path_segments[0] in ROOT_LANDING_SEGMENTS
        ):
            return False

        # ----------------------------------------------------
        # AMAZON
        # ----------------------------------------------------

        if (
    hostname == "amazon.jobs"
    or hostname.endswith(".amazon.jobs")
):

            # Amazon search pages are NOT job postings.
            if "search" in path_segments:
                return False

            # Actual Amazon job URLs.
            if "job" in path_segments:
                return True

            if "jobs" in path_segments:
                return True

            return False

        # ----------------------------------------------------
        # MICROSOFT
        # ----------------------------------------------------

        if hostname == MICROSOFT_ALTERNATE_JOB_DOMAIN:
            return (
                "/job/" in path
                or path.rstrip("/").endswith("/job")
            )

        # ----------------------------------------------------
        # GOOGLE
        # ----------------------------------------------------

        if hostname == "careers.google.com":
            return "/jobs/results/" in path

        # ----------------------------------------------------
        # OTHER CAREER DOMAINS
        # ----------------------------------------------------

        if clean_domain:

            if not _is_career_domain_url(
                clean_url,
                clean_domain,
            ):
                return False

        return _is_actual_job_url(clean_url)

    except Exception:
        return False
# STEP 9A: IDENTITY TEXT NORMALIZATION
# ============================================================

def _normalize_identity_text(
    value: Any,
) -> str:
    value = str(value or "").lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


# ============================================================
# STEP 9B: LOCATION NORMALIZATION
# ============================================================

def _normalize_location(
    location: Any,
) -> str:
    text = _normalize_identity_text(location)

    if not text:
        return ""

    tokens = text.split()

    normalized_tokens = [
        LOCATION_ABBR_MAP.get(
            token,
            token,
        )
        for token in tokens
    ]

    return " ".join(normalized_tokens)


# ============================================================
# STEP 9C: JOB IDENTITY KEY
# ============================================================

def _job_identity_key(
    job: Dict[str, Any],
) -> str:
    company = _normalize_identity_text(
        job.get("company")
    )

    title = _normalize_identity_text(
        job.get("title")
    )

    location = _normalize_location(
        job.get("location")
    )

    if not company or not title:
        return ""

    return (
        f"{company}|"
        f"{title}|"
        f"{location}"
    )


# ============================================================
# STEP 9D: CROSS-PLATFORM IDENTITY DEDUPLICATION
# ============================================================

def _remember_job_identity(
    job: Dict[str, Any],
    seen_identities,
    lock: Optional[Lock] = None,
) -> bool:

    identity = _job_identity_key(
        job
    )

    if not identity:
        return True

    def remember() -> bool:

        # ----------------------------------------------------
        # NORMAL SET
        # ----------------------------------------------------

        if isinstance(
            seen_identities,
            set,
        ):

            if identity in seen_identities:
                return False

            seen_identities.add(
                identity
            )

            return True

        # ----------------------------------------------------
        # ORDERED DICT
        # ----------------------------------------------------

        if identity in seen_identities:

            if hasattr(
                seen_identities,
                "move_to_end",
            ):
                seen_identities.move_to_end(
                    identity
                )

            return False

        seen_identities[identity] = None

        while (
            len(seen_identities)
            > MAX_SEEN_IDENTITIES
        ):

            oldest = next(
                iter(seen_identities)
            )

            del seen_identities[
                oldest
            ]

        return True

    if lock:
        with lock:
            return remember()

    return remember()

# ============================================================
# STEP 9E: EXACT URL DEDUPLICATION
# ============================================================

def _remember_url(
    url: str,
    seen_urls,
    lock: Optional[Lock] = None,
) -> bool:

    clean_url = _normalize_url(
        _clean_display_url(url)
    )

    if not clean_url:
        return False

    def remember() -> bool:

        # ----------------------------------------------------
        # NORMAL SET
        # ----------------------------------------------------

        if isinstance(
            seen_urls,
            set,
        ):

            if clean_url in seen_urls:
                return False

            seen_urls.add(
                clean_url
            )

            return True

        # ----------------------------------------------------
        # ORDERED DICT
        # ----------------------------------------------------

        if clean_url in seen_urls:

            if hasattr(
                seen_urls,
                "move_to_end",
            ):
                seen_urls.move_to_end(
                    clean_url
                )

            return False

        seen_urls[clean_url] = None

        while (
            len(seen_urls)
            > MAX_SEEN_URLS
        ):

            oldest = next(
                iter(seen_urls)
            )

            del seen_urls[oldest]

        return True

    if lock:
        with lock:
            return remember()

    return remember()

# ============================================================
# EXTRACT BEST JOB URL
# ============================================================

def _extract_best_url(
    job: Dict[str, Any],
) -> str:
    """
    Extracts a real application/career URL.

    IMPORTANT:
    We intentionally do NOT manufacture a Google search URL
    from job_id. A synthetic Google URL is not a reliable
    canonical application URL.
    """

    if not isinstance(
        job,
        dict,
    ):
        return ""

    apply_options = job.get(
        "apply_options",
        [],
    )

    preferred_keywords = {
        "company",
        "careers",
        "workday",
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "jobvite",
    }

    # --------------------------------------------------------
    # PREFERRED APPLY LINKS
    # --------------------------------------------------------

    if isinstance(
        apply_options,
        list,
    ):

        for option in apply_options:

            if not isinstance(
                option,
                dict,
            ):
                continue

            link = (
                option.get("link")
                or ""
            ).strip()

            title = (
                option.get("title")
                or ""
            ).lower()

            if (
                link
                and any(
                    keyword in title
                    for keyword in preferred_keywords
                )
            ):
                return link

        # ----------------------------------------------------
        # ANY APPLY LINK
        # ----------------------------------------------------

        for option in apply_options:

            if not isinstance(
                option,
                dict,
            ):
                continue

            link = (
                option.get("link")
                or ""
            ).strip()

            if link:
                return link

    # --------------------------------------------------------
    # RELATED LINKS
    # --------------------------------------------------------

    related_links = job.get(
        "related_links",
        [],
    )

    if isinstance(
        related_links,
        list,
    ):

        for item in related_links:

            if not isinstance(
                item,
                dict,
            ):
                continue

            link = (
                item.get("link")
                or ""
            ).strip()

            if link:
                return link

    # --------------------------------------------------------
    # DIRECT LINK
    # --------------------------------------------------------

    direct_link = (
        job.get("link")
        or ""
    ).strip()

    if direct_link:
        return direct_link

    # --------------------------------------------------------
    # SHARE LINK
    # --------------------------------------------------------

    share_link = (
        job.get("share_link")
        or ""
    ).strip()

    if share_link:
        return share_link

    # --------------------------------------------------------
    # NO REAL URL
    # --------------------------------------------------------

    return ""
# ============================================================
# RETRY-AFTER
# ============================================================

def _get_retry_after(
    response: requests.Response,
) -> Optional[float]:
    value = response.headers.get(
        "Retry-After"
    )

    if not value:
        return None

    value = value.strip()

    # --------------------------------------------------------
    # SECONDS
    # --------------------------------------------------------

    try:
        seconds = float(value)

        return max(
            0.0,
            seconds,
        )

    except ValueError:
        pass

    # --------------------------------------------------------
    # HTTP DATE
    # --------------------------------------------------------

    try:
        retry_date = parsedate_to_datetime(
            value
        )

        if retry_date.tzinfo is None:
            retry_date = retry_date.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        delay = (
            retry_date - now
        ).total_seconds()

        return max(
            0.0,
            delay,
        )

    except Exception:
        return None


# ============================================================
# BACKOFF
# ============================================================

def _calculate_backoff(
    attempt: int,
) -> float:
    base = 2 ** (
        attempt - 1
    )

    jitter = random.uniform(
        0.1,
        0.5,
    )

    return base + jitter


# ============================================================
# REQUEST SERPAPI
# ============================================================

def _request_serpapi(
    session: requests.Session,
    params: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        # ====================================================
        # REQUEST
        # ====================================================

        try:
            response = session.get(
                SERPAPI_ENDPOINT,
                params=params,
                timeout=timeout,
            )

        except requests.RequestException as error:

            if attempt >= MAX_RETRIES:
                raise SerpAPIError(
                    "SerpAPI request failed "
                    "after maximum retries."
                ) from error

            delay = _calculate_backoff(attempt)

            logger.warning(
                "SerpAPI request failed. "
                "Retrying in %.2f seconds.",
                delay,
            )

            time.sleep(delay)

            continue

        # ====================================================
        # AUTHENTICATION
        # ====================================================

        if response.status_code == 401:
            raise SerpAPIAuthError(
                "Invalid SerpAPI API key."
            )

        # ====================================================
        # FORBIDDEN / QUOTA
        # ====================================================

        if response.status_code == 403:
            raise SerpAPIQuotaExceeded(
                "SerpAPI access forbidden "
                "or quota exceeded."
            )

        # ====================================================
        # RATE LIMIT — HTTP 429
        # ====================================================

        if response.status_code == 429:

            if attempt >= MAX_RETRIES:
                raise SerpAPIQuotaExceeded(
                    "SerpAPI rate limit exceeded "
                    "after maximum retries."
                )

            retry_after = _get_retry_after(
                response
            )

            delay = (
                retry_after
                if retry_after is not None
                else _calculate_backoff(attempt)
            )

            logger.warning(
                "SerpAPI rate limited "
                "(HTTP 429). "
                "Retrying in %.2f seconds.",
                delay,
            )

            time.sleep(delay)

            continue

        # ====================================================
        # SERVER ERRORS
        # ====================================================

        if response.status_code >= 500:

            if attempt >= MAX_RETRIES:
                raise SerpAPIError(
                    "SerpAPI server error: "
                    f"{response.status_code}"
                )

            retry_after = _get_retry_after(
                response
            )

            delay = (
                retry_after
                if retry_after is not None
                else _calculate_backoff(attempt)
            )

            logger.warning(
                "SerpAPI server error "
                "%s. Retrying in %.2f seconds.",
                response.status_code,
                delay,
            )

            time.sleep(delay)

            continue

        # ====================================================
        # OTHER HTTP ERRORS
        # ====================================================

        if response.status_code != 200:
            raise SerpAPIError(
                "SerpAPI returned HTTP "
                f"status {response.status_code}."
            )

        # ====================================================
        # JSON PARSING
        # ====================================================

        try:
            data = response.json()

        except ValueError as error:
            raise SerpAPIError(
                "Invalid JSON response "
                "from SerpAPI."
            ) from error

        if not isinstance(
            data,
            dict,
        ):
            raise SerpAPIError(
                "SerpAPI returned invalid "
                "JSON structure."
            )

        # ====================================================
        # API-LEVEL ERROR
        # ====================================================

        if "error" in data:

            error_message = str(
                data.get("error")
            )

            lower_message = (
                error_message.lower()
            )

            # -----------------------------------------------
            # AUTH ERROR
            # -----------------------------------------------

            if (
                "api key" in lower_message
                or "authentication" in lower_message
                or "unauthorized" in lower_message
            ):
                raise SerpAPIAuthError(
                    error_message
                )

            # -----------------------------------------------
            # QUOTA / RATE LIMIT
            # -----------------------------------------------

            if (
                "quota" in lower_message
                or "rate limit" in lower_message
                or "requests" in lower_message
                or "searches" in lower_message
            ):
                raise SerpAPIQuotaExceeded(
                    error_message
                )

            # -----------------------------------------------
            # GENERAL API ERROR
            # -----------------------------------------------

            raise SerpAPIError(
                "SerpAPI error: "
                f"{error_message}"
            )

        return data

    raise SerpAPIError(
        "SerpAPI request failed "
        "after maximum retries."
    )


# ============================================================
# SEARCH RESPONSE CACHE
# ============================================================

def _get_cached_response(
    cache_key: str,
) -> Optional[Dict[str, Any]]:

    with _CACHE_LOCK:

        cached = _SEARCH_CACHE.get(
            cache_key
        )

        if cached is None:
            return None

        data, timestamp = cached

        age = (
            time.time()
            - timestamp
        )

        if age >= CACHE_TTL_SECONDS:
            del _SEARCH_CACHE[cache_key]
            return None

        _SEARCH_CACHE.move_to_end(
            cache_key
        )

        return data


def _set_cached_response(
    cache_key: str,
    data: Dict[str, Any],
) -> None:

    with _CACHE_LOCK:

        _SEARCH_CACHE[cache_key] = (
            data,
            time.time(),
        )

        _SEARCH_CACHE.move_to_end(
            cache_key
        )

        while (
            len(_SEARCH_CACHE)
            > MAX_SEARCH_CACHE_ENTRIES
        ):
            _SEARCH_CACHE.popitem(
                last=False
            )


# ============================================================
# OUTDATED LISTING DETECTION
# ============================================================

def _contains_outdated_year(
    text: str,
) -> bool:
    if not text:
        return False

    text_lower = text.lower()

    return any(
        year in text_lower
        for year in OUTDATED_YEARS
    )


# ============================================================
# EXTRACT POSTED DATE
# ============================================================

def _extract_posted_at(
    job: Dict[str, Any],
) -> str:

    if not isinstance(
        job,
        dict,
    ):
        return ""

    detected_extensions = job.get(
        "detected_extensions",
        {},
    )

    if isinstance(
        detected_extensions,
        dict,
    ):
        return str(
            detected_extensions.get(
                "posted_at"
            )
            or ""
        ).strip()

    return ""
# ============================================================
# NORMALIZE JOB
# ============================================================

def _normalize_job(
    job: Dict[str, Any],
    requested_company: str,
) -> Optional[Dict[str, Any]]:

    if not isinstance(
        job,
        dict,
    ):
        return None

    title = (
        job.get("title")
        or ""
    ).strip()

    if not title:
        return None

    if _contains_outdated_year(title):
        logger.info(
            "Outdated job skipped | "
            "company=%s | title=%s",
            requested_company,
            title,
        )

        return None

    company = (
        job.get("company_name")
        or job.get("company")
        or requested_company
        or ""
    ).strip()

    if not company:
        return None

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

    url = _extract_best_url(job)

    if not url:
        logger.debug(
            "Job skipped because no real URL "
            "was found | company=%s | title=%s",
            company,
            title,
        )

        return None

    posted_at = _extract_posted_at(job)

    return {
        "company": company,
        "title": title,
        "location": location,
        "description": description,
        "source": "SerpAPI",
        "via": via,
        "url": url,
        "relevance_score": None,
        "passed_filter": False,
        "status": "NEW",
        "email_sent": False,
        "posted_at": posted_at,
        "raw_data": job,
    }


# ============================================================
# EXTRACT ORGANIC RESULT LOCATION
# ============================================================

def _extract_organic_location(
    result: Dict[str, Any],
) -> str:
    """
    Extracts location information from a SerpAPI organic result.

    Checks common SerpAPI location fields first, then falls back
    to extensions contained in rich snippets.

    Returns:
        Location string, or "Location not specified"
    """

    if not isinstance(result, dict):
        return "Location not specified"

    # --------------------------------------------------------
    # DIRECT LOCATION FIELDS
    # --------------------------------------------------------

    for key in (
        "location",
        "job_location",
        "formatted_location",
    ):
        value = result.get(key)

        if value:
            return str(value).strip()

    # --------------------------------------------------------
    # TOP-LEVEL EXTENSIONS
    # --------------------------------------------------------

    extensions = result.get("extensions")

    if isinstance(extensions, list):
        values = [
            str(value).strip()
            for value in extensions
            if value
        ]

        if values:
            return ", ".join(values)

    # --------------------------------------------------------
    # RICH SNIPPET
    # --------------------------------------------------------

    rich_snippet = result.get("rich_snippet")

    if isinstance(rich_snippet, dict):

        for section in (
            "top",
            "bottom",
        ):

            section_data = rich_snippet.get(section)

            if not isinstance(
                section_data,
                dict,
            ):
                continue

            extensions = section_data.get(
                "extensions"
            )

            if isinstance(extensions, list):

                values = [
                    str(value).strip()
                    for value in extensions
                    if value
                ]

                if values:
                    return ", ".join(values)

    # --------------------------------------------------------
    # NO LOCATION
    # --------------------------------------------------------

    return "Location not specified"


# ============================================================
# NORMALIZE ORGANIC RESULT
# ============================================================

def _normalize_organic_result(
    result: Dict[str, Any],
    requested_company: str,
) -> Optional[Dict[str, Any]]:
    """
    Normalizes a Google organic search result into the same
    internal internship structure used by Google Jobs results.
    """

    if not isinstance(result, dict):
        return None

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = (
        result.get("title")
        or ""
    ).strip()

    if not title:
        return None

    # --------------------------------------------------------
    # OUTDATED YEAR FILTER
    # --------------------------------------------------------

    if _contains_outdated_year(title):
        logger.info(
            "Outdated organic result skipped | "
            "company=%s | title=%s",
            requested_company,
            title,
        )

        return None

    # --------------------------------------------------------
    # COMPANY
    # --------------------------------------------------------

    company = (
        result.get("company_name")
        or result.get("company")
        or requested_company
        or ""
    ).strip()

    if not company:
        return None

    # --------------------------------------------------------
    # LOCATION
    # --------------------------------------------------------

    location = _extract_organic_location(
        result
    )

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = (
        result.get("snippet")
        or result.get("description")
        or ""
    ).strip()

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    url = (
        result.get("link")
        or ""
    ).strip()

    if not url:
        return None

    # --------------------------------------------------------
    # VIA
    # --------------------------------------------------------

    via = (
    result.get("via")
    or "Direct Career Site"
).strip()

    # --------------------------------------------------------
    # POSTED DATE
    # --------------------------------------------------------

    posted_at = _extract_posted_at(
        result
    )

    # --------------------------------------------------------
    # NORMALIZED RESULT
    # --------------------------------------------------------

    return {
        "company": company,
        "title": title,
        "location": location,
        "description": description,
        "source": "SerpAPI",
        "via": via,
        "url": url,
        "relevance_score": None,
        "passed_filter": False,
        "status": "NEW",
        "email_sent": False,
        "posted_at": posted_at,
        "raw_data": result,
    }

def _extract_organic_location(
    result: Dict[str, Any],
) -> str:
    """
    Extracts location information from a SerpAPI organic result.

    Checks common SerpAPI location fields first, then falls back
    to extensions contained in rich snippets.

    Returns:
        Location string, or "Location not specified"
    """

    if not isinstance(result, dict):
        return "Location not specified"

    # --------------------------------------------------------
    # DIRECT LOCATION FIELDS
    # --------------------------------------------------------

    for key in (
        "location",
        "job_location",
        "formatted_location",
    ):
        value = result.get(key)

        if value:
            return str(value).strip()

    # --------------------------------------------------------
    # TOP-LEVEL EXTENSIONS
    # --------------------------------------------------------

    extensions = result.get("extensions")

    if isinstance(extensions, list):
        values = [
            str(value).strip()
            for value in extensions
            if value
        ]

        if values:
            return ", ".join(values)

    # --------------------------------------------------------
    # RICH SNIPPET
    # --------------------------------------------------------

    rich_snippet = result.get("rich_snippet")

    if isinstance(rich_snippet, dict):

        for section in (
            "top",
            "bottom",
        ):

            section_data = rich_snippet.get(section)

            if not isinstance(
                section_data,
                dict,
            ):
                continue

            extensions = section_data.get(
                "extensions"
            )

            if isinstance(extensions, list):

                values = [
                    str(value).strip()
                    for value in extensions
                    if value
                ]

                if values:
                    return ", ".join(values)

    # --------------------------------------------------------
    # NO LOCATION
    # --------------------------------------------------------

    return "Location not specified"

# ============================================================
# SESSION HELPER
# ============================================================

def active_session_if_needed(
    session: requests.Session,
) -> requests.Session:
    """
    Compatibility helper.

    The caller normally provides an active session.
    """

    return session


# ============================================================
# DIRECT CAREER SITE FALLBACK
# ============================================================

# ============================================================
# DIRECT CAREER SITE FALLBACK
# ============================================================
def _search_direct_career_site(
    company: str,
    domain: str,
    api_key: str,
    timeout: float,
    seen_urls,
    seen_urls_lock: Optional[Lock] = None,
    seen_identities=None,
    seen_identities_lock: Optional[Lock] = None,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:

    clean_domain = _normalize_domain(
        domain
    )

    if not clean_domain:
        return []

    company_term = _quote_search_term(
        company
    )

    if clean_domain == "careers.microsoft.com":

        query = (
            "(site:jobs.careers.microsoft.com "
            "OR site:careers.microsoft.com) "
            f"{company_term} internship"
        )

    else:

        query = (
            f"site:{clean_domain} "
            f"{company_term} internship"
        )

    logger.info(
        "Starting direct career-site fallback | "
        "company=%s | domain=%s | query=%s",
        company,
        clean_domain,
        query,
    )

    params = {
        "engine": "google",
        "q": query,
        "location": DEFAULT_LOCATION,
        "hl": DEFAULT_LANGUAGE,
        "num": CAREER_FALLBACK_MAX_RESULTS,
        "api_key": api_key,
    }

    if session is None:
        session = _create_session()
        own_session = True
    else:
        own_session = False

    try:

        data = _request_serpapi(
            session=active_session_if_needed(
                session
            ),
            params=params,
            timeout=timeout,
        )

        organic_results = data.get(
            "organic_results",
            [],
        )

        if not isinstance(
            organic_results,
            list,
        ):
            return []

        internships: List[
            Dict[str, Any]
        ] = []

        # ----------------------------------------------------
        # DEFAULT IDENTITY STORE
        # ----------------------------------------------------

        if seen_identities is None:
            seen_identities = OrderedDict()

        # ----------------------------------------------------
        # PROCESS ORGANIC RESULTS
        # ----------------------------------------------------

        for result in organic_results:

            normalized = _normalize_organic_result(
                result=result,
                requested_company=company,
            )

            if normalized is None:
                continue

            # ------------------------------------------------
            # FALLBACK DOMAIN VALIDATION
            # ------------------------------------------------

            if not _looks_like_job_posting_url(
                normalized["url"],
                clean_domain,
            ):
                logger.info(
                    "Direct fallback rejected non-job URL | "
                    "company=%s | url=%s",
                    company,
                    normalized["url"],
                )
                continue

            # ------------------------------------------------
            # URL NORMALIZATION
            # ------------------------------------------------

            original_url = _clean_display_url(
                normalized["url"]
            )

            if not original_url:
                continue

            canonical_url = _normalize_url(
                original_url
            )

            if not canonical_url:
                continue

            normalized["url"] = canonical_url

            # ------------------------------------------------
            # URL DEDUPLICATION
            # ------------------------------------------------

            if not _remember_url(
                canonical_url,
                seen_urls,
                seen_urls_lock,
            ):
                continue

            # ------------------------------------------------
            # IDENTITY DEDUPLICATION
            # ------------------------------------------------

            if not _remember_job_identity(
                normalized,
                seen_identities,
                seen_identities_lock,
            ):
                continue

            # ------------------------------------------------
            # SAVE RESULT
            # ------------------------------------------------

            internships.append(
                normalized
            )

        logger.info(
            "Direct career-site fallback completed | "
            "company=%s | results=%s",
            company,
            len(internships),
        )

        return internships

    finally:

        if own_session:
            session.close()
# ============================================================
# SINGLE COMPANY SEARCH
# ============================================================

def search_internships(
    company: str,
    domain: Optional[str] = None,
    api_key: Optional[str] = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: float = DEFAULT_TIMEOUT,
    seen_urls: Optional[OrderedDict] = None,
    seen_urls_lock: Optional[Lock] = None,
    seen_identities: Optional[OrderedDict] = None,
    seen_identities_lock: Optional[Lock] = None,
    session: Optional[requests.Session] = None,
    request_delay: float = REQUEST_DELAY_SECONDS,
) -> List[Dict[str, Any]]:

    company = (
        company or ""
    ).strip()

    if not company:
        logger.warning(
            "Empty company supplied. "
            "Search skipped."
        )

        return []

    key = _get_api_key(api_key)

    # --------------------------------------------------------
    # MAX PAGES
    # --------------------------------------------------------

    try:
        max_pages = int(max_pages)

    except (
        TypeError,
        ValueError,
    ):
        max_pages = 1

    max_pages = max(
        1,
        min(
            max_pages,
            MAX_ALLOWED_PAGES,
        ),
    )

    # --------------------------------------------------------
    # TIMEOUT
    # --------------------------------------------------------

    try:
        timeout = float(timeout)

    except (
        TypeError,
        ValueError,
    ):
        timeout = DEFAULT_TIMEOUT

    timeout = max(
        1.0,
        timeout,
    )

    # --------------------------------------------------------
    # REQUEST DELAY
    # --------------------------------------------------------

    try:
        request_delay = float(request_delay)

    except (
        TypeError,
        ValueError,
    ):
        request_delay = REQUEST_DELAY_SECONDS

    request_delay = max(
        0.0,
        request_delay,
    )

    # --------------------------------------------------------
    # SHARED DEDUPLICATION
    # --------------------------------------------------------

    if seen_urls is None:
        seen_urls = OrderedDict()

    if seen_identities is None:
        seen_identities = OrderedDict()

    # --------------------------------------------------------
    # SESSION
    # --------------------------------------------------------

    own_session = session is None

    active_session = (
        session
        if session is not None
        else _create_session()
    )

    internships: List[Dict[str, Any]] = []

    next_page_token: Optional[str] = None

    clean_domain = _normalize_domain(domain)

    # --------------------------------------------------------
    # GOOGLE JOBS QUERY
    # --------------------------------------------------------

    query_parts = [
        _quote_search_term(company),
        "internship",
    ]

    query = " ".join(
        part
        for part in query_parts
        if part
    )

    logger.info(
        "Starting SerpAPI search | "
        "company=%s | domain=%s | query=%s | pages=%s",
        company,
        clean_domain or "none",
        query,
        max_pages,
    )

    try:

        # ====================================================
        # GOOGLE JOBS
        # ====================================================

        for page_number in range(
            1,
            max_pages + 1,
        ):

            if (
                page_number > 1
                and request_delay > 0
            ):
                time.sleep(request_delay)

            params = {
                "engine": "google_jobs",
                "q": query,
                "location": DEFAULT_LOCATION,
                "hl": DEFAULT_LANGUAGE,
                "api_key": key,
            }

            if next_page_token:
                params["next_page_token"] = (
                    next_page_token
                )

            # ------------------------------------------------
            # CACHE
            # ------------------------------------------------

            cache_key = (
                "google_jobs|"
                f"{company.lower()}|"
                f"{clean_domain}|"
                f"{DEFAULT_LOCATION}|"
                f"{page_number}|"
                f"{next_page_token or ''}"
            )

            data = _get_cached_response(
                cache_key
            )

            # ------------------------------------------------
            # API REQUEST
            # ------------------------------------------------

            if data is None:

                data = _request_serpapi(
                    session=active_session,
                    params=params,
                    timeout=timeout,
                )

                _set_cached_response(
                    cache_key,
                    data,
                )

            jobs_results = data.get(
                "jobs_results",
                [],
            )

            if not isinstance(
                jobs_results,
                list,
            ):
                logger.warning(
                    "Invalid jobs_results format | "
                    "company=%s | page=%s",
                    company,
                    page_number,
                )

                break

            if not jobs_results:
                logger.info(
                    "No jobs found | "
                    "company=%s | page=%s",
                    company,
                    page_number,
                )

                break

            logger.info(
                "SerpAPI page received | "
                "company=%s | page=%s | jobs=%s",
                company,
                page_number,
                len(jobs_results),
            )

            for job in jobs_results:

                normalized = _normalize_job(
                    job=job,
                    requested_company=company,
                )

                if normalized is None:
                    continue

                original_url = _clean_display_url(
                    normalized["url"]
                )

                if not original_url:
                    continue

                normalized["url"] = original_url

                # --------------------------------------------
                # STEP 6
                # --------------------------------------------

                if clean_domain:

                    if not _is_career_domain_url(
                        original_url,
                        clean_domain,
                    ):
                        logger.info(
                            "STEP 6 REJECT | "
                            "non-career-domain | "
                            "company=%s | domain=%s | "
                            "title=%s | url=%s",
                            company,
                            clean_domain,
                            normalized.get("title"),
                            original_url,
                        )

                        continue

                # --------------------------------------------
                # STEP 7
                # --------------------------------------------

                if not _is_valid_internship_posting(
                    normalized.get("title", ""),
                    original_url,
                ):
                    logger.info(
                        "STEP 7 REJECT | "
                        "not valid internship requisition | "
                        "company=%s | title=%s | url=%s",
                        company,
                        normalized.get("title"),
                        original_url,
                    )

                    continue

                # --------------------------------------------
                # STEP 8
                # --------------------------------------------

                canonical_url = _normalize_url(
                    original_url
                )

                if not canonical_url:
                    continue

                normalized["url"] = canonical_url

                # --------------------------------------------
                # STEP 9A
                # --------------------------------------------

                if not _remember_url(
                    canonical_url,
                    seen_urls,
                    seen_urls_lock,
                ):
                    logger.debug(
                        "STEP 9A REJECT | "
                        "duplicate URL | "
                        "company=%s | url=%s",
                        company,
                        canonical_url,
                    )

                    continue

                # --------------------------------------------
                # STEP 9B
                # --------------------------------------------

                if not _remember_job_identity(
                    normalized,
                    seen_identities,
                    seen_identities_lock,
                ):
                    logger.info(
                        "STEP 9B REJECT | "
                        "cross-platform duplicate | "
                        "company=%s | title=%s | "
                        "location=%s",
                        company,
                        normalized.get("title"),
                        normalized.get("location"),
                    )

                    continue

                internships.append(normalized)

            # ------------------------------------------------
            # PAGINATION
            # ------------------------------------------------

            pagination = data.get(
                "serpapi_pagination",
                {},
            )

            if not isinstance(
                pagination,
                dict,
            ):
                pagination = {}

            next_page_token = (
                pagination.get(
                    "next_page_token"
                )
                or data.get(
                    "next_page_token"
                )
            )

            if not next_page_token:
                break

        # ====================================================
        # DIRECT CAREER SITE FALLBACK
        # ====================================================

        if (
            ENABLE_DIRECT_CAREER_FALLBACK
            and clean_domain
            and len(internships) == 0
        ):

            logger.info(
                "No validated career-site jobs found | "
                "company=%s | starting fallback",
                company,
            )

            fallback_results = (
                _search_direct_career_site(
                    company=company,
                    domain=clean_domain,
                    api_key=key,
                    timeout=timeout,
                    seen_urls=seen_urls,
                    seen_urls_lock=seen_urls_lock,
                    seen_identities=seen_identities,
                    seen_identities_lock=seen_identities_lock,
                    session=active_session,
                )
            )

            internships.extend(
                fallback_results
            )

    finally:

        if own_session:
            active_session.close()

    logger.info(
        "SerpAPI search completed | "
        "company=%s | results=%s",
        company,
        len(internships),
    )

    return internships


# ============================================================
# MULTI-COMPANY PARALLEL SEARCH
# ============================================================

def search_multiple_companies(
    companies: List[
        Union[
            Dict[str, Any],
            str,
        ]
    ],
    domain: Optional[str] = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_workers: int = DEFAULT_MAX_WORKERS,
    timeout: float = DEFAULT_TIMEOUT,
    api_key: Optional[str] = None,
    request_delay: float = REQUEST_DELAY_SECONDS,
) -> List[Dict[str, Any]]:

    if not companies:
        logger.warning(
            "No companies supplied."
        )

        return []

    # --------------------------------------------------------
    # WORKERS
    # --------------------------------------------------------

    try:
        max_workers = int(max_workers)

    except (
        TypeError,
        ValueError,
    ):
        max_workers = DEFAULT_MAX_WORKERS

    max_workers = max(
        1,
        min(
            max_workers,
            20,
        ),
    )

    # --------------------------------------------------------
    # SHARED FIFO DEDUPLICATION
    # --------------------------------------------------------

    shared_seen_urls = OrderedDict()

    shared_seen_identities = OrderedDict()

    seen_urls_lock = Lock()

    seen_identities_lock = Lock()

    all_internships: List[Dict[str, Any]] = []

    # --------------------------------------------------------
    # SHARED SESSION
    # --------------------------------------------------------

    shared_session = _create_session()

    logger.info(
        "Starting parallel company search | "
        "companies=%s | workers=%s",
        len(companies),
        max_workers,
    )

    submitted_companies = 0

    try:

        with ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:

            future_map = {}

            # =================================================
            # SUBMIT TASKS
            # =================================================

            for item in companies:

                item_domain = domain

                if isinstance(
                    item,
                    dict,
                ):

                    company = (
                        item.get("company")
                        or item.get("name")
                        or ""
                    ).strip()

                    if item.get("domain"):
                        item_domain = (
                            item.get("domain")
                        )

                else:

                    company = str(
                        item
                    ).strip()

                if not company:
                    logger.warning(
                        "Empty company skipped."
                    )

                    continue

                submitted_companies += 1

                future = executor.submit(
                    search_internships,
                    company=company,
                    domain=item_domain,
                    api_key=api_key,
                    max_pages=max_pages,
                    timeout=timeout,
                    seen_urls=shared_seen_urls,
                    seen_urls_lock=seen_urls_lock,
                    seen_identities=shared_seen_identities,
                    seen_identities_lock=seen_identities_lock,
                    session=shared_session,
                    request_delay=request_delay,
                )

                future_map[future] = company

            # =================================================
            # COLLECT RESULTS
            # =================================================

            for future in as_completed(
                future_map
            ):

                company = future_map[future]

                try:

                    results = future.result()

                    all_internships.extend(
                        results
                    )

                    logger.info(
                        "Company search completed | "
                        "company=%s | jobs=%s",
                        company,
                        len(results),
                    )

                except SerpAPIAuthError as error:

                    logger.error(
                        "Authentication failure | "
                        "company=%s | error=%s",
                        company,
                        error,
                    )

                except SerpAPIQuotaExceeded as error:

                    logger.error(
                        "Quota/rate-limit failure | "
                        "company=%s | error=%s",
                        company,
                        error,
                    )

                except SerpAPIError as error:

                    logger.error(
                        "SerpAPI failure | "
                        "company=%s | error=%s",
                        company,
                        error,
                    )

                except Exception as error:

                    logger.exception(
                        "Unexpected company search failure | "
                        "company=%s | error=%s",
                        company,
                        error,
                    )

    finally:

        shared_session.close()

    logger.info(
        "Parallel search completed | "
        "companies_submitted=%s | "
        "total_jobs=%s",
        submitted_companies,
        len(all_internships),
    )

    return all_internships


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    test_companies = [
        {
            "company": "Amazon",
            "domain": "amazon.jobs",
        },
        {
            "company": "Google",
            "domain": "careers.google.com",
        },
        {
            "company": "Microsoft",
            "domain": "careers.microsoft.com",
        },
    ]

    try:

        results = search_multiple_companies(
            companies=test_companies,
            max_pages=1,
            max_workers=3,
        )

        logger.info(
            "Test completed | results=%s",
            len(results),
        )

        for job in results:

            logger.info(
                "Job | company=%s | "
                "title=%s | "
                "location=%s | "
                "posted_at=%s | "
                "via=%s | "
                "url=%s",
                job.get("company"),
                job.get("title"),
                job.get("location"),
                job.get("posted_at"),
                job.get("via"),
                job.get("url"),
            )

    except SerpAPIAuthError as error:

        logger.error(
            "SerpAPI authentication error: %s",
            error,
        )

    except SerpAPIQuotaExceeded as error:

        logger.error(
            "SerpAPI quota error: %s",
            error,
        )

    except SerpAPIError as error:

        logger.error(
            "SerpAPI error: %s",
            error,
        )
