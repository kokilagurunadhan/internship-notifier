from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    Float,
    Index,
    func
)
from pgvector.sqlalchemy import Vector
from app.database.database import Base


class HistoricalJob(Base):

    __tablename__ = "historical_jobs"

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
        index=True
    )

    title = Column(
        String,
        nullable=False
    )

    location = Column(
        String,
        nullable=True
    )

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
    # JOB DATE
    # ============================================================

    posted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        server_default=func.now(),
        onupdate=func.now()
    )

    # ============================================================
    # FILTER RESULT
    # ============================================================

    passed = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True
    )

    # ============================================================
    # RELEVANCE
    # ============================================================

    # Supports decimal AI / semantic scores.
    #
    # Examples:
    #      0.87
    #      0.6234
    #      87.5
    #
    # The exact scoring convention will be locked by
    # the relevance engine.

    relevance_score = Column(
        Float,
        nullable=True
    )

    # ============================================================
    # JOB STATUS
    # ============================================================

    status = Column(
        String,
        nullable=False,
        default="NEW"
    )

    # ============================================================
    # ACTIVE / SOFT DELETE
    # ============================================================

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True
    )

    # ============================================================
    # DETERMINISTIC JOB IDENTITY
    # ============================================================

    # MD5 produces exactly 32 hexadecimal characters.

    job_hash = Column(
        String(32),
        nullable=False,
        unique=True,
        index=True
    )

    # ============================================================
    # VECTOR EMBEDDING
    # ============================================================

    # 384 dimensions must match the embedding model
    # selected by the semantic engine.

    embedding = Column(
        Vector(384),
        nullable=True
    )

    # ============================================================
    # CREATED TIME
    # ============================================================

    # PostgreSQL generates this timestamp at INSERT time.
    # This works correctly for:
    #
    # - SQLAlchemy ORM
    # - asyncpg
    # - raw SQL INSERT
    # - bulk INSERT
    # - ARQ workers
    #
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True
    )

    # ============================================================
    # INDEXES
    # ============================================================

    __table_args__ = (

        # --------------------------------------------------------
        # PHASE 1 READ ENGINE
        # --------------------------------------------------------
        #
        # Main query:
        #
        # passed = TRUE
        # AND is_active = TRUE
        # AND created_at >= NOW() - 7 days
        #
        # --------------------------------------------------------

        Index(
            "ix_historical_jobs_read_engine",
            "passed",
            "is_active",
            "created_at"
        ),

        # --------------------------------------------------------
        # NEWEST RELEVANT JOBS
        # --------------------------------------------------------

        Index(
            "ix_historical_jobs_passed_posted",
            "passed",
            "is_active",
            "posted_at"
        ),

        # --------------------------------------------------------
        # VECTOR SEARCH (PGVECTOR HNSW)
        # --------------------------------------------------------

        Index(
            "ix_historical_jobs_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),

    )