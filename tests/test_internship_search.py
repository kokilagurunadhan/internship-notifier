from multiprocessing import Lock
from unittest.mock import Mock, patch

import pytest
import requests


@pytest.fixture(autouse=True)
def clear_search_cache():
    import app.services.internship_search as internship_search

    internship_search._SEARCH_CACHE.clear()
    yield
    internship_search._SEARCH_CACHE.clear()


from app.services.internship_search import (
    SerpAPIError,
    SerpAPIAuthError,
    SerpAPIQuotaExceeded,
    _normalize_domain,
    _normalize_url,
    _clean_display_url,
    _is_career_domain_url,
    _is_valid_internship_title,
    _looks_like_job_posting_url,
    _contains_outdated_year,
    _extract_posted_at,
    _extract_organic_location,
    _remember_url,
    _extract_best_url,
    _normalize_job,
    _normalize_organic_result,
    _get_api_key,
    _calculate_backoff,
    _get_retry_after,
    _create_session,
    _request_serpapi,
    _search_direct_career_site,
    search_internships,
    search_multiple_companies,
)


# ============================================================
# 1. DOMAIN NORMALIZATION
# ============================================================


def test_normalize_domain():
    assert _normalize_domain(
        "https://careers.google.com/jobs"
    ) == "careers.google.com"

    assert _normalize_domain(
        "HTTP://Amazon.Jobs/"
    ) == "amazon.jobs"

    assert _normalize_domain(
        " careers.microsoft.com "
    ) == "careers.microsoft.com"

    assert _normalize_domain("") == ""


def test_normalize_domain_case_insensitive():
    assert _normalize_domain(
        "HTTPS://CAREERS.GOOGLE.COM/"
    ) == "careers.google.com"


def test_normalize_domain_with_path():
    assert _normalize_domain(
        "https://careers.microsoft.com/global/en/job/123"
    ) == "careers.microsoft.com"


# ============================================================
# 2. URL NORMALIZATION
# ============================================================


def test_normalize_url_removes_tracking_parameters():
    url = (
        "https://example.com/job/123"
        "?utm_source=google"
        "&utm_campaign=test"
        "&id=123"
    )

    assert _normalize_url(url) == (
        "https://example.com/job/123?id=123"
    )


def test_normalize_url_removes_utm_medium():
    url = (
        "https://example.com/job/123"
        "?utm_medium=social"
        "&id=123"
    )

    assert _normalize_url(url) == (
        "https://example.com/job/123?id=123"
    )


def test_normalize_url_removes_trailing_slash():
    assert _normalize_url(
        "https://example.com/job/123/"
    ) == "https://example.com/job/123"


def test_normalize_url_removes_fragment():
    assert _normalize_url(
        "https://example.com/job/123#apply"
    ) == "https://example.com/job/123"


def test_normalize_url_lowercases_scheme_and_host():
    assert _normalize_url(
        "HTTPS://EXAMPLE.COM/job/123"
    ) == "https://example.com/job/123"


def test_normalize_url_removes_default_https_port():
    assert _normalize_url(
        "https://example.com:443/job/123"
    ) == "https://example.com/job/123"


def test_normalize_url_removes_default_http_port():
    assert _normalize_url(
        "http://example.com:80/job/123"
    ) == "http://example.com/job/123"


def test_normalize_url_preserves_non_default_port():
    assert _normalize_url(
        "https://example.com:8443/job/123"
    ) == "https://example.com:8443/job/123"


def test_normalize_url_invalid_url():
    assert _normalize_url("") == ""
    assert _normalize_url("not-a-url") == ""


def test_normalize_url_none():
    assert _normalize_url(None) == ""


# ============================================================
# 3. URL DISPLAY CLEANUP
# ============================================================


def test_clean_display_url_decodes_url():
    url = (
        "https://example.com/job"
        "?x=%5Cu003d123"
    )

    result = _clean_display_url(url)

    assert "\\u003d" not in result
    assert "%5Cu003d" not in result


def test_clean_display_url_preserves_normal_url():
    url = "https://example.com/job/123"

    assert _clean_display_url(url) == url


def test_clean_display_url_empty():
    assert _clean_display_url("") == ""


# ============================================================
# 4. CAREER DOMAIN VALIDATION
# ============================================================


def test_career_domain_accepts_exact_domain():
    assert _is_career_domain_url(
        "https://careers.google.com/jobs/results/123",
        "careers.google.com",
    )


