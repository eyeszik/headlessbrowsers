"""
Database session management.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine
from backend.app.core.config import settings


# Synchronous engine for migrations
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    pool_pre_ping=True,
)

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.LOG_LEVEL == "DEBUG",
    future=True,
    pool_pre_ping=True,
)

# Session factories
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session():
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        yield session


def get_session():
    """Dependency for getting sync database sessions."""
    with SessionLocal() as session:
        yield session
