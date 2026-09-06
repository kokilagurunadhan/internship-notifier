
# ============================================================
# JOB URL VALIDATOR
# File: app/services/job_url_validator.py
# ============================================================

import json
import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
RULES_PATH = BASE_DIR / "job_url_rules.json"


# ============================================================
# LOAD RULES
# ============================================================

def load_rules() -> dict:
    """
    Load optional job URL rules.

    The validator does NOT depend entirely on this file.
    Built-in rules below are always available so that
    companies such as Microsoft continue working even if
    job_url_rules.json is incomplete.
    """

    if not RULES_PATH.exists():
        logger.warning(
            "job_url_rules.json not found at: %s. "
            "Using built-in URL validation rules.",
            RULES_PATH,
        )
        return {}

    try:
        with open(
            RULES_PATH,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            logger.warning(
                "job_url_rules.json does not contain a JSON object."
            )
            return {}

        return data

    except Exception as error:
        logger.exception(
            "Failed to load job_url_rules.json | error=%s",
            error,
        )
        return {}


RULES = load_rules()


# ============================================================
# TRACKING PARAMETERS
# ============================================================

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
    "source",
}


# ============================================================
# BUILT-IN MICROSOFT RULES
# ============================================================

MICROSOFT_DOMAINS = {
    "careers.microsoft.com",
    "jobs.careers.microsoft.com",
}


MICROSOFT_JOB_PATH_PATTERNS = (
    # Current Microsoft careers structure.
    r"^/v2/global/.+/(job|jobs)/",
    r"^/v2/global/.+/job/",
    r"^/v2/global/.+/jobs/",

    # Microsoft job pages can also contain a job/requisition
    # identifier later in the path.
    r"/job/",
    r"/jobs/",
    r"/jobdetail/",
    r"/jobdetails/",
    r"/requisition/",
    r"/requisitions/",
)


# ============================================================
# GENERIC JOB PATH PATTERNS
# ============================================================

GENERIC_JOB_SEGMENTS = {
    "job",
    "jobs",
    "jobdetail",
    "jobdetails",
    "requisition",
    "requisitions",
    "opening",
    "openings",
    "position",
    "positions",
    "vacancy",
    "vacancies",
    "careers/job",
    "careers/jobs",
}


GENERIC_REJECTED_SEGMENTS = {
    "about",
    "contact",
    "contactus",
    "locations",
    "location",
    "students",
    "student",
    "universities",
    "university",
    "internship",
    "internships",
    "program",
    "programs",
    "events",
    "event",
    "stories",
    "story",
    "benefits",
    "teams",
    "team",
    "culture",
    "life",
    "faq",
    "faqs",
    "search",
}


# ============================================================
# URL NORMALIZATION
# ============================================================

def normalize_url(url: str) -> str:
    """
    Normalize a URL while preserving meaningful query parameters.

    Tracking parameters are removed.
    """

    if not url or not isinstance(url, str):
        return ""

    value = url.strip()

    if not value:
        return ""

    if not value.startswith(
        ("http://", "https://")
    ):
        value = "https://" + value

    try:
        parsed = urlparse(value)

    except Exception:
        return ""

    if parsed.scheme.lower() not in (
        "http",
        "https",
    ):
        return ""

    hostname = (
        parsed.hostname
        or ""
    ).lower().strip()

    if not hostname:
        return ""

    path = parsed.path or "/"

    if len(path) > 1:
        path = path.rstrip("/")

    # Remove tracking parameters but keep real job parameters.
    query_pairs = parse_qsl(
        parsed.query,
        keep_blank_values=True,
    )

    clean_pairs = []

    for key, value in query_pairs:

        key_lower = key.lower()

        if key_lower in TRACKING_PARAMS:
            continue

        if key_lower.startswith("utm_"):
            continue

        clean_pairs.append(
            (
                key,
                value,
            )
        )

    clean_query = urlencode(
        clean_pairs,
        doseq=True,
    )

    return urlunparse(
        (
            parsed.scheme.lower(),
            hostname,
            path,
            "",
            clean_query,
            "",
        )
    )


# ============================================================
# URL COMPONENT HELPERS
# ============================================================

def get_hostname(url: str) -> str:

    try:
        return (
            urlparse(url)
            .hostname
            or ""
        ).lower().strip()

    except Exception:
        return ""


def get_path(url: str) -> str:

    try:
        return (
            urlparse(url).path
            or "/"
        )

    except Exception:
        return "/"


def get_query(url: str) -> str:

    try:
        return (
            urlparse(url).query
            or ""
        ).lower()

    except Exception:
        return ""


# ============================================================
# DOMAIN HELPERS
# ============================================================

