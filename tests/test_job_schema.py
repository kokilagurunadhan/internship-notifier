# ============================================================
# JOB SCHEMA TESTS
# File: tests/test_job_schema.py
# ============================================================

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.job import JobCreate, JobInDB


# ============================================================
# COMMON TEST DATA
# ============================================================

def valid_job_data():
    return {
        "company": "Amazon",
        "title": "Software Engineering Intern",
        "location": "India",
        "description": "Software engineering internship",
        "source": "SerpAPI",
        "via": "Google Jobs",
        "url": "https://amazon.jobs/job/123",
        "posted_at": "3 days ago",
        "posted_date": "3 days ago",
        "raw_data": {
            "title": "Software Engineering Intern"
        },
    }


# ============================================================
# 1. NORMAL JOB CREATION
# ============================================================

def test_job_create_success():

    job = JobCreate(
        **valid_job_data()
    )

    assert job.company == "Amazon"

    assert job.title == (
        "Software Engineering Intern"
    )

    assert job.location == "India"

    assert str(job.url) == (
        "https://amazon.jobs/job/123"
    )

    assert job.dedup_hash is not None

    assert len(
        job.dedup_hash
    ) == 64


# ============================================================
# 2. INVALID URL
# ============================================================

def test_invalid_url_rejected():

    data = valid_job_data()

    data["url"] = "not-a-valid-url"

    with pytest.raises(
        ValidationError
    ):
        JobCreate(
            **data
        )


# ============================================================
# 3. HOURS AGO
# ============================================================

def test_hours_ago():

    data = valid_job_data()

    data["posted_date"] = "5 hours ago"

    job = JobCreate(
        **data
    )

    assert isinstance(
        job.posted_date,
        datetime
    )


# ============================================================
# 4. DAYS AGO
# ============================================================

def test_days_ago():

    data = valid_job_data()

    data["posted_date"] = "3 days ago"

    job = JobCreate(
        **data
    )

    assert isinstance(
        job.posted_date,
        datetime
    )


# ============================================================
# 5. WEEKS AGO
# ============================================================

def test_weeks_ago():

    data = valid_job_data()

    data["posted_date"] = "2 weeks ago"

    job = JobCreate(
        **data
    )

    assert isinstance(
        job.posted_date,
        datetime
    )


# ============================================================
# 6. MONTHS AGO
# ============================================================

def test_months_ago():

    data = valid_job_data()

    data["posted_date"] = "1 month ago"

    job = JobCreate(
        **data
    )

    assert isinstance(
        job.posted_date,
        datetime
    )


# ============================================================
# 7. YESTERDAY
# ============================================================

def test_yesterday():

    data = valid_job_data()

    data["posted_date"] = "yesterday"

    job = JobCreate(
        **data
    )

    assert isinstance(
        job.posted_date,
        datetime
    )


# ============================================================
# 8. INVALID DATE
# ============================================================

def test_invalid_date_returns_none():

    data = valid_job_data()

    data["posted_date"] = (
        "something completely unknown"
    )

    job = JobCreate(
        **data
    )

    assert job.posted_date is None


# ============================================================
# 9. TRAILING SLASH HASH CONSISTENCY
# ============================================================

def test_trailing_slash_same_hash():

    data1 = valid_job_data()

    data1["url"] = (
        "https://amazon.jobs/job/123"
    )

    job1 = JobCreate(
        **data1
    )

    data2 = valid_job_data()

    data2["url"] = (
        "https://amazon.jobs/job/123/"
    )

    job2 = JobCreate(
        **data2
    )

    assert (
        job1.dedup_hash
        ==
        job2.dedup_hash
    )


# ============================================================
# 10. DIFFERENT URL = DIFFERENT HASH
# ============================================================

def test_different_url_different_hash():

    data1 = valid_job_data()

    data1["url"] = (
        "https://amazon.jobs/job/123"
    )

    job1 = JobCreate(
        **data1
    )

    data2 = valid_job_data()

    data2["url"] = (
        "https://amazon.jobs/job/456"
    )

    job2 = JobCreate(
        **data2
    )

    assert (
        job1.dedup_hash
        !=
        job2.dedup_hash
    )


# ============================================================
# 11. JOBCREATE HAS NO WORKFLOW STATE
# ============================================================

def test_job_create_does_not_have_workflow_fields():

    job = JobCreate(
        **valid_job_data()
    )

    assert not hasattr(
        job,
        "email_sent"
    )

    assert not hasattr(
        job,
        "relevance_score"
    )

    assert not hasattr(
        job,
        "passed_filter"
    )

    assert not hasattr(
        job,
        "status"
    )


# ============================================================
# 12. JOBINDB HAS WORKFLOW STATE
# ============================================================

def test_job_in_db_defaults():

    job = JobInDB(
        **valid_job_data()
    )

    assert job.email_sent is False

    assert job.passed_filter is False

    assert job.status == "NEW"

    assert job.relevance_score is None

    assert job.id is None


# ============================================================
# 13. HTTPURL SERIALIZATION
# ============================================================

def test_url_serialization():

    job = JobCreate(
        **valid_job_data()
    )

    dumped = job.model_dump(
        mode="json"
    )

    assert isinstance(
        dumped["url"],
        str
    )

    assert dumped["url"] == (
        "https://amazon.jobs/job/123"
    )