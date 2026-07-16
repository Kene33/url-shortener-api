import asyncio
import logging
import time
from dataclasses import dataclass

import redis.asyncio as redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RateLimitPolicy:
    scope: str
    limit: int
    window_seconds: int


@dataclass(frozen=True, slots=True)
class RateLimitStatus:
    limit: int
    remaining: int
    reset_after_seconds: int


class RateLimitExceededError(Exception):
    def __init__(self, status: RateLimitStatus) -> None:
        self.status = status


class RateLimiter:
    def __init__(self, redis_url: str | None, *, prefix: str = "ratelimit") -> None:
        self.prefix = prefix
        self.client = (
            redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            if redis_url
            else None
        )
        self._memory_windows: dict[str, tuple[int, float]] = {}
        self._memory_lock = asyncio.Lock()

    async def consume(self, policy: RateLimitPolicy, subject: str) -> RateLimitStatus:
        if self.client is not None:
            try:
                return await self._consume_redis(policy, subject)
            except (RedisError, OSError) as exc:
                logger.warning(
                    "Redis unavailable for rate limiting scope=%s, using in-memory fallback",
                    policy.scope,
                    exc_info=exc,
                )
        return await self._consume_memory(policy, subject)

    async def close(self) -> None:
        if self.client is not None:
            await self.client.close()

    def _redis_key(self, policy: RateLimitPolicy, subject: str) -> str:
        return f"{self.prefix}:{policy.scope}:{subject}"

    async def _consume_redis(self, policy: RateLimitPolicy, subject: str) -> RateLimitStatus:
        assert self.client is not None
        key = self._redis_key(policy, subject)
        count = await self.client.incr(key)
        if count == 1:
            await self.client.expire(key, policy.window_seconds)
            ttl = policy.window_seconds
        else:
            ttl = await self.client.ttl(key)
            if ttl is None or ttl <= 0:
                await self.client.expire(key, policy.window_seconds)
                ttl = policy.window_seconds
        status = RateLimitStatus(
            limit=policy.limit,
            remaining=max(policy.limit - count, 0),
            reset_after_seconds=max(int(ttl), 1),
        )
        if count > policy.limit:
            raise RateLimitExceededError(status)
        return status

    async def _consume_memory(self, policy: RateLimitPolicy, subject: str) -> RateLimitStatus:
        key = self._redis_key(policy, subject)
        now = time.monotonic()
        async with self._memory_lock:
            current, reset_at = self._memory_windows.get(key, (0, now + policy.window_seconds))
            if reset_at <= now:
                current = 0
                reset_at = now + policy.window_seconds
            current += 1
            self._memory_windows[key] = (current, reset_at)
            reset_after_seconds = max(int(reset_at - now), 1)
        status = RateLimitStatus(
            limit=policy.limit,
            remaining=max(policy.limit - current, 0),
            reset_after_seconds=reset_after_seconds,
        )
        if current > policy.limit:
            raise RateLimitExceededError(status)
        return status