def normalize_domain(
    domain: Optional[str],
) -> str:

    if not domain:
        return ""

    value = str(domain).strip().lower()

    value = re.sub(
        r"^https?://",
        "",
        value,
    )

    value = value.split("/")[0]
    value = value.split(":")[0]

    return value.strip()


def domain_matches(
    hostname: str,
    domain: str,
) -> bool:

    hostname = (
        hostname or ""
    ).lower().strip()

    domain = normalize_domain(domain)

    if not hostname or not domain:
        return False

    return (
        hostname == domain
        or hostname.endswith(
            "." + domain
        )
    )


# ============================================================
# COMPANY NORMALIZATION
# ============================================================

def normalize_company_name(
    company: Optional[str],
) -> str:

    if not company:
        return ""

    value = str(company).lower().strip()

    value = re.sub(
        r"[^a-z0-9]+",
        "",
        value,
    )

    return value


# ============================================================
# REJECTED GENERIC PAGES
# ============================================================

def _path_segments(path: str) -> list[str]:

    return [
        segment.lower().strip()
        for segment in path.split("/")
        if segment.strip()
    ]


def contains_rejected_segment(
    path: str,
) -> bool:

    segments = _path_segments(path)

    rejected = set(
        RULES.get(
            "generic",
            {},
        ).get(
            "rejected_segments",
            [],
        )
    )

    rejected = {
        str(value).lower().strip()
        for value in rejected
    }

    rejected.update(
        GENERIC_REJECTED_SEGMENTS
    )

    return any(
        segment in rejected
        for segment in segments
    )


def is_obvious_generic_page(
    path: str,
) -> bool:

    clean_path = (
        path or "/"
    ).rstrip("/").lower()

    if clean_path in {
        "",
        "/",
        "/careers",
        "/career",
        "/jobs",
        "/job",
        "/students",
        "/student",
        "/internship",
        "/internships",
        "/university",
        "/universities",
        "/programs",
        "/events",
        "/locations",
        "/stories",
        "/about",
        "/about-us",
    }:
        return True

    # Generic Microsoft student/internship landing pages.
    microsoft_generic_patterns = (
        r"^/v2/global/.*/students?$",
        r"^/v2/global/.*/university",
        r"^/v2/global/.*/internships?$",
        r"^/v2/global/.*/programs?$",
        r"^/v2/global/.*/events?$",
        r"^/v2/global/.*/locations?$",
    )

    for pattern in microsoft_generic_patterns:

        if re.search(
            pattern,
            clean_path,
            re.IGNORECASE,
        ):
            return True

    return False


# ============================================================
# PATTERN MATCHING
# ============================================================

def matches_any_pattern(
    path: str,
    patterns: list[str],
) -> bool:

    for pattern in patterns:

        try:

            if re.search(
                pattern,
                path,
                re.IGNORECASE,
            ):
                return True

        except re.error as error:

            logger.warning(
                "Invalid job URL regex | "
                "pattern=%s | error=%s",
                pattern,
                error,
            )

    return False


# ============================================================
# MICROSOFT VALIDATION
# ============================================================

def validate_microsoft_url(
    url: str,
) -> bool:

    hostname = get_hostname(url)
    path = get_path(url)

    if not any(
        domain_matches(
            hostname,
            domain,
        )
        for domain in MICROSOFT_DOMAINS
    ):
        return False

    if is_obvious_generic_page(path):
        return False

    # Current Microsoft careers URL structure.
    if matches_any_pattern(
        path,
        list(MICROSOFT_JOB_PATH_PATTERNS),
    ):
        return True

    # Microsoft sometimes exposes job IDs through query
    # parameters.
    query = get_query(url)

    microsoft_query_patterns = (
        "jobid=",
        "job_id=",
        "positionid=",
        "requisitionid=",
        "requisition=",
        "reqid=",
    )

    if any(
        pattern in query
        for pattern in microsoft_query_patterns
    ):
        return True

    return False


# ============================================================
# COMPANY RULE VALIDATION
# ============================================================

def validate_company_rule(
    url: str,
    company_config: dict,
) -> bool:

    hostname = get_hostname(url)
    path = get_path(url)

    domains = company_config.get(
        "domains",
        [],
    )

    if not any(
        domain_matches(
            hostname,
            domain,
        )
        for domain in domains
    ):
        return False

    patterns = company_config.get(
        "job_url_patterns",
        [],
    )

    if patterns and matches_any_pattern(
        path,
        patterns,
    ):
        return True

    return False


# ============================================================
# ATS RULE VALIDATION
# ============================================================

