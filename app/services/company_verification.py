# ============================================================
# COMPANY VERIFICATION
# ============================================================
import logging

logger = logging.getLogger(__name__)
import re
from typing import Optional, Dict
from urllib.parse import urlparse


# ============================================================
# CORPORATE SUFFIXES
# ============================================================

CORPORATE_SUFFIXES = {
    "llc",
    "ltd",
    "limited",
    "inc",
    "incorporated",
    "pvt",
    "private",
    "corporation",
    "corp",
    "company",
    "co",
    "plc",
    "llp",
    "gmbh",
    "ag",
    "sa",
    "india",
    "operations",
    "solutions",
    "technologies",
    "technology",
    "services",
    "software",
}


# ============================================================
# COMPANY ALIASES
# ============================================================

COMPANY_ALIASES: Dict[str, str] = {

    "tcs": "tata consultancy services",
    "tata consultancy services limited":
        "tata consultancy services",
    "tata consultancy services ltd":
        "tata consultancy services",

    "infosys limited":
        "infosys",
    "infosys ltd":
        "infosys",

    "ibm corporation":
        "ibm",
    "international business machines":
        "ibm",

    "google llc":
        "google",

    "microsoft corporation":
        "microsoft",

    "amazon web services":
        "amazon",
    "amazon.com":
        "amazon",

    "wipro limited":
        "wipro",
    "wipro ltd":
        "wipro",

    "hcl technologies":
        "hcl",
    "hcl technologies limited":
        "hcl",

    "cognizant technology solutions":
        "cognizant",
    "cognizant technology solutions corporation":
        "cognizant",

    "cts":
        "cognizant",

    "meta platforms":
        "meta",
    "facebook":
        "meta",

    "accenture plc":
        "accenture",

    "capgemini technology services":
        "capgemini",
}


# ============================================================
# TRUSTED JOB PORTALS
# ============================================================

JOB_PORTALS = {
    "linkedin.com",
    "indeed.com",
    "naukri.com",
    "internshala.com",
    "glassdoor.com",
    "bebee.com",
    "fresherjobinfo.in",
    "foundit.in",
    "ziprecruiter.com",
    "jooble.org",
    "wellfound.com",
    "lever.co",
    "greenhouse.io",
    "myworkdayjobs.com",
    "workday.com",
}


# ============================================================
# REGEX PATTERNS
# ============================================================

TOKEN_CLEAN_PATTERN = re.compile(
    r"[^a-z0-9\s]+"
)

MULTI_SPACE_PATTERN = re.compile(
    r"\s+"
)

SUFFIX_NOISE_PATTERN = re.compile(
    r"\b(?:"
    r"llc|ltd|limited|inc|incorporated|"
    r"pvt|private|corporation|corp|company|"
    r"co|plc|llp|gmbh|ag|sa|india|"
    r"operations|solutions"
    r")\b",
    re.IGNORECASE
)

SUBDOMAIN_STRIP_PATTERN = re.compile(
    r"^(?:www\.)",
    re.IGNORECASE
)


# ============================================================
# NORMALIZE
# ============================================================

def normalize_company(company: Optional[str]) -> str:

    if not company:
        return ""

    company = str(company).lower().strip()

    company = TOKEN_CLEAN_PATTERN.sub(
        " ",
        company
    )

    company = MULTI_SPACE_PATTERN.sub(
        " ",
        company
    )

    return company.strip()


# ============================================================
# REMOVE CORPORATE SUFFIX NOISE
# ============================================================

def remove_corporate_suffixes(
    company: Optional[str]
) -> str:

    normalized = normalize_company(
        company
    )

    if not normalized:
        return ""

    cleaned = SUFFIX_NOISE_PATTERN.sub(
        " ",
        normalized
    )

    cleaned = MULTI_SPACE_PATTERN.sub(
        " ",
        cleaned
    )

    return cleaned.strip()


# ============================================================
# RESOLVE ALIAS
# ============================================================

def resolve_company_alias(
    company: Optional[str]
) -> str:

    normalized = normalize_company(
        company
    )

    if not normalized:
        return ""

    # Direct alias
    if normalized in COMPANY_ALIASES:

        return normalize_company(
            COMPANY_ALIASES[normalized]
        )

    # Suffix-cleaned alias
    cleaned = remove_corporate_suffixes(
        normalized
    )

    if cleaned in COMPANY_ALIASES:

        return normalize_company(
            COMPANY_ALIASES[cleaned]
        )

    return cleaned


# ============================================================
# TOKEN SET
# ============================================================

def company_tokens(
    company: Optional[str]
):

    cleaned = remove_corporate_suffixes(
        company
    )

    if not cleaned:
        return set()

    return set(
        cleaned.split()
    )


# ============================================================
# SHORT COMPANY / ACRONYM DETECTION
# ============================================================

def is_short_company_token(
    company: Optional[str]
) -> bool:

    cleaned = resolve_company_alias(
        company
    )

    # Examples:
    #
    # TCS  -> short
    # IBM  -> short
    # HCL  -> short
    # CTS  -> short
    #
    # Infosys -> not short

    return (
        len(cleaned.replace(" ", "")) <= 4
    )


