from logging.config import fileConfig
import os

from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from alembic import context

from app.database.database import Base


# ============================================================
# ALEMBIC CONFIGURATION
# ============================================================

config = context.config


# ============================================================
# LOGGING
# ============================================================

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name
    )


# ============================================================
# IMPORT ALL MODELS
#
# IMPORTANT:
# Alembic must know about every SQLAlchemy model before
# autogenerate can compare the models with PostgreSQL.
# ============================================================

from app.models.subscription import Subscription
from app.models.internship import Internship
from app.models.notification import Notification


# ============================================================
# SQLALCHEMY METADATA
# ============================================================

target_metadata = Base.metadata
def include_object(object, name, type_, reflected, compare_to):
    # historical_jobs is a legacy table and is intentionally
    # not managed by the current Alembic migration chain.
    if type_ == "table" and name == "historical_jobs":
        return False

    return True


# ============================================================
# DATABASE URL
# ============================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is required."
    )


# ============================================================
# CONVERT ASYNCPG URL TO SYNCHRONOUS DRIVER
#
# Alembic's normal migration engine is synchronous.
#
# Application:
#
#     postgresql+asyncpg://
#
# Alembic:
#
#     postgresql+psycopg2://
#
# ============================================================

if DATABASE_URL.startswith(
    "postgresql+asyncpg://"
):

    ALEMBIC_DATABASE_URL = DATABASE_URL.replace(
        "postgresql+asyncpg://",
        "postgresql+psycopg2://",
        1
    )

elif DATABASE_URL.startswith(
    "postgresql://"
):

    ALEMBIC_DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1
    )

else:

    ALEMBIC_DATABASE_URL = DATABASE_URL


# ============================================================
# OFFLINE MIGRATIONS
# ============================================================

def run_migrations_offline() -> None:

    context.configure(
    url=ALEMBIC_DATABASE_URL,
    target_metadata=target_metadata,
    include_object=include_object,
    literal_binds=True,

        dialect_opts={
            "paramstyle": "named"
        },

        compare_type=True,

        compare_server_default=True,
    )

    with context.begin_transaction():

        context.run_migrations()


# ============================================================
# ONLINE MIGRATIONS
# ============================================================

def run_migrations_online() -> None:

    connectable = create_engine(

        ALEMBIC_DATABASE_URL,

        poolclass=NullPool,

        future=True,
    )

    with connectable.connect() as connection:

        context.configure(

            connection=connection,

            target_metadata=target_metadata,
            include_object=include_object,

            compare_type=True,

            compare_server_default=True,
        )

        with context.begin_transaction():

            context.run_migrations()

    connectable.dispose()


# ============================================================
# START MIGRATION
# ============================================================

if context.is_offline_mode():

    run_migrations_offline()

else:

    run_migrations_online()