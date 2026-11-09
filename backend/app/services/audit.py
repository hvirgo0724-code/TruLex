"""审计日志落库工具。"""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def record_audit(
    db: AsyncSession,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    detail: Optional[Any] = None,
) -> AuditLog:
    """写入一条审计日志（detail 中的敏感信息应在调用前脱敏）。"""
    log = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        detail=detail,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log