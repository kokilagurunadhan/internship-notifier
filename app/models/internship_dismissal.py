# ============================================================
# INTERNSHIP DISMISSAL MODEL
# File: app/models/internship_dismissal.py
# ============================================================

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)

from app.database.database import Base


# ============================================================
# UTC TIME
# ============================================================

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# INTERNSHIP DISMISSAL
# ============================================================

class InternshipDismissal(Base):

    __tablename__ = "internship_dismissals"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # USER
    # ========================================================

    user_email = Column(
        String,
        nullable=False,
        index=True,
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
    # TIMESTAMP
    # ========================================================

    dismissed_at = Column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )

    # ========================================================
    # CONSTRAINTS / INDEXES
    # ========================================================

    __table_args__ = (

        # One user can dismiss one internship only once.
        UniqueConstraint(
            "user_email",
            "internship_id",
            name="uq_internship_dismissal_user_internship",
        ),

        Index(
            "ix_internship_dismissals_user",
            "user_email",
            "dismissed_at",
        ),

    )