def validate_ats_rule(
    url: str,
    ats_config: dict,
) -> bool:

    hostname = get_hostname(url)
    path = get_path(url)

    domains = ats_config.get(
        "domains",
        [],
    )

    if not any(
        domain_matches(
            hostname,
            domain,
        )
        for domain in domains
    ):
        return False

    patterns = ats_config.get(
        "job_url_patterns",
        [],
    )

    if patterns and matches_any_pattern(
        path,
        patterns,
    ):
        return True

    return False


# ============================================================
# MODERN GENERIC PATTERN
# ============================================================

def validate_modern_pattern(
    url: str,
) -> bool:

    path = get_path(url)

    modern_config = RULES.get(
        "modern_pattern",
        {},
    )

    pattern = modern_config.get(
        "path_regex"
    )

    if not pattern:
        return False

    try:

        return bool(
            re.search(
                pattern,
                path,
                re.IGNORECASE,
            )
        )

    except re.error as error:

        logger.warning(
            "Invalid modern pattern | error=%s",
            error,
        )

        return False


# ============================================================
# GENERIC JOB VALIDATION
# ============================================================

def validate_generic_job_url(
    url: str,
) -> bool:

    path = get_path(url)

    if not path or path == "/":
        return False

    if is_obvious_generic_page(path):
        return False

    generic = RULES.get(
        "generic",
        {},
    )

    indicators = [
        str(indicator).lower()
        for indicator in generic.get(
            "job_path_indicators",
            [],
        )
    ]

    indicators.extend(
        GENERIC_JOB_SEGMENTS
    )

    lower_path = path.lower()

    # Explicit job-path indicators.
    has_job_indicator = any(
        (
            f"/{indicator}/" in lower_path
            or lower_path.endswith(
                f"/{indicator}"
            )
            or lower_path.startswith(
                f"/{indicator}/"
            )
        )
        for indicator in indicators
    )

    if not has_job_indicator:
        return False

    if contains_rejected_segment(path):
        return False

    if validate_modern_pattern(url):
        return True

    # Numeric job ID.
    numeric_min = int(
        generic.get(
            "minimum_numeric_id_digits",
            3,
        )
    )

    numeric_pattern = (
        rf"/\d{{{numeric_min},}}(?:/|$)"
    )

    if re.search(
        numeric_pattern,
        path,
        re.IGNORECASE,
    ):
        return True

    # Alphanumeric job ID.
    alpha_min = int(
        generic.get(
            "minimum_alphanumeric_id_length",
            5,
        )
    )

    alpha_numeric_pattern = (
        rf"/[a-zA-Z0-9]{{{alpha_min},}}(?:/|$)"
    )

    if re.search(
        alpha_numeric_pattern,
        path,
        re.IGNORECASE,
    ):
        return True

    return False


# ============================================================
# QUERY-BASED JOB VALIDATION
# ============================================================

def validate_query_job_url(
    url: str,
) -> bool:

    query = get_query(url)

    if not query:
        return False

    query_job_patterns = (
        "jobid=",
        "job_id=",
        "reqid=",
        "requisition=",
        "requisitionid=",
        "positionid=",
        "position_id=",
        "job=",
        "jobkey=",
        "job_key=",
    )

    return any(
        pattern in query
        for pattern in query_job_patterns
    )


# ============================================================
# MAIN VALIDATOR
# ============================================================

