"""Redis 异步客户端 + 令牌桶 / 滑动窗口限流工具。"""

import time
from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings

_client: Optional[aioredis.Redis] = None

# 令牌桶 Lua 脚本（原子刷新令牌 + 扣减）
_TOKEN_BUCKET_LUA = """
local tokens_key = KEYS[1]
local timestamp_key = KEYS[2]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

local tokens = tonumber(redis.call('GET', tokens_key))
if tokens == nil then
    tokens = capacity
end
local last_refill = tonumber(redis.call('GET', timestamp_key))
if last_refill == nil then
    last_refill = now
end
local delta = math.max(0, now - last_refill)
local refill = math.floor(delta * refill_rate)
tokens = math.min(capacity, tokens + refill)
redis.call('SET', timestamp_key, now)

local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end
redis.call('SET', tokens_key, tokens)
redis.call('EXPIRE', tokens_key, math.ceil(capacity / refill_rate) + 60)
redis.call('EXPIRE', timestamp_key, math.ceil(capacity / refill_rate) + 60)
return allowed
"""

# 滑动窗口 Lua 脚本（ZSET 记录请求时间戳）
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, window)
    return 1
end
return 0
"""


def get_redis() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


class TokenBucket:
    """令牌桶限流：按恒定速率补充令牌，突发流量可瞬时放行（capacity 上限）。"""

    def __init__(
        self,
        redis: aioredis.Redis,
        key_prefix: str = "ratelimit:token_bucket",
        capacity: int = 30,
        refill_rate: float = 1.0,
    ) -> None:
        self._redis = redis
        self._key_prefix = key_prefix
        self._capacity = capacity
        self._refill_rate = refill_rate

    async def allow(self, key: str, requested: int = 1) -> bool:
        tokens_key = f"{self._key_prefix}:{key}:tokens"
        timestamp_key = f"{self._key_prefix}:{key}:ts"
        now = time.time()
        result = await self._redis.eval(
            _TOKEN_BUCKET_LUA,
            2,
            tokens_key,
            timestamp_key,
            self._capacity,
            self._refill_rate,
            requested,
            now,
        )
        return bool(result)


class SlidingWindow:
    """滑动窗口限流：统计最近 window 秒内的请求数。"""

    def __init__(
        self, redis: aioredis.Redis, key_prefix: str = "ratelimit:sliding_window"
    ) -> None:
        self._redis = redis
        self._key_prefix = key_prefix

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        redis_key = f"{self._key_prefix}:{key}"
        now = time.time()
        member = f"{now:.6f}"
        result = await self._redis.eval(
            _SLIDING_WINDOW_LUA, 1, redis_key, limit, window_seconds, now, member
        )
        return bool(result)