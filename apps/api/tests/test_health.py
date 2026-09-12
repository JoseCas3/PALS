import pytest
from httpx import AsyncClient

from app.api.health import database_is_ready
from app.main import app


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


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
async def test_domain_write_methods_are_allowed_by_cors(
    async_client: AsyncClient, method: str
) -> None:
    response = await async_client.options(
        "/api/v1/subjects",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert method in response.headers["access-control-allow-methods"]
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
