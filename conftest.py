import os

import pytest_asyncio
from dotenv import load_dotenv


# ============================================================
# TEST DATABASE CONFIGURATION
# ============================================================

load_dotenv()

database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise RuntimeError(
        "DATABASE_URL is required to configure the test database."
    )

os.environ["DATABASE_URL"] = database_url.replace(
    "/internship_notifier",
    "/internship_notifier_test",
    1,
)


# Import the application engine only AFTER
# DATABASE_URL has been redirected to the test database.

from app.database.database import engine


# ============================================================
# DATABASE CLEANUP
# ============================================================

@pytest_asyncio.fixture(autouse=True)
async def dispose_database_engine_after_test():

    yield

    await engine.dispose()