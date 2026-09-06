# ============================================================
# INTERNSHIP MODEL
# File: app/models/internship.py
# ============================================================

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Internship(Base):

    __tablename__ = "internships"

    # ============================================================
    # PRIMARY KEY
    # ============================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ============================================================
    # JOB INFORMATION
    # ============================================================

    company = Column(
        String,
        nullable=False,
        index=True  # Fast lookup for get_subscriptions_for_company()
    )

    title = Column(
        String,
        nullable=False
    )

    location = Column(
        String,
        nullable=True
    )

    # ============================================================
    # CANONICAL JOB URL
    #
    # CRITICAL:
    # Multiple crawlers/sources can discover the same job.
    # UNIQUE URL prevents duplicate history records.
    # ============================================================

    url = Column(
        String,
        nullable=False,
        unique=True,
        index=True
    )

    description = Column(
        Text,
        nullable=True
    )

    source = Column(
        String,
        nullable=True
    )

    via = Column(
        String,
        nullable=True
    )

    # ============================================================
    # RELEVANCE SCORE
    # ============================================================

    relevance_score = Column(
        Float,
        nullable=True
    )

    # ============================================================
    # FILTER STATUS
    # ============================================================

    passed_filter = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # ============================================================
    # JOB STATUS
    #
    # NEW
    # RELEVANT
    # LOW_RELEVANCE
    # ============================================================

    status = Column(
        String(30),
        default="NEW",
        nullable=False
    )

    # ============================================================
    # EMAIL STATUS
    #
    # Kept for historical compatibility.
    # Actual delivery state is now controlled by Notification.
    # ============================================================

    email_sent = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # ============================================================
    # TIMELINE
    # ============================================================

    created_at = Column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False
    )

    last_seen_at = Column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False
    )

    # ============================================================
    # ORM RELATIONSHIP
    # ============================================================

    notifications = relationship(
        "Notification",
        back_populates="internship",
        cascade="all, delete-orphan",
    )

    # ============================================================
    # INDEXES
    # ============================================================

    __table_args__ = (
        # Optimizes dashboard & notification generator window checks
        Index(
            "ix_internships_company_created",
            "company",
            "created_at"
        ),

        # Optimizes filter queries: WHERE passed_filter = TRUE AND created_at >= cutoff
        Index(
            "ix_internships_filter_created",
            "passed_filter",
            "created_at"
        ),

        # Useful for scheduler/history freshness queries
        Index(
            "ix_internships_last_seen",
            "last_seen_at"
        ),
    )