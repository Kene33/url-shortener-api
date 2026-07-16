import logging
from dataclasses import dataclass

from redis.exceptions import RedisError

from app.db.redis.links import LinkCache
from app.db.sql.crud import LinkRecord, SQLClient, ShortcodeCollisionError
from app.utils.generate import generate_code

logger = logging.getLogger(__name__)


class LinkCreationError(Exception):
    """Raised when a unique shortcode cannot be allocated."""


class LinkDisabledError(Exception):
    """Raised when an inactive guest link already reserves a URL."""


@dataclass(frozen=True, slots=True)
class CreateLinkResult:
    link: LinkRecord
    created: bool


class LinkService:
    def __init__(
        self,
        database: SQLClient,
        cache: LinkCache,
        shortcode_length: int = 8,
        max_attempts: int = 10,
    ) -> None:
        self.database = database
        self.cache = cache
        self.shortcode_length = shortcode_length
        self.max_attempts = max_attempts

    async def create_guest_link(
        self,
        url: str,
        normalized_url: str,
    ) -> CreateLinkResult:
        for _ in range(self.max_attempts):
            shortcode = generate_code(self.shortcode_length)
            try:
                link, created = await self.database.get_or_create_guest_link(
                    url=url,
                    normalized_url=normalized_url,
                    shortcode=shortcode,
                )
            except ShortcodeCollisionError:
                continue

            if not link.is_active:
                raise LinkDisabledError(normalized_url)
            if created:
                await self._cache_set(link.shortcode, link.url)
            return CreateLinkResult(link=link, created=created)

        raise LinkCreationError("Unable to allocate a unique shortcode")

    async def create_user_link(
        self,
        *,
        url: str,
        normalized_url: str,
        owner_id: int,
        label: str | None,
        reuse: bool,
    ) -> CreateLinkResult:
        for _ in range(self.max_attempts):
            shortcode = generate_code(self.shortcode_length)
            try:
                link, created = await self.database.get_or_create_user_link(
                    url=url,
                    normalized_url=normalized_url,
                    shortcode=shortcode,
                    owner_id=owner_id,
                    label=label,
                    reuse=reuse,
                )
            except ShortcodeCollisionError:
                continue
            if created:
                await self._cache_set(link.shortcode, link.url)
            return CreateLinkResult(link=link, created=created)
        raise LinkCreationError("Unable to allocate a unique shortcode")

    async def update_link_metadata(
        self,
        shortcode: str,
        *,
        owner_id: int | None,
        label: str | None,
        set_label: bool,
        is_active: bool | None,
        set_active: bool,
    ) -> LinkRecord | None:
        link = await self.database.update_link_metadata(
            shortcode,
            owner_id=owner_id,
            label=label,
            set_label=set_label,
            is_active=is_active,
            set_active=set_active,
        )
        if link is not None:
            if link.is_active:
                await self._cache_set(link.shortcode, link.url)
            else:
                await self._cache_delete(link.shortcode)
        return link

    async def resolve(self, shortcode: str) -> LinkRecord | None:
        cached_url = await self._cache_get(shortcode)
        if cached_url is not None:
            stored_url = await self.database.increment_access_count(shortcode)
            if stored_url is not None:
                if stored_url != cached_url:
                    logger.warning("Correcting inconsistent cache entry for %s", shortcode)
                    await self._cache_set(shortcode, stored_url)
                return LinkRecord(
                    id=0,
                    url=stored_url,
                    normalized_url=stored_url,
                    shortcode=shortcode,
                    owner_id=None,
                    is_canonical=True,
                    label=None,
                    is_active=True,
                    created_at="",
                    updated_at="",
                    access_count=0,
                    last_accessed_at=None,
                )
            await self._cache_delete(shortcode)

        link = await self.database.get_link_by_shortcode(shortcode)
        if link is None or not link.is_active:
            return link

        stored_url = await self.database.increment_access_count(shortcode)
        if stored_url is None:
            return await self.database.get_link_by_shortcode(shortcode)
        await self._cache_set(shortcode, stored_url)
        return link

    async def _cache_get(self, shortcode: str) -> str | None:
        try:
            return await self.cache.get(shortcode)
        except (RedisError, OSError):
            logger.warning("Redis unavailable while reading %s", shortcode)
            return None

    async def _cache_set(self, shortcode: str, url: str) -> None:
        try:
            await self.cache.set(shortcode, url)
        except (RedisError, OSError):
            logger.warning("Redis unavailable while caching %s", shortcode)

    async def _cache_delete(self, shortcode: str) -> None:
        try:
            await self.cache.delete(shortcode)
        except (RedisError, OSError):
            logger.warning("Redis unavailable while invalidating %s", shortcode)