def test_career_domain_accepts_subdomain():
    assert _is_career_domain_url(
        "https://jobs.careers.microsoft.com/job/123",
        "careers.microsoft.com",
    )


def test_career_domain_accepts_case_difference():
    assert _is_career_domain_url(
        "https://CAREERS.GOOGLE.COM/jobs/123",
        "careers.google.com",
    )


def test_career_domain_rejects_other_domain():
    assert not _is_career_domain_url(
        "https://linkedin.com/jobs/view/123",
        "careers.google.com",
    )


def test_career_domain_rejects_attacker_suffix():
    assert not _is_career_domain_url(
        "https://careers.microsoft.com.attacker.com/job/123",
        "careers.microsoft.com",
    )


def test_career_domain_rejects_empty_values():
    assert not _is_career_domain_url(
        "",
        "careers.google.com",
    )

    assert not _is_career_domain_url(
        "https://careers.google.com/jobs/123",
        "",
    )


def test_career_domain_rejects_none_values():
    assert not _is_career_domain_url(
        None,
        "careers.google.com",
    )

    assert not _is_career_domain_url(
        "https://careers.google.com/jobs/123",
        None,
    )


# ============================================================
# 5. INTERNSHIP TITLE DETECTION
# ============================================================


@pytest.mark.parametrize(
    "title",
    [
        "Software Engineering Intern",
        "Summer Internship",
        "Data Science Co-op",
        "Student Software Engineer",
        "Machine Learning Intern",
        "Software Engineering INTERN",
    ],
)
def test_internship_title_detected(title):
    assert _is_valid_internship_title(title) is True


@pytest.mark.parametrize(
    "title",
    [
        "Software Engineer",
        "Senior Software Engineer",
        "Engineering Manager",
        "Engineering Director",
    ],
)
def test_non_internship_title_rejected(title):
    assert _is_valid_internship_title(title) is False


@pytest.mark.parametrize(
    "title",
    [
        "",
        "Student Support Specialist",
        "Student Services Coordinator",
        "Student Account Manager",
    ],
)
def test_internship_title_rejects_non_internship_student_titles(title):
    assert _is_valid_internship_title(title) is False


@pytest.mark.parametrize(
    "title",
    [
        "Internship Eligibility",
        "Intern US base pay ranges and additional pay information",
        "Microsoft Careers: Home",
        "Career Overview",
        "Internship FAQ",
    ],
)
def test_non_job_internship_title_rejected(title):
    assert _is_valid_internship_title(title) is False


def test_internship_title_none():
    assert _is_valid_internship_title(None) is False


# ============================================================
# 6. FALLBACK JOB URL VALIDATION
# ============================================================


def test_amazon_job_url_is_valid():
    assert _looks_like_job_posting_url(
        "https://www.amazon.jobs/en/jobs/123/software-intern",
        "amazon.jobs",
    )


def test_google_job_url_is_valid():
    assert _looks_like_job_posting_url(
        "https://careers.google.com/jobs/results/123-test",
        "careers.google.com",
    )


def test_microsoft_job_url_is_valid():
    assert _looks_like_job_posting_url(
        "https://jobs.careers.microsoft.com/global/en/job/123/test",
        "careers.microsoft.com",
    )


def test_career_homepage_is_not_job():
    assert not _looks_like_job_posting_url(
        "https://careers.google.com/",
        "careers.google.com",
    )


def test_search_page_is_not_job():
    assert not _looks_like_job_posting_url(
        "https://www.amazon.jobs/en/search?base_query=intern",
        "amazon.jobs",
    )


def test_empty_job_url_is_invalid():
    assert not _looks_like_job_posting_url(
        "",
        "amazon.jobs",
    )


# ============================================================
# 7. OUTDATED YEAR FILTER
# ============================================================


def test_outdated_year_detected():
    assert _contains_outdated_year(
        "Microsoft Internship 2024"
    )


def test_current_listing_not_marked_outdated():
    assert not _contains_outdated_year(
        "Software Engineering Internship 2027"
    )


def test_outdated_year_in_description():
    assert _contains_outdated_year(
        "Apply for our 2024 internship program"
    )


def test_no_year_not_outdated():
    assert not _contains_outdated_year(
        "Software Engineering Intern"
    )


# ============================================================
# 8. POSTED DATE EXTRACTION
# ============================================================


