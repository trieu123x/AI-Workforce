from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ---------------------------------------------------------------------------
# We use sync engine for simplicity on Windows (no C++ compiler needed)
# FastAPI stays async, but DB calls use run_in_executor via asyncio
# ---------------------------------------------------------------------------
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),
    echo=settings.APP_DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# Alias for Alembic compatibility
engine = sync_engine


# ---------------------------------------------------------------------------
# Async-compatible dependency using run_in_executor
# ---------------------------------------------------------------------------
import asyncio
from contextvars import copy_context

async def get_db():
    """FastAPI dependency that yields a sync DB session in an async context."""
    db: Session = SyncSessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

