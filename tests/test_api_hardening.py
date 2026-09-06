import pytest
from httpx import ASGITransport, AsyncClient

from main import app


# ============================================================
# HELPER
# ============================================================

@pytest.fixture
def async_client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    )


# ============================================================
# SUBSCRIPTION VALIDATION
# ============================================================

@pytest.mark.asyncio
async def test_create_subscription_rejects_invalid_email(
    async_client,
):
    async with async_client as client:
        response = await client.post(
            "/subscriptions",
            json={
                "user_email": "not-an-email",
                "company": "Microsoft",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_subscription_rejects_oversized_company(
    async_client,
):
    async with async_client as client:
        response = await client.post(
            "/subscriptions",
            json={
                "user_email": "test@example.com",
                "company": "A" * 201,
            },
        )

    assert response.status_code == 422


# ============================================================
# INTERNSHIP VALIDATION
# ============================================================

@pytest.mark.asyncio
async def test_create_internship_rejects_invalid_url(
    async_client,
):
    async with async_client as client:
        response = await client.post(
            "/internships",
            json={
                "company": "Microsoft",
                "title": "Software Engineering Intern",
                "url": "not-a-valid-url",
            },
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_internship_rejects_oversized_company(
    async_client,
):
    async with async_client as client:
        response = await client.post(
            "/internships",
            json={
                "company": "A" * 201,
                "title": "Software Engineering Intern",
                "url": "https://example.com/internship",
            },
        )

    assert response.status_code == 422


# ============================================================
# PATH PARAMETER VALIDATION
# ============================================================

@pytest.mark.asyncio
async def test_delete_subscription_rejects_zero_id(
    async_client,
):
    async with async_client as client:
        response = await client.delete(
            "/subscriptions/0"
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_subscription_rejects_negative_id(
    async_client,
):
    async with async_client as client:
        response = await client.delete(
            "/subscriptions/-1"
        )

    assert response.status_code == 422


# ============================================================
# QUERY PARAMETER VALIDATION
# ============================================================

@pytest.mark.asyncio
async def test_search_internships_rejects_empty_company(
    async_client,
):
    async with async_client as client:
        response = await client.get(
            "/search-internships",
            params={"company": ""},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_internships_rejects_oversized_company(
    async_client,
):
    async with async_client as client:
        response = await client.get(
            "/search-internships",
            params={"company": "A" * 201},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_search_and_save_rejects_oversized_company(
    async_client,
):
    async with async_client as client:
        response = await client.post(
            "/search-and-save",
            params={"company": "A" * 201},
        )

    assert response.status_code == 422


# ============================================================
# HEALTH CHECK
# ============================================================

@pytest.mark.asyncio
async def test_healthz_returns_healthy_when_database_is_available(
    async_client,
    monkeypatch,
):
    import main

    class FakeConnection:
        async def execute(self, query):
            return 1

    class FakeConnectionContext:
        async def __aenter__(self):
            return FakeConnection()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConnectionContext()

    monkeypatch.setattr(
        main,
        "engine",
        FakeEngine(),
    )

    async with async_client as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
    }


# ============================================================
# CORS
# ============================================================

@pytest.mark.asyncio
async def test_cors_allows_configured_origin(
    async_client,
):
    async with async_client as client:
        response = await client.options(
            "/healthz",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin")
        == "http://localhost:3000"
    )


@pytest.mark.asyncio
async def test_cors_rejects_arbitrary_origin(
    async_client,
):
    async with async_client as client:
        response = await client.options(
            "/healthz",
            headers={
                "Origin": "https://evil-example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert (
        response.headers.get("access-control-allow-origin")
        != "https://evil-example.com"
    )


@pytest.mark.asyncio
async def test_cors_does_not_use_wildcard_origin(
    async_client,
):
    async with async_client as client:
        response = await client.options(
            "/healthz",
            headers={
                "Origin": "https://evil-example.com",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert (
        response.headers.get("access-control-allow-origin")
        != "*"
    )