# ============================================================
# JOB PYDANTIC SCHEMAS
# File: app/schemas/job.py
# ============================================================

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Dict, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_serializer,
    field_validator,
    model_validator,
)


# ============================================================
# BASE JOB SCHEMA
# ============================================================

class JobBase(BaseModel):
    """
    Common fields shared by all job schemas.
    """

    model_config = ConfigDict(
        extra="ignore"
    )

    # ========================================================
    # BASIC JOB INFORMATION
    # ========================================================

    company: str = Field(
        ...,
        min_length=1,
        description="Company offering the internship/job"
    )

    title: str = Field(
        ...,
        min_length=1,
        description="Internship/job title"
    )

    location: str = Field(
        default="Location not specified"
    )

    description: str = Field(
        default=""
    )

    # ========================================================
    # SOURCE INFORMATION
    # ========================================================

    source: str = Field(
        default="SerpAPI"
    )

    via: str = Field(
        default="Google Jobs"
    )

    # ========================================================
    # JOB URL
    # ========================================================

    url: HttpUrl

    @field_serializer("url")
    def serialize_url(
        self,
        url: HttpUrl
    ) -> str:
        """
        Converts Pydantic HttpUrl into a normal Python string
        when the model is serialized.
        """

        return str(url)

    # ========================================================
    # ORIGINAL SERPAPI POSTED DATE
    # ========================================================

    posted_at: str = Field(
        default=""
    )

    # ========================================================
    # PARSED POSTED DATE
    # ========================================================

    posted_date: Optional[datetime] = Field(
        default=None,
        description="Parsed publication date"
    )

    @field_validator(
        "posted_date",
        mode="before"
    )
    @classmethod
    def parse_posted_date(
        cls,
        value: Any
    ) -> Optional[datetime]:
        """
        Converts relative SerpAPI date strings into datetime.

        Supported examples:

            today
            just now
            just posted
            yesterday
            5 hours ago
            1 hour ago
            3 days ago
            1 day ago
            2 weeks ago
            1 week ago
            1 month ago
            ISO datetime strings

        Unknown formats safely become None.
        """

        # ----------------------------------------------------
        # NONE
        # ----------------------------------------------------

        if value is None:
            return None

        # ----------------------------------------------------
        # ALREADY DATETIME
        # ----------------------------------------------------

        if isinstance(
            value,
            datetime
        ):
            return value

        # ----------------------------------------------------
        # INVALID TYPE
        # ----------------------------------------------------

        if not isinstance(
            value,
            str
        ):
            return None

        text = value.strip().lower()

        if not text:
            return None

        now = datetime.now(
            timezone.utc
        )

        # ====================================================
        # TODAY
        # ====================================================

        if text in {
            "today",
            "just now",
            "just posted",
        }:

            return now

        # ====================================================
        # YESTERDAY
        # ====================================================

        if text == "yesterday":

            return now - timedelta(
                days=1
            )

        # ====================================================
        # HOURS AGO
        # ====================================================

        if "hour" in text:

            parts = text.split()

            if parts:

                try:

                    hours = int(
                        parts[0]
                    )

                    return now - timedelta(
                        hours=hours
                    )

                except ValueError:
                    pass

        # ====================================================
        # DAYS AGO
        # ====================================================

        if "day" in text:

            parts = text.split()

            if parts:

                try:

                    days = int(
                        parts[0]
                    )

                    return now - timedelta(
                        days=days
                    )

                except ValueError:
                    pass

        # ====================================================
        # WEEKS AGO
        # ====================================================

        if "week" in text:

            parts = text.split()

            if parts:

                try:

                    weeks = int(
                        parts[0]
                    )

                    return now - timedelta(
                        weeks=weeks
                    )

                except ValueError:
                    pass

        # ====================================================
        # MONTHS AGO
        # ====================================================

        if "month" in text:

            parts = text.split()

            if parts:

                try:

                    months = int(
                        parts[0]
                    )

                    # Approximation:
                    # 1 month = 30 days
                    return now - timedelta(
                        days=months * 30
                    )

                except ValueError:
                    pass

        # ====================================================
        # ISO DATETIME
        # ====================================================

        try:

            parsed = datetime.fromisoformat(
                text.replace(
                    "z",
                    "+00:00"
                )
            )

            return parsed

        except ValueError:
            return None