def test_extract_posted_at():
    job = {
        "detected_extensions": {
            "posted_at": "2 days ago"
        }
    }

    assert _extract_posted_at(job) == "2 days ago"


def test_extract_posted_at_missing():
    assert _extract_posted_at({}) == ""


def test_extract_posted_at_empty_extensions():
    assert _extract_posted_at({
        "detected_extensions": {}
    }) == ""


def test_extract_posted_at_none():
    assert _extract_posted_at(None) == ""


# ============================================================
# 9. LOCATION EXTRACTION
# ============================================================


def test_extract_organic_location_from_location():
    result = {
        "location": "Hyderabad, India"
    }

    assert _extract_organic_location(result) == (
        "Hyderabad, India"
    )


def test_extract_organic_location_from_job_location():
    result = {
        "job_location": "Bangalore, India"
    }

    assert _extract_organic_location(result) == (
        "Bangalore, India"
    )


def test_extract_organic_location_from_formatted_location():
    result = {
        "formatted_location": "Chennai, India"
    }

    assert _extract_organic_location(result) == (
        "Chennai, India"
    )


def test_extract_organic_location_from_extensions():
    result = {
        "extensions": [
            "Hyderabad, India",
            "Full-time",
        ]
    }

    assert _extract_organic_location(result) == (
        "Hyderabad, India, Full-time"
    )


def test_extract_organic_location_from_rich_snippet_top():
    result = {
        "rich_snippet": {
            "top": {
                "extensions": [
                    "Remote",
                    "India",
                ]
            }
        }
    }

    assert _extract_organic_location(result) == (
        "Remote, India"
    )


def test_extract_organic_location_from_rich_snippet_bottom():
    result = {
        "rich_snippet": {
            "bottom": {
                "extensions": [
                    "Bangalore",
                ]
            }
        }
    }

    assert _extract_organic_location(result) == "Bangalore"


def test_extract_organic_location_missing():
    assert _extract_organic_location({}) == (
        "Location not specified"
    )


def test_extract_organic_location_empty_values():
    result = {
        "location": "",
        "job_location": "",
        "formatted_location": "",
    }

    assert _extract_organic_location(result) == (
        "Location not specified"
    )


# ============================================================
# 10. URL DEDUPLICATION
# ============================================================


def test_remember_url_first_time():
    seen = set()

    assert _remember_url(
        "https://example.com/job/123",
        seen,
    )

    assert len(seen) == 1


def test_remember_url_duplicate():
    seen = set()

    assert _remember_url(
        "https://example.com/job/123",
        seen,
    )

    assert not _remember_url(
        "https://example.com/job/123",
        seen,
    )


def test_remember_url_tracking_urls_are_duplicates():
    seen = set()

    assert _remember_url(
        "https://example.com/job/123?utm_source=google",
        seen,
    )

    assert not _remember_url(
        "https://example.com/job/123?utm_source=linkedin",
        seen,
    )


def test_remember_url_with_lock():
    seen = set()
    lock = Lock()

    first = _remember_url(
        "https://example.com/job/1",
        seen,
        lock,
    )

    second = _remember_url(
        "https://example.com/job/1",
        seen,
        lock,
    )

    assert first is True
    assert second is False


def test_remember_url_empty():
    seen = set()

    assert not _remember_url(
        "",
        seen,
    )


# ============================================================
# 11. BEST URL EXTRACTION
# ============================================================


def test_extract_best_url_prefers_career_link():
    job = {
        "apply_options": [
            {
                "title": "Apply on LinkedIn",
                "link": "https://linkedin.com/job/123",
            },
            {
                "title": "Apply on company careers",
                "link": "https://careers.example.com/job/123",
            },
        ]
    }

    assert _extract_best_url(job) == (
        "https://careers.example.com/job/123"
    )


def test_extract_best_url_prefers_company_career_link():
    job = {
        "apply_options": [
            {
                "title": "Apply now",
                "link": "https://external.com/apply"
            },
            {
                "title": "Amazon Careers",
                "link": "https://amazon.jobs/job/123"
            }
        ]
    }

    assert _extract_best_url(job) == (
        "https://amazon.jobs/job/123"
    )


def test_extract_best_url_falls_back_to_direct_link():
    job = {
        "link": "https://example.com/job/123"
    }

    assert _extract_best_url(job) == (
        "https://example.com/job/123"
    )


