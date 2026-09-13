from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.dependencies import get_session
from app.core.config import get_settings
from app.db.base import Base
from app.main import app as fastapi_app
from app.models import AIInteraction, Attempt, Exam, ExamTopic, Mastery, Question, Subject, Topic

_MODELS = (AIInteraction, Attempt, Exam, ExamTopic, Mastery, Question, Subject, Topic)
test_engine = create_async_engine(get_settings().database_url, poolclass=NullPool)


@pytest.fixture(scope="session", autouse=True)
async def ensure_database_schema() -> AsyncIterator[None]:
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await test_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield session
        await session.close()
        if transaction.is_active:
            await transaction.rollback()


@pytest.fixture
async def async_client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    fastapi_app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        yield client
    fastapi_app.dependency_overrides.clear()
