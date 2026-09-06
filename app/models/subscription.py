# ============================================================
# SUBSCRIPTION MODEL
# File: app/models/subscription.py
# ============================================================

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    UniqueConstraint,
    Index,
    Enum
)

from sqlalchemy.orm import relationship

from app.database.database import Base


# ============================================================
# UTC TIME
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# SUBSCRIPTION MODEL
# ============================================================

class Subscription(Base):

    __tablename__ = "subscriptions"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # ========================================================
    # USER EMAIL
    # ========================================================

    user_email = Column(
        String,
        nullable=False,
        index=True
    )

    # ========================================================
    # COMPANY
    # ========================================================

    company = Column(
        String,
        nullable=False,
        index=True
    )

    # ========================================================
    # DOMAIN
    # ========================================================

    domain = Column(
        String,
        nullable=True,
        index=True
    )

    # ========================================================
    # ACTIVE STATUS
    # ========================================================

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )

    # ========================================================
    # SUBSCRIPTION STATUS
    # ========================================================

    status = Column(
        Enum(
            "ACTIVE",
            "PAUSED",
            "CANCELLED",
            name="subscription_status"
        ),
        nullable=False,
        default="ACTIVE"
    )

    # ========================================================
    # CREATED TIME
    # ========================================================

    created_at = Column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False
    )

    # ========================================================
    # ORM RELATIONSHIP
    # ========================================================

    notifications = relationship(
        "Notification",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )

    # ========================================================
    # DATABASE CONSTRAINTS
    # ========================================================

    __table_args__ = (

        # ----------------------------------------------------
        # One subscription per user + company + domain
        # ----------------------------------------------------

        UniqueConstraint(
            "user_email",
            "company",
            "domain",
            name="uq_subscription_user_company_domain"
        ),

        # ----------------------------------------------------
        # Fast scheduler lookup
        # ----------------------------------------------------

        Index(
            "ix_subscriptions_company_domain_active",
            "company",
            "domain",
            "is_active"
        ),

    )