def test_extract_best_url_uses_related_link():
    job = {
        "related_links": [
            {
                "link": "https://example.com/job/123"
            }
        ]
    }

    assert _extract_best_url(job) == (
        "https://example.com/job/123"
    )


def test_extract_best_url_uses_share_link():
    job = {
        "share_link": "https://example.com/share/123"
    }

    assert _extract_best_url(job) == (
        "https://example.com/share/123"
    )


def test_extract_best_url_uses_job_id():
    job = {
        "job_id": "ABC123"
    }

    result = _extract_best_url(job)

    assert result == ""


def test_extract_best_url_missing():
    assert _extract_best_url({}) == ""


def test_extract_best_url_none():
    assert _extract_best_url(None) == ""


# ============================================================
# 12. NORMALIZE GOOGLE JOB
# ============================================================


def test_normalize_job():
    job = {
        "title": "Software Engineering Intern",
        "company_name": "Microsoft",
        "location": "Hyderabad, India",
        "description": "Software engineering internship",
        "via": "Microsoft Careers",
        "link": "https://careers.microsoft.com/job/123",
        "detected_extensions": {
            "posted_at": "1 day ago"
        },
    }

    result = _normalize_job(
        job,
        "Microsoft",
    )

    assert result is not None
    assert result["company"] == "Microsoft"
    assert result["title"] == "Software Engineering Intern"
    assert result["location"] == "Hyderabad, India"
    assert result["source"] == "SerpAPI"
    assert result["email_sent"] is False
    assert result["passed_filter"] is False
    assert result["status"] == "NEW"
    assert result["posted_at"] == "1 day ago"


def test_normalize_job_uses_requested_company():
    job = {
        "title": "Software Engineering Intern",
        "link": "https://example.com/job/123",
    }

    result = _normalize_job(
        job,
        "Amazon",
    )

    assert result is not None
    assert result["company"] == "Amazon"


def test_normalize_job_uses_default_location():
    job = {
        "title": "Software Engineering Intern",
        "link": "https://example.com/job/123",
        "company_name": "Amazon",
    }

    result = _normalize_job(
        job,
        "Amazon",
    )

    assert result is not None
    assert result["location"] == "Location not specified"


def test_normalize_job_preserves_posted_date():
    job = {
        "title": "Software Engineering Intern",
        "company_name": "Amazon",
        "link": "https://example.com/job/123",
        "detected_extensions": {
            "posted_at": "2 days ago"
        },
    }

    result = _normalize_job(
        job,
        "Amazon",
    )

    assert result is not None
    assert result["posted_at"] == "2 days ago"


def test_normalize_job_without_title():
    result = _normalize_job(
        {},
        "Microsoft",
    )

    assert result is None


def test_normalize_job_without_url():
    job = {
        "title": "Software Engineering Intern",
        "company_name": "Microsoft",
    }

    result = _normalize_job(
        job,
        "Microsoft",
    )

    assert result is None


def test_normalize_job_outdated():
    job = {
        "title": "Microsoft Internship 2024",
        "company_name": "Microsoft",
        "link": "https://careers.microsoft.com/job/123",
    }

    result = _normalize_job(
        job,
        "Microsoft",
    )

    assert result is None


def test_normalize_job_invalid_input():
    assert _normalize_job(
        None,
        "Amazon",
    ) is None


# ============================================================
# 13. NORMALIZE ORGANIC RESULT
# ============================================================


def test_normalize_organic_result():
    result = {
        "title": "Software Engineering Intern",
        "link": "https://careers.google.com/jobs/results/123",
        "snippet": "Internship opportunity",
        "displayed_link": "careers.google.com",
    }

    normalized = _normalize_organic_result(
        result,
        "Google",
    )

    assert normalized is not None
    assert normalized["company"] == "Google"
    assert normalized["title"] == "Software Engineering Intern"

    assert normalized["url"] == (
        "https://careers.google.com/jobs/results/123"
    )

    assert normalized["via"] == "Direct Career Site"


def test_normalize_organic_result_uses_snippet():
    result = {
        "title": "Software Engineering Intern",
        "link": "https://careers.example.com/job/123",
        "snippet": "Summer internship opportunity",
    }

    normalized = _normalize_organic_result(
        result,
        "Amazon",
    )

    assert normalized is not None
    assert normalized["description"] == (
        "Summer internship opportunity"
    )


def test_normalize_organic_result_default_location():
    result = {
        "title": "Software Engineering Intern",
        "link": "https://careers.example.com/job/123",
    }

    normalized = _normalize_organic_result(
        result,
        "Amazon",
    )

    assert normalized is not None

    assert normalized["location"] == (
        "Location not specified"
    )


