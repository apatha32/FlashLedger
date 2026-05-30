"""
Database connection and session management
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

# Database URL — defaults to SQLite for zero-config local/HF Spaces runs
_RAW_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./flashledger.db"
)
# Normalise Heroku-style postgres:// URLs
DATABASE_URL = _RAW_URL.replace("postgres://", "postgresql+asyncpg://", 1)

_IS_SQLITE = DATABASE_URL.startswith("sqlite")

# SQLite does not support pool_size / max_overflow
if _IS_SQLITE:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
    )

# Session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


async def init_db():
    """Initialize database tables"""
    from app.db.models import Trade  # Import models to register them
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """Dependency to get database session"""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
