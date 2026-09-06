import pytest_asyncio

from app.database.database import engine


@pytest_asyncio.fixture(autouse=True)
async def dispose_database_engine_after_test():
    yield

    await engine.dispose()