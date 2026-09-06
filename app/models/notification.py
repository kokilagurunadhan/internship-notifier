# ============================================================
# NOTIFICATION MODEL
# File: app/models/notification.py
# ============================================================

import enum

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
    func,
    text,
)

from sqlalchemy.orm import relationship

from app.database.database import Base


# ============================================================
# UTC TIME HELPER
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# NOTIFICATION STATUS
# ============================================================

class NotificationStatus(str, enum.Enum):

    PENDING = "PENDING"

    PROCESSING = "PROCESSING"

    SENT = "SENT"

    FAILED = "FAILED"


# ============================================================
# NOTIFICATION MODEL
# ============================================================

class Notification(Base):

    __tablename__ = "notifications"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
    )

    # ========================================================
    # SUBSCRIPTION
    # ========================================================

    subscription_id = Column(
        Integer,
        ForeignKey(
            "subscriptions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # ========================================================
    # USER
    #
    # IMPORTANT:
    #
    # This is part of the notification uniqueness rule.
    #
    # One user should receive one internship only once.
    # ========================================================

    user_email = Column(
        String,
        nullable=False,
    )

    # ========================================================
    # INTERNSHIP
    # ========================================================

    internship_id = Column(
        Integer,
        ForeignKey(
            "internships.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # ========================================================
    # STATUS
    # ========================================================

    status = Column(
        SQLEnum(
            NotificationStatus,
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=NotificationStatus.PENDING,
        server_default=text("'PENDING'"),
    )

    # ========================================================
    # RELEVANCE
    # ========================================================

    relevance_score = Column(
        Float,
        nullable=True,
    )

    # ========================================================
    # TIMESTAMPS
    # ========================================================

    created_at = Column(
        DateTime(timezone=True),
        default=_utc_now,
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        server_default=func.now(),
        nullable=False,
    )

    sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================================================
    # PROCESSING LEASE
    # ========================================================

    processing_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ========================================================
    # IDEMPOTENCY
    #
    # Each logical email delivery can have a persistent key.
    #
    # NULL values are allowed for notifications that have not
    # yet been assigned a delivery key.
    # ========================================================

    idempotency_key = Column(
        String(256),
        nullable=True,
    )

    # ========================================================
    # RETRY
    # ========================================================

    retry_count = Column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )

    next_retry_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    error_message = Column(
        String,
        nullable=True,
    )

    # ========================================================
    # RELATIONSHIPS
    #
    # Use lazy="select" instead of lazy="joined".
    #
    # Dispatcher explicitly uses joinedload() when it needs
    # internship data.
    # ========================================================

    subscription = relationship(
        "Subscription",
        back_populates="notifications",
        lazy="select",
    )

    internship = relationship(
        "Internship",
        back_populates="notifications",
        lazy="select",
    )

    # ========================================================
    # DATABASE CONSTRAINTS / INDEXES
    # ========================================================

    __table_args__ = (

        # ----------------------------------------------------
        # CRITICAL BUSINESS RULE
        #
        # ONE USER + ONE INTERNSHIP = ONE NOTIFICATION
        #
        # This prevents:
        #
        # Subscription A -> Internship X
        # Subscription B -> Internship X
        #
        # from producing two notifications for the same user.
        # ----------------------------------------------------

        UniqueConstraint(
            "user_email",
            "internship_id",
            name="uq_notification_user_internship",
        ),

        # ----------------------------------------------------
        # PENDING DISPATCH QUEUE
        #
        # Only PENDING notifications are actionable here.
        #
        # status is intentionally NOT included as an index
        # column because the partial index guarantees it.
        # ----------------------------------------------------

        Index(
            "ix_notifications_dispatch",
            "next_retry_at",
            "created_at",
            postgresql_where=text(
                "status = 'PENDING'"
            ),
        ),

        # ----------------------------------------------------
        # ZOMBIE RECOVERY
        #
        # Only PROCESSING notifications are included.
        # ----------------------------------------------------

        Index(
            "ix_notifications_zombie_recovery",
            "processing_started_at",
            postgresql_where=text(
                "status = 'PROCESSING'"
            ),
        ),

        # ----------------------------------------------------
        # USER DIGEST LOOKUP
        #
        # Used when finding notifications belonging to one
        # user and filtering by status.
        # ----------------------------------------------------

        Index(
            "ix_notifications_user_status",
            "user_email",
            "status",
            "created_at",
        ),

        # ----------------------------------------------------
        # IDEMPOTENCY KEY
        #
        # Only non-NULL keys must be unique.
        # PostgreSQL partial unique index allows multiple
        # NULL values.
        # ----------------------------------------------------

        Index(
            "uq_notifications_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text(
                "idempotency_key IS NOT NULL"
            ),
        ),
    )

    # ========================================================
    # DEBUG REPRESENTATION
    # ========================================================

    def __repr__(self) -> str:

        return (
            "<Notification("
            f"id={self.id}, "
            f"user_email='{self.user_email}', "
            f"status='{self.status}', "
            f"internship_id={self.internship_id}"
            ")>"
        )