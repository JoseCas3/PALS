from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.dependencies import get_session
from app.core.config import get_settings
from app.db.base import Base
from app.main import app as fastapi_app
from app.models import AIInteraction, Attempt, Exam, ExamTopic, Mastery, Question, Subject, Topic

_MODELS = (AIInteraction, Attempt, Exam, ExamTopic, Mastery, Question, Subject, Topic)
test_database_url = get_settings().database_url
test_database_name = make_url(test_database_url).database or ""
if not test_database_name.endswith("_test"):
    raise RuntimeError(
        "Backend tests require an explicit disposable database whose name ends with '_test'"
    )
test_engine = create_async_engine(test_database_url, poolclass=NullPool, hide_parameters=True)


@pytest.fixture(scope="session", autouse=True)
async def ensure_database_schema() -> AsyncIterator[None]:
    async with test_engine.connect() as connection:
        table_names = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
        database_columns = await connection.run_sync(
            lambda sync: {
                table_name: {column["name"] for column in inspect(sync).get_columns(table_name)}
                for table_name in Base.metadata.tables
                if table_name in table_names
            }
        )
    missing_tables = set(Base.metadata.tables) - table_names
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(
            f"Test database is not migration-complete; missing tables: {missing}. "
            "Run 'alembic upgrade head' against the disposable test database."
        )
    missing_columns = {
        table_name: set(table.columns.keys()) - database_columns[table_name]
        for table_name, table in Base.metadata.tables.items()
        if set(table.columns.keys()) - database_columns[table_name]
    }
    if missing_columns:
        details = ", ".join(
            f"{table}: {', '.join(sorted(columns))}"
            for table, columns in sorted(missing_columns.items())
        )
        raise RuntimeError(
            f"Test database is not migration-complete; missing columns: {details}. "
            "Run 'alembic upgrade head' against the disposable test database."
        )
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
