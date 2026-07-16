from typing import Protocol

import redis.asyncio as redis


class LinkCache(Protocol):
    async def get(self, shortcode: str) -> str | None: ...

    async def set(self, shortcode: str, url: str) -> None: ...

    async def delete(self, shortcode: str) -> None: ...

    async def ping(self) -> None: ...

    async def close(self) -> None: ...


class RedisClient:
    def __init__(self, url: str, ttl_seconds: int = 3600) -> None:
        self.client = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(shortcode: str) -> str:
        return f"links:{shortcode}"

    async def get(self, shortcode: str) -> str | None:
        return await self.client.get(self._key(shortcode))

    async def set(self, shortcode: str, url: str) -> None:
        await self.client.set(self._key(shortcode), url, ex=self.ttl_seconds)

    async def delete(self, shortcode: str) -> None:
        await self.client.delete(self._key(shortcode))

    async def ping(self) -> None:
        await self.client.ping()

    async def close(self) -> None:
        await self.client.close()