def is_valid_job_url(
    url: str,
    company: Optional[str] = None,
    domain: Optional[str] = None,
) -> bool:
    """
    Validate whether a URL is an actual job/internship posting.

    IMPORTANT:
    This function intentionally accepts BOTH:

        is_valid_job_url(url, domain=...)
        is_valid_job_url(url, company=..., domain=...)

    because the internship search service uses both forms.

    Domain restriction is always respected when supplied.
    """

    if not url or not isinstance(
        url,
        str,
    ):
        return False

    normalized = normalize_url(url)

    if not normalized:
        return False

    hostname = get_hostname(
        normalized
    )

    path = get_path(
        normalized
    )

    if not hostname:
        return False

    # --------------------------------------------------------
    # DOMAIN RESTRICTION
    # --------------------------------------------------------

    expected_domain = normalize_domain(
        domain
    )

    if expected_domain:

        if not domain_matches(
            hostname,
            expected_domain,
        ):
            logger.debug(
                "Job URL rejected: wrong domain | "
                "expected=%s | hostname=%s | url=%s",
                expected_domain,
                hostname,
                normalized,
            )
            return False

    # --------------------------------------------------------
    # ALWAYS REJECT OBVIOUS GENERIC PAGES
    # --------------------------------------------------------

    if is_obvious_generic_page(
        path
    ):
        return False

    # --------------------------------------------------------
    # MICROSOFT
    # --------------------------------------------------------

    if (
        domain_matches(
            hostname,
            "careers.microsoft.com",
        )
        or domain_matches(
            hostname,
            "jobs.careers.microsoft.com",
        )
    ):

        result = validate_microsoft_url(
            normalized
        )

        if result:
            return True

        # If Microsoft uses a query-based job URL.
        if validate_query_job_url(
            normalized
        ):
            return True

        return False

    # --------------------------------------------------------
    # COMPANY-SPECIFIC RULE
    # --------------------------------------------------------

    if company:

        company_config = (
            RULES.get(
                "companies",
                {},
            ).get(
                company
            )
        )

        if company_config:

            if validate_company_rule(
                normalized,
                company_config,
            ):
                return True

    # --------------------------------------------------------
    # ATS RULES
    # --------------------------------------------------------

    for (
        ats_name,
        ats_config,
    ) in RULES.get(
        "ats",
        {},
    ).items():

        if validate_ats_rule(
            normalized,
            ats_config,
        ):

            return True

    # --------------------------------------------------------
    # QUERY-BASED JOB URL
    # --------------------------------------------------------

    if validate_query_job_url(
        normalized
    ):
        return True

    # --------------------------------------------------------
    # GENERIC JOB URL
    # --------------------------------------------------------

    if validate_generic_job_url(
        normalized
    ):
        return True

    return False


# ============================================================
# DETAILED VALIDATION
# ============================================================

def validate_job_url(
    url: str,
    company: Optional[str] = None,
    domain: Optional[str] = None,
) -> dict:
    """
    Return detailed validation information.

    This is useful for debugging search failures.
    """

    normalized = normalize_url(
        url
    )

    if not normalized:

        return {
            "valid": False,
            "reason": "invalid_url",
            "url": url,
        }

    hostname = get_hostname(
        normalized
    )

    if not hostname:

        return {
            "valid": False,
            "reason": "invalid_hostname",
            "url": normalized,
        }

    expected_domain = normalize_domain(
        domain
    )

    if expected_domain:

        if not domain_matches(
            hostname,
            expected_domain,
        ):

            return {
                "valid": False,
                "reason": "wrong_domain",
                "url": normalized,
                "hostname": hostname,
                "expected_domain": expected_domain,
            }

    if is_obvious_generic_page(
        get_path(normalized)
    ):

        return {
            "valid": False,
            "reason": "generic_career_page",
            "url": normalized,
        }

    # Microsoft.
    if (
        domain_matches(
            hostname,
            "careers.microsoft.com",
        )
        or domain_matches(
            hostname,
            "jobs.careers.microsoft.com",
        )
    ):

        if validate_microsoft_url(
            normalized
        ):

            return {
                "valid": True,
                "reason": "microsoft_rule",
                "url": normalized,
            }

        if validate_query_job_url(
            normalized
        ):

            return {
                "valid": True,
                "reason": "microsoft_query_rule",
                "url": normalized,
            }

    # Company-specific rules.
    if company:

        company_config = (
            RULES.get(
                "companies",
                {},
            ).get(
                company
            )
        )

        if company_config:

            if validate_company_rule(
                normalized,
                company_config,
            ):

                return {
                    "valid": True,
                    "reason": "company_rule",
                    "url": normalized,
                }

    # ATS.
    for (
        ats_name,
        ats_config,
    ) in RULES.get(
        "ats",
        {},
    ).items():

        if validate_ats_rule(
            normalized,
            ats_config,
        ):

            return {
                "valid": True,
                "reason": (
                    f"ats_{ats_name.lower()}"
                ),
                "url": normalized,
            }

    # Query job.
    if validate_query_job_url(
        normalized
    ):

        return {
            "valid": True,
            "reason": "query_job_rule",
            "url": normalized,
        }

    # Generic.
    if validate_generic_job_url(
        normalized
    ):

        return {
            "valid": True,
            "reason": "generic_rule",
            "url": normalized,
        }

    return {
        "valid": False,
        "reason": "no_job_pattern_matched",
        "url": normalized,
    }


# ============================================================
# COMPATIBILITY ALIASES
# ============================================================

def is_job_url(
    url: str,
    company: Optional[str] = None,
    domain: Optional[str] = None,
) -> bool:

    return is_valid_job_url(
        url,
        company=company,
        domain=domain,
    )


def validate_url(
    url: str,
    company: Optional[str] = None,
    domain: Optional[str] = None,
) -> bool:

    return is_valid_job_url(
        url,
        company=company,
        domain=domain,
    )