def test_normalize_organic_result_preserves_location():
    result = {
        "title": "Software Engineering Intern",
        "link": "https://careers.example.com/job/123",
        "location": "Bangalore, India",
    }

    normalized = _normalize_organic_result(
        result,
        "Amazon",
    )

    assert normalized is not None
    assert normalized["location"] == "Bangalore, India"


def test_normalize_organic_result_missing_url():
    result = {
        "title": "Software Engineering Intern"
    }

    assert _normalize_organic_result(
        result,
        "Google",
    ) is None


def test_normalize_organic_result_invalid_input():
    assert _normalize_organic_result(
        None,
        "Amazon",
    ) is None


# ============================================================
# 14. API KEY VALIDATION
# ============================================================


def test_api_key_argument():
    assert _get_api_key("test-key") == "test-key"


def test_missing_api_key(monkeypatch):
    monkeypatch.delenv(
        "SERPAPI_API_KEY",
        raising=False,
    )

    monkeypatch.delenv(
        "SERPAPI_KEY",
        raising=False,
    )

    with pytest.raises(SerpAPIAuthError):
        _get_api_key()


# ============================================================
# 15. BACKOFF
# ============================================================


def test_backoff_is_positive():
    result = _calculate_backoff(1)

    assert result >= 1.1
    assert result <= 1.5


def test_backoff_increases():
    first = _calculate_backoff(1)
    second = _calculate_backoff(2)

    assert second > first


def test_backoff_first_attempt_is_reasonable():
    with patch(
        "app.services.internship_search.random.uniform",
        return_value=0.2,
    ):
        result = _calculate_backoff(1)

    assert result == 1.2


def test_backoff_second_attempt_is_reasonable():
    with patch(
        "app.services.internship_search.random.uniform",
        return_value=0.2,
    ):
        result = _calculate_backoff(2)

    assert result == 2.2


# ============================================================
# 16. RETRY-AFTER
# ============================================================


def test_retry_after_seconds():
    response = Mock()

    response.headers = {
        "Retry-After": "10"
    }

    assert _get_retry_after(response) == 10.0


def test_retry_after_numeric_string():
    response = Mock()

    response.headers = {
        "Retry-After": "5"
    }

    assert _get_retry_after(response) == 5.0


def test_retry_after_invalid_value():
    response = Mock()

    response.headers = {
        "Retry-After": "invalid"
    }

    assert _get_retry_after(response) is None


def test_retry_after_missing():
    response = Mock()

    response.headers = {}

    assert _get_retry_after(response) is None


# ============================================================
# 17. SESSION CREATION
# ============================================================


def test_create_session():
    session = _create_session()

    try:
        assert session is not None
        assert "User-Agent" in session.headers
        assert "Accept" in session.headers
    finally:
        session.close()


# ============================================================
# 18. SERPAPI REQUEST SUCCESS
# ============================================================


def test_request_serpapi_success():
    session = Mock()

    response = Mock()
    response.status_code = 200
    response.json.return_value = {
        "jobs_results": []
    }

    session.get.return_value = response

    result = _request_serpapi(
        session=session,
        params={"q": "Amazon internship"},
        timeout=5,
    )

    assert result == {
        "jobs_results": []
    }

    session.get.assert_called_once()


# ============================================================
# 19. SERPAPI HTTP ERRORS
# ============================================================


def test_request_serpapi_401():
    session = Mock()

    response = Mock()
    response.status_code = 401

    session.get.return_value = response

    with pytest.raises(SerpAPIAuthError):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert session.get.call_count == 1


def test_request_serpapi_403():
    session = Mock()

    response = Mock()
    response.status_code = 403

    session.get.return_value = response

    with pytest.raises(SerpAPIQuotaExceeded):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert session.get.call_count == 1


def test_request_serpapi_other_http_error():
    session = Mock()

    response = Mock()
    response.status_code = 400

    session.get.return_value = response

    with pytest.raises(SerpAPIError):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )


# ============================================================
# 20. SERPAPI JSON ERRORS
# ============================================================


def test_request_serpapi_invalid_json():
    session = Mock()

    response = Mock()
    response.status_code = 200
    response.json.side_effect = ValueError()

    session.get.return_value = response

    with pytest.raises(SerpAPIError):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )


