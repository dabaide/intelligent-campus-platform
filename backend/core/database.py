from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import asyncio
from typing import AsyncGenerator

from core.config import settings

# Async engine - supports both SQLite and PostgreSQL
if "sqlite" in settings.DATABASE_URL:
    # SQLite configuration
    async_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        connect_args={"check_same_thread": False}
    )
else:
    # PostgreSQL configuration
    async_engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=settings.DEBUG,
        future=True
    )

# Async session maker
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()
metadata = MetaData()

# [异步并发底层基建]:
# 初始化数据库连接引擎，全局架构强制采用 AsyncSession 与 asyncio 协程，防止高并发海量请求下由于数据库 I/O 阻塞主线程从而引发服务雪崩。
async def init_db():
    """
    Initialize database tables
    [架构解析]: 数据库初始化，采用 asyncio 协程和 sqlalchemy.ext.asyncio 引擎，保证高并发下数据库读写不会阻塞主线程。
    """
    async with async_engine.begin() as conn:
        # Import models here to register them
        from models import user, conversation, knowledge_base, agent_interaction
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Database initialized successfully")

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
