from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.exceptions import RedisError

from app.core.config import Settings
from app.db.redis.links import LinkCache
from app.db.sql.crud import SQLClient
from main import create_app


class MemoryCache:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, shortcode: str) -> str | None:
        return self.values.get(shortcode)

    async def set(self, shortcode: str, url: str) -> None:
        self.values[shortcode] = url

    async def delete(self, shortcode: str) -> None:
        self.values.pop(shortcode, None)

    async def ping(self) -> None:
        return None

    async def close(self) -> None:
        return None


class UnavailableCache(MemoryCache):
    async def get(self, shortcode: str) -> str | None:
        raise RedisError("cache unavailable")

    async def set(self, shortcode: str, url: str) -> None:
        raise RedisError("cache unavailable")

    async def ping(self) -> None:
        raise RedisError("cache unavailable")


@dataclass(frozen=True, slots=True)
class AppHarness:
    app: FastAPI
    client: AsyncClient
    database: SQLClient
    cache: LinkCache


@pytest.fixture
def app_factory(
    tmp_path: Path,
) -> Callable[..., AbstractAsyncContextManager[AppHarness]]:
    next_database = 0

    @asynccontextmanager
    async def build(
        *,
        cache: LinkCache | None = None,
        database: SQLClient | None = None,
    ) -> AsyncIterator[AppHarness]:
        nonlocal next_database
        next_database += 1
        app_database = (
            database
            if database is not None
            else SQLClient(str(tmp_path / f"links-{next_database}.db"))
        )
        app_cache = cache if cache is not None else MemoryCache()
        settings = Settings(
            public_base_url="https://sho.rt",
            database_path=app_database.database_path,
            redis_url="redis://unused.invalid:6379/0",
            cors_origins=[],
            shortcode_length=8,
        )
        app = create_app(settings=settings, database=app_database, cache=app_cache)

        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://testserver",
                follow_redirects=False,
            ) as client:
                yield AppHarness(
                    app=app,
                    client=client,
                    database=app_database,
                    cache=app_cache,
                )

    return build


@pytest.fixture
def unavailable_cache() -> UnavailableCache:
    return UnavailableCache()


@pytest.fixture
def memory_cache() -> MemoryCache:
    return MemoryCache()