def test_request_serpapi_invalid_json_structure():
    session = Mock()

    response = Mock()
    response.status_code = 200
    response.json.return_value = []

    session.get.return_value = response

    with pytest.raises(SerpAPIError):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )


def test_request_serpapi_api_key_error_from_json():
    session = Mock()

    response = Mock()
    response.status_code = 200

    response.json.return_value = {
        "error": "Invalid API key"
    }

    session.get.return_value = response

    with pytest.raises(SerpAPIAuthError):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )


def test_request_serpapi_quota_error_from_json():
    session = Mock()

    response = Mock()
    response.status_code = 200

    response.json.return_value = {
        "error": "Quota exceeded"
    }

    session.get.return_value = response

    with pytest.raises(SerpAPIQuotaExceeded):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )


def test_request_serpapi_generic_api_error_from_json():
    session = Mock()

    response = Mock()
    response.status_code = 200

    response.json.return_value = {
        "error": "Something went wrong"
    }

    session.get.return_value = response

    with pytest.raises(SerpAPIError):
        _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )


# ============================================================
# 21. SERPAPI NETWORK RETRY
# ============================================================


def test_request_serpapi_retries_request_exception():
    session = Mock()

    response = Mock()
    response.status_code = 200

    response.json.return_value = {
        "jobs_results": []
    }

    session.get.side_effect = [
        requests.RequestException("network error"),
        response,
    ]

    with patch(
        "app.services.internship_search.time.sleep"
    ):
        result = _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert result == {
        "jobs_results": []
    }

    assert session.get.call_count == 2


def test_request_serpapi_network_failure_exhausts_retries():
    session = Mock()

    session.get.side_effect = requests.RequestException(
        "network unavailable"
    )

    with patch(
        "app.services.internship_search.time.sleep"
    ):
        with pytest.raises(SerpAPIError):
            _request_serpapi(
                session=session,
                params={},
                timeout=5,
            )

    assert session.get.call_count >= 2


# ============================================================
# 22. SERPAPI 429 RETRY
# ============================================================


def test_request_serpapi_429_retries():
    session = Mock()

    rate_limit_response = Mock()
    rate_limit_response.status_code = 429
    rate_limit_response.headers = {}

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "jobs_results": []
    }

    session.get.side_effect = [
        rate_limit_response,
        success_response,
    ]

    with patch(
        "app.services.internship_search.time.sleep"
    ) as mock_sleep:

        result = _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert result == {
        "jobs_results": []
    }

    assert session.get.call_count == 2
    mock_sleep.assert_called_once()


def test_request_serpapi_429_honors_retry_after():
    session = Mock()

    rate_limit_response = Mock()
    rate_limit_response.status_code = 429
    rate_limit_response.headers = {
        "Retry-After": "10"
    }

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "jobs_results": []
    }

    session.get.side_effect = [
        rate_limit_response,
        success_response,
    ]

    with patch(
        "app.services.internship_search.time.sleep"
    ) as mock_sleep:

        result = _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert result == {
        "jobs_results": []
    }

    assert session.get.call_count == 2
    mock_sleep.assert_called_once_with(10.0)


def test_request_serpapi_429_exhausts_retries():
    session = Mock()

    rate_limit_response = Mock()
    rate_limit_response.status_code = 429
    rate_limit_response.headers = {}

    session.get.return_value = rate_limit_response

    with patch(
        "app.services.internship_search.time.sleep"
    ):
        with pytest.raises(SerpAPIError):
            _request_serpapi(
                session=session,
                params={},
                timeout=5,
            )

    assert session.get.call_count >= 2


# ============================================================
# 23. SERPAPI 5XX RETRY
# ============================================================


def test_request_serpapi_500_retries():
    session = Mock()

    server_error_response = Mock()
    server_error_response.status_code = 500
    server_error_response.headers = {}

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "jobs_results": []
    }

    session.get.side_effect = [
        server_error_response,
        success_response,
    ]

    with patch(
        "app.services.internship_search.time.sleep"
    ) as mock_sleep:

        result = _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert result == {
        "jobs_results": []
    }

    assert session.get.call_count == 2
    mock_sleep.assert_called_once()