# ============================================================
# JOB CREATE
# ============================================================

class JobCreate(JobBase):
    """
    Schema used immediately after the search service
    retrieves and normalizes a job.

    Contains ingestion/search data only.

    Workflow fields such as:

        relevance_score
        passed_filter
        status
        email_sent

    belong to JobInDB.
    """

    # ========================================================
    # ORIGINAL RAW SEARCH DATA
    # ========================================================

    raw_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Original SerpAPI response"
    )

    # ========================================================
    # DEDUPLICATION HASH
    # ========================================================

    dedup_hash: Optional[str] = Field(
        default=None,
        min_length=64,
        max_length=64,
        description="SHA-256 hash used for duplicate detection"
    )

    # ========================================================
    # GENERATE DEDUP HASH
    # ========================================================

    @model_validator(
        mode="before"
    )
    @classmethod
    def generate_dedup_hash(
        cls,
        data: Any
    ) -> Any:
        """
        Generates dedup_hash before Pydantic creates
        the JobCreate model.

        URL normalization is performed before hashing so:

            https://example.com/job

        and:

            https://example.com/job/

        produce the same deduplication hash.
        """

        # ----------------------------------------------------
        # Make sure input is a dictionary
        # ----------------------------------------------------

        if not isinstance(
            data,
            dict
        ):
            return data

        # ----------------------------------------------------
        # Preserve an existing hash
        # ----------------------------------------------------

        existing_hash = data.get(
            "dedup_hash"
        )

        if existing_hash:
            return data

        # ====================================================
        # COMPANY
        # ====================================================

        company = str(
            data.get(
                "company",
                ""
            )
            or ""
        ).strip().lower()

        # ====================================================
        # TITLE
        # ====================================================

        title = str(
            data.get(
                "title",
                ""
            )
            or ""
        ).strip().lower()

        # ====================================================
        # LOCATION
        # ====================================================

        location = str(
            data.get(
                "location",
                "Location not specified"
            )
            or "Location not specified"
        ).strip().lower()

        # ====================================================
        # URL NORMALIZATION
        # ====================================================

        url = str(
            data.get(
                "url",
                ""
            )
            or ""
        ).strip().rstrip("/").lower()

        # ====================================================
        # BUILD UNIQUE JOB IDENTITY
        # ====================================================

        identity = (
            f"{company}|"
            f"{title}|"
            f"{location}|"
            f"{url}"
        )

        # ====================================================
        # GENERATE SHA-256
        # ====================================================

        dedup_hash = sha256(
            identity.encode(
                "utf-8"
            )
        ).hexdigest()

        # ====================================================
        # COPY INPUT DATA
        # ====================================================

        new_data = dict(
            data
        )

        new_data[
            "dedup_hash"
        ] = dedup_hash

        return new_data


# ============================================================
# JOB IN DATABASE
# ============================================================

class JobInDB(JobCreate):
    """
    Schema representing a job after it enters the
    processing/database stage.

    Workflow state belongs here.
    """

    # ========================================================
    # DATABASE ID
    # ========================================================

    id: Optional[int] = Field(
        default=None
    )

    # ========================================================
    # RELEVANCE SCORE
    # ========================================================

    relevance_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Relevance score generated by relevance engine"
    )

    # ========================================================
    # FILTER STATUS
    # ========================================================

    passed_filter: bool = Field(
        default=False
    )

    # ========================================================
    # PIPELINE STATUS
    # ========================================================

    status: str = Field(
        default="NEW"
    )

    # ========================================================
    # EMAIL STATUS
    # ========================================================

    email_sent: bool = Field(
        default=False
    )