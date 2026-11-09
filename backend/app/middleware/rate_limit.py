"""简单限流依赖（基于 Redis 滑动窗口，按客户端 IP + 路径）。"""

from typing import Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings
from app.core.redis import SlidingWindow, get_redis


def rate_limit(
    limit: int = 60, window_seconds: int = 60, key_prefix: str = "rl"
) -> Callable:
    """返回一个 FastAPI 限流依赖。

    :param limit: 窗口内允许的最大请求数
    :param window_seconds: 滑动窗口时长（秒）
    """

    async def _dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        key = f"{key_prefix}:{client_ip}:{path}"
        limiter = SlidingWindow(get_redis(), key_prefix="ratelimit:sliding_window")
        try:
            allowed = await limiter.allow(key, limit, window_seconds)
        except Exception:
            # 限流服务不可用时放行，避免拖垮主链路
            return
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求过于频繁，请稍后再试",
            )

    return _dependency


# 基于 settings 的默认限流依赖
default_rate_limit = rate_limit(limit=settings.RATE_LIMIT_PER_MINUTE, window_seconds=60)