"""Async SQLAlchemy session factory and DB initialisation."""

from collections.abc import AsyncGenerator

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
    _engine = create_async_engine(
        settings.effective_database_url,
        echo=settings.app.env == "development",
        pool_pre_ping=True,
    )
    _AsyncSessionLocal = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields a DB session per request."""
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialised. Call init_db() at startup.")
    async with _AsyncSessionLocal() as session:
        yield session