# ============================================================
# JARO-WINKLER
# ============================================================

def _calculate_jaro_winkler(
    s1: str,
    s2: str,
    prefix_weight: float = 0.1
) -> float:

    if s1 == s2:
        return 1.0

    len1 = len(s1)
    len2 = len(s2)

    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = (
        max(len1, len2) // 2
    ) - 1

    if match_distance < 0:
        match_distance = 0

    s1_matches = [
        False
    ] * len1

    s2_matches = [
        False
    ] * len2

    matches = 0

    for i in range(len1):

        start = max(
            0,
            i - match_distance
        )

        end = min(
            i + match_distance + 1,
            len2
        )

        for j in range(start, end):

            if s2_matches[j]:
                continue

            if s1[i] != s2[j]:
                continue

            s1_matches[i] = True
            s2_matches[j] = True

            matches += 1

            break

    if matches == 0:
        return 0.0

    matched_s1 = [
        s1[i]
        for i in range(len1)
        if s1_matches[i]
    ]

    matched_s2 = [
        s2[j]
        for j in range(len2)
        if s2_matches[j]
    ]

    transpositions = sum(
        a != b
        for a, b in zip(
            matched_s1,
            matched_s2
        )
    ) / 2.0

    jaro = (
        (matches / len1)
        +
        (matches / len2)
        +
        (
            (matches - transpositions)
            / matches
        )
    ) / 3.0

    prefix_len = 0

    for i in range(
        min(
            4,
            min(len1, len2)
        )
    ):

        if s1[i] == s2[i]:

            prefix_len += 1

        else:

            break

    return (
        jaro
        +
        (
            prefix_len
            * prefix_weight
            * (1.0 - jaro)
        )
    )


# ============================================================
# FUZZY MATCH
# ============================================================

def fuzzy_company_match(
    actual_company: str,
    target_company: str
) -> bool:

    actual = resolve_company_alias(
        actual_company
    )

    target = resolve_company_alias(
        target_company
    )

    if not actual or not target:
        return False

    # --------------------------------------------------------
    # IMPORTANT SAFETY RULE
    #
    # Never fuzzy-match short company identifiers.
    #
    # TCS -> Tata Motors
    # IBM -> IBN
    # HCL -> HCL Technologies
    #
    # Short names must use exact/alias/token logic.
    # --------------------------------------------------------

    if is_short_company_token(
        target_company
    ):

        return False

    if is_short_company_token(
        actual_company
    ):

        return False

    # --------------------------------------------------------
    # Require reasonably long strings
    # --------------------------------------------------------

    target_compact = target.replace(
        " ",
        ""
    )

    actual_compact = actual.replace(
        " ",
        ""
    )

    if (
        len(target_compact) < 5
        or len(actual_compact) < 5
    ):

        return False

    # --------------------------------------------------------
    # Jaro-Winkler
    # --------------------------------------------------------

    confidence = _calculate_jaro_winkler(
        actual_compact,
        target_compact
    )

    # --------------------------------------------------------
    # Strong threshold
    # --------------------------------------------------------

    if confidence >= 0.86:

        logger.info(
    "Fuzzy company match succeeded",
    extra={
        "confidence": round(float(confidence), 2),
    },
)

        return True

    return False


# ============================================================
# COMPANY NAME MATCH
# ============================================================

def company_name_matches(
    job_company: str,
    requested_company: str
) -> bool:

    actual_raw = normalize_company(
        job_company
    )

    target_raw = normalize_company(
        requested_company
    )

    if not actual_raw or not target_raw:
        return False

    # --------------------------------------------------------
    # 1. EXACT MATCH
    # --------------------------------------------------------

    if actual_raw == target_raw:
        return True

    # --------------------------------------------------------
    # 2. RESOLVE ALIASES
    # --------------------------------------------------------

    actual = resolve_company_alias(
        actual_raw
    )

    target = resolve_company_alias(
        target_raw
    )

    if actual == target:
        return True

    # --------------------------------------------------------
    # 3. TOKEN MATCH
    #
    # Example:
    #
    # Razorpay
    # Razorpay India
    #
    # Razorpay Software Pvt Ltd
    # Razorpay India
    # --------------------------------------------------------

    actual_tokens = company_tokens(
        actual_raw
    )

    target_tokens = company_tokens(
        target_raw
    )

    if actual_tokens and target_tokens:

        # Full token set containment
        if (
            target_tokens.issubset(
                actual_tokens
            )
            or
            actual_tokens.issubset(
                target_tokens
            )
        ):

            return True

    # --------------------------------------------------------
    # 4. SAFE SUBSTRING MATCH
    #
    # Only allow this when the target is not
    # a dangerous short acronym.
    # --------------------------------------------------------

    target_compact = target.replace(
        " ",
        ""
    )

    actual_compact = actual.replace(
        " ",
        ""
    )

    if len(target_compact) >= 5:

        if (
            target_compact in actual_compact
            or
            actual_compact in target_compact
        ):

            return True

    # --------------------------------------------------------
    # 5. FUZZY MATCH
    #
    # ONLY for sufficiently long names.
    # --------------------------------------------------------

    if fuzzy_company_match(
        actual_raw,
        target_raw
    ):

        return True

    return False


