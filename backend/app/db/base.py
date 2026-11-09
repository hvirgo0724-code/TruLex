"""SQLAlchemy 声明式基类。"""

from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """返回去除时区信息的 UTC 当前时间（适配 ``DATETIME`` 列）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass