"""
Test fixtures.

Uses an in-memory SQLite DB (aiosqlite) instead of Postgres/pgvector for fast,
dependency-free unit tests. The `transcript_chunks.embedding` Vector column is
Postgres-specific, so retrieval-heavy tests that need real vector search are
marked and skipped here — see tests/test_retrieval.py for how those are
exercised against a fake in-memory index instead of the SQL layer directly.
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models.db_models import Base, ChatSession


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        # Skip the pgvector-only table; SQLite can't create a Vector column.
        tables = [t for t in Base.metadata.sorted_tables if t.name != "transcript_chunks"]
        for table in tables:
            await conn.run_sync(table.create)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_session(db_session):
    session = ChatSession(id=uuid.uuid4(), title="Test session", llm_provider="ollama")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session