def test_request_serpapi_500_honors_retry_after():
    session = Mock()

    server_error_response = Mock()
    server_error_response.status_code = 500
    server_error_response.headers = {
        "Retry-After": "7"
    }

    success_response = Mock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "jobs_results": []
    }

    session.get.side_effect = [
        server_error_response,
        success_response,
    ]

    with patch(
        "app.services.internship_search.time.sleep"
    ) as mock_sleep:

        result = _request_serpapi(
            session=session,
            params={},
            timeout=5,
        )

    assert result == {
        "jobs_results": []
    }

    assert session.get.call_count == 2
    mock_sleep.assert_called_once_with(7.0)


def test_request_serpapi_500_exhausts_retries():
    session = Mock()

    server_error_response = Mock()
    server_error_response.status_code = 500
    server_error_response.headers = {}

    session.get.return_value = server_error_response

    with patch(
        "app.services.internship_search.time.sleep"
    ):
        with pytest.raises(SerpAPIError):
            _request_serpapi(
                session=session,
                params={},
                timeout=5,
            )

    assert session.get.call_count >= 2


# ============================================================
# 24. SEARCH INTERNSHIPS
# ============================================================


def test_search_internships_empty_company():
    result = search_internships(
        company="",
        api_key="test-key",
    )

    assert result == []


def test_search_internships_stops_when_no_jobs():
    session = Mock()

    with patch(
        "app.services.internship_search._request_serpapi",
        return_value={
            "jobs_results": []
        },
    ) as mock_request:

        result = search_internships(
            company="Amazon",
            api_key="test-key",
            max_pages=3,
            session=session,
            request_delay=0,
        )

    assert result == []
    assert mock_request.call_count == 1


def test_search_internships_respects_max_pages():
    session = Mock()

    page_one = {
        "jobs_results": [
            {
                "title": "Software Engineering Intern",
                "company_name": "Amazon",
                "location": "India",
                "link": "https://amazon.jobs/job/1",
            }
        ],
        "serpapi_pagination": {
            "next_page_token": "PAGE2"
        },
    }

    page_two = {
        "jobs_results": [
            {
                "title": "Data Science Intern",
                "company_name": "Amazon",
                "location": "India",
                "link": "https://amazon.jobs/job/2",
            }
        ]
    }

    with patch(
        "app.services.internship_search._request_serpapi",
        side_effect=[
            page_one,
            page_two,
        ],
    ) as mock_request:

        result = search_internships(
            company="Amazon",
            api_key="test-key",
            max_pages=2,
            session=session,
            request_delay=0,
        )

    assert len(result) == 2
    assert mock_request.call_count == 2


def test_search_internships_caps_max_pages_at_five():
    session = Mock()

    responses = []

    for index in range(5):
        response = {
            "jobs_results": [
                {
                    "title": f"Software Engineering Intern {index}",
                    "company_name": "Amazon",
                    "location": "India",
                    "link": (
                        f"https://amazon.jobs/job/{index}"
                    ),
                }
            ],
            "serpapi_pagination": {
                "next_page_token": f"PAGE{index + 2}"
            },
        }

        responses.append(response)

    with patch(
        "app.services.internship_search._request_serpapi",
        side_effect=responses,
    ) as mock_request:

        result = search_internships(
            company="Amazon",
            api_key="test-key",
            max_pages=999,
            session=session,
            request_delay=0,
        )

    assert len(result) == 5
    assert mock_request.call_count == 5





def test_search_internships_removes_duplicate_urls():
    session = Mock()

    data = {
        "jobs_results": [
            {
                "title": "Software Engineering Intern",
                "company_name": "Amazon",
                "link": (
                    "https://amazon.jobs/job/1"
                    "?utm_source=google"
                ),
            },
            {
                "title": "Software Engineering Intern",
                "company_name": "Amazon",
                "link": (
                    "https://amazon.jobs/job/1"
                ),
            },
        ]
    }

    with patch(
        "app.services.internship_search._request_serpapi",
        return_value=data,
    ):

        result = search_internships(
            company="Amazon",
            api_key="test-key",
            max_pages=1,
            session=session,
            request_delay=0,
        )

    assert len(result) == 1


def test_search_internships_rejects_wrong_domain():
    session = Mock()

    data = {
        "jobs_results": [
            {
                "title": "Software Engineering Intern",
                "company_name": "Amazon",
                "link": (
                    "https://linkedin.com/jobs/123"
                ),
            }
        ]
    }

    with patch(
        "app.services.internship_search._request_serpapi",
        return_value=data,
    ):

        result = search_internships(
            company="Amazon",
            domain="amazon.jobs",
            api_key="test-key",
            max_pages=1,
            session=session,
            request_delay=0,
        )

    assert result == []


