"""Database base configuration."""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from apps.shared.config import settings

# Base class for all models
Base = declarative_base()

# Async engine and session factory
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+psycopg://"),
    echo=settings.database_echo,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine (for Alembic migrations)
sync_engine = create_engine(
    settings.database_url.replace("postgresql+psycopg://", "postgresql://"),
    echo=settings.database_echo,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_session():
    """Get sync database session (for migrations)."""
    return SessionLocal()

