import asyncio
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from app.utils.urls import normalize_url

LINK_COLUMNS = """
    id, url, normalized_url, shortcode, owner_id, is_canonical, label, is_active,
    created_at, updated_at, access_count, last_accessed_at
"""


@dataclass(frozen=True, slots=True)
class LinkRecord:
    id: int
    url: str
    normalized_url: str
    shortcode: str
    owner_id: int | None
    is_canonical: bool
    label: str | None
    is_active: bool
    created_at: str
    updated_at: str
    access_count: int
    last_accessed_at: str | None


class ShortcodeCollisionError(Exception):
    """Raised when a generated shortcode is already reserved."""


class SQLClient:
    def __init__(self, database_path: str = "data/links.db") -> None:
        self.database_path = database_path

    async def create_database(self) -> None:
        path = Path(self.database_path)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)

        async with self._connect() as db:
            await db.execute("PRAGMA journal_mode = WAL")
            columns = await self._table_columns(db, "links")
            if columns and "normalized_url" not in columns:
                await self._migrate_legacy_schema(db)
            elif columns and "is_canonical" not in columns:
                await self._upgrade_v2_schema(db)
            else:
                await self._create_schema(db)
            await db.execute("PRAGMA user_version = 3")
            await db.commit()

    async def get_guest_link_by_url(self, normalized_url: str) -> LinkRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                SELECT {LINK_COLUMNS} FROM links
                WHERE normalized_url = ?
                  AND owner_id IS NULL
                  AND is_canonical = 1
                LIMIT 1
                """,
                (normalized_url,),
            )
            return self._to_record(await cursor.fetchone())

    async def get_link_by_shortcode(self, shortcode: str) -> LinkRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT {LINK_COLUMNS} FROM links WHERE shortcode = ? LIMIT 1",
                (shortcode,),
            )
            return self._to_record(await cursor.fetchone())

    async def get_or_create_guest_link(
        self,
        url: str,
        normalized_url: str,
        shortcode: str,
    ) -> tuple[LinkRecord, bool]:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                INSERT INTO links (url, normalized_url, shortcode, owner_id)
                VALUES (?, ?, ?, NULL)
                ON CONFLICT DO NOTHING
                RETURNING {LINK_COLUMNS}
                """,
                (url, normalized_url, shortcode),
            )
            inserted = self._to_record(await cursor.fetchone())
            if inserted is not None:
                await db.commit()
                return inserted, True

            cursor = await db.execute(
                f"""
                SELECT {LINK_COLUMNS} FROM links
                WHERE normalized_url = ?
                  AND owner_id IS NULL
                  AND is_canonical = 1
                LIMIT 1
                """,
                (normalized_url,),
            )
            existing = self._to_record(await cursor.fetchone())
            await db.rollback()
            if existing is not None:
                return existing, False
            raise ShortcodeCollisionError(shortcode)

    async def insert_guest_link(
        self,
        url: str,
        normalized_url: str,
        shortcode: str,
    ) -> LinkRecord:
        link, _ = await self.get_or_create_guest_link(url, normalized_url, shortcode)
        return link

    async def increment_access_count(self, shortcode: str) -> str | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE links
                SET access_count = access_count + 1,
                    last_accessed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shortcode = ? AND is_active = 1
                RETURNING url
                """,
                (shortcode,),
            )
            row = await cursor.fetchone()
            await db.commit()
            return row[0] if row is not None else None

    async def ping(self) -> None:
        async with self._connect() as db:
            await db.execute("UPDATE links SET updated_at = updated_at WHERE 0")
            await db.commit()

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.database_path, timeout=5)

    @staticmethod
    async def _table_columns(db: aiosqlite.Connection, table: str) -> set[str]:
        cursor = await db.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in await cursor.fetchall()}

    async def _migrate_legacy_schema(self, db: aiosqlite.Connection) -> None:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute("ALTER TABLE links RENAME TO links_legacy")
        await self._create_schema(db)
        cursor = await db.execute(
            """
            SELECT
                id, url, shortcode, createdAt, updatedAt, accessCount
            FROM links_legacy
            ORDER BY id
            """
        )
        legacy_rows = await cursor.fetchall()
        canonical_urls: set[str] = set()
        for row in legacy_rows:
            link_id, url, shortcode, created_at, updated_at, access_count = row
            if shortcode is None:
                continue
            try:
                normalized_url = normalize_url(url)
            except ValueError:
                normalized_url = url
            is_canonical = normalized_url not in canonical_urls
            canonical_urls.add(normalized_url)
            await db.execute(
                """
                INSERT INTO links (
                    id, url, normalized_url, shortcode, owner_id, is_canonical,
                    label, is_active, created_at, updated_at, access_count,
                    last_accessed_at
                )
                VALUES (?, ?, ?, ?, NULL, ?, NULL, 1, ?, ?, ?, NULL)
                """,
                (
                    link_id,
                    url,
                    normalized_url,
                    shortcode,
                    int(is_canonical),
                    created_at,
                    updated_at,
                    access_count,
                ),
            )
        await db.execute("DROP TABLE links_legacy")

    async def _upgrade_v2_schema(self, db: aiosqlite.Connection) -> None:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """
            ALTER TABLE links
            ADD COLUMN is_canonical INTEGER NOT NULL DEFAULT 1
            CHECK (is_canonical IN (0, 1))
            """
        )
        await db.execute("DROP INDEX IF EXISTS ux_guest_link_url")
        await self._create_schema(db)

    @staticmethod
    async def _create_schema(db: aiosqlite.Connection) -> None:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                normalized_url TEXT NOT NULL,
                shortcode TEXT NOT NULL UNIQUE,
                owner_id INTEGER,
                is_canonical INTEGER NOT NULL DEFAULT 1
                    CHECK (is_canonical IN (0, 1)),
                label TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_guest_link_url
            ON links(normalized_url)
            WHERE owner_id IS NULL AND is_canonical = 1
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_links_owner_created
            ON links(owner_id, created_at DESC)
            """
        )

    @staticmethod
    def _to_record(row: tuple | None) -> LinkRecord | None:
        if row is None:
            return None
        return LinkRecord(
            id=row[0],
            url=row[1],
            normalized_url=row[2],
            shortcode=row[3],
            owner_id=row[4],
            is_canonical=bool(row[5]),
            label=row[6],
            is_active=bool(row[7]),
            created_at=row[8],
            updated_at=row[9],
            access_count=row[10],
            last_accessed_at=row[11],
        )