# ============================================================
# 25. DIRECT CAREER FALLBACK
# ============================================================


def test_direct_career_fallback_returns_valid_result():
    session = Mock()
    seen = set()

    data = {
        "organic_results": [
            {
                "title": "Software Engineering Intern",
                "link": (
                    "https://amazon.jobs/en/jobs/123"
                ),
                "snippet": "Internship opportunity",
            }
        ]
    }

    with patch(
        "app.services.internship_search._request_serpapi",
        return_value=data,
    ):

        result = _search_direct_career_site(
            company="Amazon",
            domain="amazon.jobs",
            api_key="test-key",
            timeout=5,
            seen_urls=seen,
            seen_urls_lock=None,
            session=session,
        )

    assert len(result) == 1
    assert result[0]["company"] == "Amazon"


def test_direct_career_fallback_rejects_wrong_domain():
    session = Mock()
    seen = set()

    data = {
        "organic_results": [
            {
                "title": "Software Engineering Intern",
                "link": (
                    "https://linkedin.com/jobs/123"
                ),
                "snippet": "Internship opportunity",
            }
        ]
    }

    with patch(
        "app.services.internship_search._request_serpapi",
        return_value=data,
    ):

        result = _search_direct_career_site(
            company="Amazon",
            domain="amazon.jobs",
            api_key="test-key",
            timeout=5,
            seen_urls=seen,
            seen_urls_lock=None,
            session=session,
        )

    assert result == []


def test_direct_career_fallback_handles_invalid_results():
    session = Mock()
    seen = set()

    with patch(
        "app.services.internship_search._request_serpapi",
        return_value={
            "organic_results": "invalid"
        },
    ):

        result = _search_direct_career_site(
            company="Amazon",
            domain="amazon.jobs",
            api_key="test-key",
            timeout=5,
            seen_urls=seen,
            seen_urls_lock=None,
            session=session,
        )

    assert result == []


# ============================================================
# 26. MULTI-COMPANY SEARCH
# ============================================================


def test_search_multiple_companies_empty():
    result = search_multiple_companies(
        companies=[],
        api_key="test-key",
    )

    assert result == []


def test_search_multiple_companies_skips_empty_company():
    with patch(
        "app.services.internship_search.search_internships",
        return_value=[],
    ) as mock_search:

        result = search_multiple_companies(
            companies=[
                "",
                "Amazon",
            ],
            api_key="test-key",
        )

    assert result == []
    assert mock_search.call_count == 1


def test_search_multiple_companies_accepts_strings():
    with patch(
        "app.services.internship_search.search_internships",
        return_value=[
            {
                "company": "Amazon",
                "title": "Software Engineering Intern",
            }
        ],
    ):

        result = search_multiple_companies(
            companies=["Amazon"],
            api_key="test-key",
        )

    assert len(result) == 1
    assert result[0]["company"] == "Amazon"


def test_search_multiple_companies_accepts_company_dicts():
    with patch(
        "app.services.internship_search.search_internships",
        return_value=[],
    ) as mock_search:

        search_multiple_companies(
            companies=[
                {
                    "company": "Amazon",
                    "domain": "amazon.jobs",
                }
            ],
            api_key="test-key",
        )

    mock_search.assert_called_once()

    call_kwargs = mock_search.call_args.kwargs

    assert call_kwargs["company"] == "Amazon"
    assert call_kwargs["domain"] == "amazon.jobs"


def test_search_multiple_companies_handles_serpapi_error():
    with patch(
        "app.services.internship_search.search_internships",
        side_effect=SerpAPIError("failed"),
    ):

        result = search_multiple_companies(
            companies=["Amazon"],
            api_key="test-key",
        )

    assert result == []


def test_search_multiple_companies_handles_auth_error():
    with patch(
        "app.services.internship_search.search_internships",
        side_effect=SerpAPIAuthError("invalid key"),
    ):

        result = search_multiple_companies(
            companies=["Amazon"],
            api_key="test-key",
        )

    assert result == []


def test_search_multiple_companies_handles_unexpected_error():
    with patch(
        "app.services.internship_search.search_internships",
        side_effect=RuntimeError("unexpected"),
    ):

        result = search_multiple_companies(
            companies=["Amazon"],
            api_key="test-key",
        )

    assert result == []


# ============================================================
# END
# ============================================================