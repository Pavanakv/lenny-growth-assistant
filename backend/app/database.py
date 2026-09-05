"""
Async SQLAlchemy engine/session setup.

Uses asyncpg + pgvector for Postgres. A connection failure at startup does not
crash the process (see main.py lifespan) so /api/health can report a clear
"database unavailable" status instead of the container just dying.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a request-scoped DB session."""
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def db_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """Context-manager version for use outside request handlers (e.g. scripts)."""
    async with SessionLocal() as session:
        yield session


async def check_db_connection() -> bool:
    """Used by /api/health. Never raises — returns False on any failure."""
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
