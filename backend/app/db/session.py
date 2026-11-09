"""SQLAlchemy 2.x 异步引擎与会话工厂（MySQL 业务库，async aiomysql）。"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine = create_async_engine(
    settings.MYSQL_URL,
    echo=False,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)