# ============================================================
# DYNAMIC DOMAIN MATCH
# ============================================================

def verify_application_url_optimized(
    application_url: Optional[str],
    target_company: str
) -> bool:

    if not application_url:
        return False

    try:

        parsed = urlparse(
            application_url
        )

        domain = (
            parsed.netloc
            .lower()
            .strip()
        )

        domain = SUBDOMAIN_STRIP_PATTERN.sub(
            "",
            domain
        )

        if not domain:
            return False

        # ----------------------------------------------------
        # Trusted job portals
        # ----------------------------------------------------

        if domain in JOB_PORTALS:

            return True

        # ----------------------------------------------------
        # Remove corporate noise from target
        # ----------------------------------------------------

        target = resolve_company_alias(
            target_company
        )

        target_compact = (
            target
            .replace(" ", "")
            .lower()
        )

        # ----------------------------------------------------
        # Domain token check
        #
        # Razorpay -> razorpay.com
        # Infosys  -> infosys.com
        # ----------------------------------------------------

        domain_without_tld = domain.split(
            "."
        )[0]

        domain_without_tld = normalize_company(
            domain_without_tld
        ).replace(
            " ",
            ""
        )

        if (
            target_compact
            and target_compact in domain_without_tld
        ):

            return True

        # ----------------------------------------------------
        # Also check individual company tokens
        # ----------------------------------------------------

        tokens = company_tokens(
            target_company
        )

        for token in tokens:

            if len(token) < 4:
                continue

            if token in domain:

                return True

    except Exception:

        return False

    return False


# ============================================================
# FULL COMPANY VERIFICATION
# ============================================================

def verify_company(
    job,
    requested_company
) -> bool:

    # --------------------------------------------------------
    # COMPANY FROM SERPAPI
    # --------------------------------------------------------

    job_company = (
        job.get("company_name")
        or job.get("company")
        or ""
    ).strip()

    if not job_company:

        logger.warning(
    "Company verification skipped: job company name is missing",
)
        return False

    # --------------------------------------------------------
    # NAME VERIFICATION
    # --------------------------------------------------------

    name_match = company_name_matches(
        job_company,
        requested_company
    )

    if name_match:

        logger.info(
    "Company verification succeeded by name match",
)

        return True

    # --------------------------------------------------------
    # URL VERIFICATION
    # --------------------------------------------------------

    apply_options = job.get(
        "apply_options",
        []
    ) or []

    application_url = ""

    if apply_options:

        first_option = apply_options[0]

        if isinstance(
            first_option,
            dict
        ):

            application_url = (
                first_option.get("link")
                or ""
            ).strip()

    if not application_url:

        application_url = (
            job.get("link")
            or job.get("url")
            or ""
        ).strip()

    # --------------------------------------------------------
    # DYNAMIC DOMAIN FALLBACK
    # --------------------------------------------------------

    if verify_application_url_optimized(
        application_url,
        requested_company
    ):

        logger.info(
    "Company verification succeeded by domain match",
)
        return True

    # --------------------------------------------------------
    # FINAL FAILURE
    # --------------------------------------------------------

    logger.info(
    "Company verification failed",
)

    return False


# ============================================================
# PIPELINE COMPATIBILITY FUNCTION
# ============================================================

def company_matches(
    actual_company,
    requested_company
):

    return company_name_matches(
        actual_company,
        requested_company
    )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 70)
    print("🧪 COMPANY VERIFICATION TEST")
    print("=" * 70)

    tests = [

        ("infosis", "Infosys", True),

        ("infosis", "Infosys Limited", True),

        ("Infosys", "Infosys Limited", True),

        ("Razorpay", "Razorpay India", True),

        (
            "Razorpay Software Pvt Ltd",
            "Razorpay India",
            True
        ),

        ("Infosys", "Microsoft", False),

        ("Razorpay", "Infosys", False),

        ("TCS", "Tata Consultancy Services", True),

        ("IBM", "International Business Machines", True),

        ("HCL", "HCL Technologies Limited", True),

        ("CTS", "Cognizant Technology Solutions", True),

        ("IBM", "Microsoft", False),

        # CRITICAL FALSE POSITIVE TEST
        ("TCS", "Tata Motors", False),

        ("amazn", "Amazon", True),

        ("googl", "Google", True),
    ]

    passed = 0
    failed = 0

    for requested, actual, expected in tests:

        result = company_name_matches(
            actual,
            requested
        )

        print()
        print(
            f"👤 Requested: {requested}"
        )

        print(
            f"🏢 Actual:    {actual}"
        )

        print(
            f"🎯 Expected:  {expected}"
        )

        print(
            f"📌 Result:    {result}"
        )

        if result == expected:

            print("✅ PASS")
            passed += 1

        else:

            print("❌ FAIL")
            failed += 1

    print()
    print("=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)

    print(
        f"✅ Passed: {passed}"
    )

    print(
        f"❌ Failed: {failed}"
    )

    print(
        f"🧪 Total:  {len(tests)}"
    )

    print("=" * 70)