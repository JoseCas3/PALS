from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.health import database_is_ready
from app.main import app


@pytest.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_is_independent_of_database(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_ready_when_database_is_connected(async_client: AsyncClient) -> None:
    async def connected() -> bool:
        return True

    app.dependency_overrides[database_is_ready] = connected
    response = await async_client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}


@pytest.mark.asyncio
async def test_not_ready_when_database_is_unavailable(async_client: AsyncClient) -> None:
    async def unavailable() -> bool:
        return False

    app.dependency_overrides[database_is_ready] = unavailable
    response = await async_client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unavailable"}


@pytest.mark.asyncio
async def test_local_web_origin_is_allowed(async_client: AsyncClient) -> None:
    response = await async_client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
