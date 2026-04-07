"""Async SQLAlchemy session factory and DB initialisation."""

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .models import Base

_engine = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Create tables if they don't exist. Called at startup."""
    global _engine, _AsyncSessionLocal

    from ..config import get_settings

    settings = get_settings()
    url = settings.effective_database_url

    engine_kwargs: dict = {
        "echo": settings.app.env == "development",
        "pool_pre_ping": True,
    }
    # SQLite requires special async handling
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        engine_kwargs["poolclass"] = StaticPool

    _engine = create_async_engine(url, **engine_kwargs)
    _AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_session_factory() -> Optional[async_sessionmaker[AsyncSession]]:
    """Return the async session factory (available after init_db)."""
    return _AsyncSessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_db() at startup.")
    async with _AsyncSessionLocal() as session:
        yield session
