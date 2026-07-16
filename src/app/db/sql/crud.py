import asyncio
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from app.utils.urls import normalize_url

LINK_COLUMNS = """
    id, url, normalized_url, shortcode, owner_id, is_canonical, label, is_active,
    created_at, updated_at, access_count, last_accessed_at
"""
QUALIFIED_LINK_COLUMNS = """
    links.id, links.url, links.normalized_url, links.shortcode, links.owner_id,
    links.is_canonical, links.label, links.is_active, links.created_at,
    links.updated_at, links.access_count, links.last_accessed_at
"""
USER_COLUMNS = """
    id, email, password_hash, is_admin, is_active, email_verified,
    created_at, updated_at
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


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: int
    email: str
    password_hash: str
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: str
    updated_at: str


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
            await db.execute("PRAGMA user_version = 4")
            await db.commit()

    async def create_user(
        self,
        email: str,
        password_hash: str,
        *,
        is_admin: bool = False,
    ) -> UserRecord:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                INSERT INTO users (email, password_hash, is_admin)
                VALUES (?, ?, ?)
                RETURNING {USER_COLUMNS}
                """,
                (email, password_hash, int(is_admin)),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            assert user is not None
            return user

    async def get_user_by_id(self, user_id: int) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT {USER_COLUMNS} FROM users WHERE id = ? LIMIT 1",
                (user_id,),
            )
            return self._to_user(await cursor.fetchone())

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT {USER_COLUMNS} FROM users WHERE email = ? COLLATE NOCASE LIMIT 1",
                (email,),
            )
            return self._to_user(await cursor.fetchone())

    async def mark_email_verified(self, user_id: int) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET email_verified = 1, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                RETURNING {USER_COLUMNS}
                """,
                (user_id,),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

    async def update_password(self, user_id: int, password_hash: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE users
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (password_hash, user_id),
            )
            await db.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND revoked_at IS NULL
                """,
                (user_id,),
            )
            await db.commit()

    async def store_refresh_token(
        self,
        user_id: int,
        token_hash: str,
        expires_at: str,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token_hash, expires_at),
            )
            await db.commit()

    async def consume_refresh_token(self, token_hash: str) -> UserRecord | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT user_id FROM refresh_tokens
                WHERE token_hash = ?
                  AND revoked_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                LIMIT 1
                """,
                (token_hash,),
            )
            row = await cursor.fetchone()
            if row is None:
                await db.rollback()
                return None
            await db.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = CURRENT_TIMESTAMP
                WHERE token_hash = ?
                """,
                (token_hash,),
            )
            cursor = await db.execute(
                f"SELECT {USER_COLUMNS} FROM users WHERE id = ? LIMIT 1",
                (row[0],),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

    async def revoke_refresh_token(self, token_hash: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP)
                WHERE token_hash = ?
                """,
                (token_hash,),
            )
            await db.commit()

    async def store_action_token(
        self,
        user_id: int,
        purpose: str,
        token_hash: str,
        expires_at: str,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE action_tokens
                SET used_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND purpose = ? AND used_at IS NULL
                """,
                (user_id, purpose),
            )
            await db.execute(
                """
                INSERT INTO action_tokens (user_id, purpose, token_hash, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, purpose, token_hash, expires_at),
            )
            await db.commit()

    async def consume_action_token(
        self,
        purpose: str,
        token_hash: str,
    ) -> UserRecord | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT user_id FROM action_tokens
                WHERE purpose = ?
                  AND token_hash = ?
                  AND used_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                LIMIT 1
                """,
                (purpose, token_hash),
            )
            row = await cursor.fetchone()
            if row is None:
                await db.rollback()
                return None
            await db.execute(
                """
                UPDATE action_tokens
                SET used_at = CURRENT_TIMESTAMP
                WHERE purpose = ? AND token_hash = ?
                """,
                (purpose, token_hash),
            )
            cursor = await db.execute(
                f"SELECT {USER_COLUMNS} FROM users WHERE id = ? LIMIT 1",
                (row[0],),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

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

    async def get_owned_link(self, shortcode: str, owner_id: int) -> LinkRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                SELECT {LINK_COLUMNS} FROM links
                WHERE shortcode = ? AND owner_id = ?
                LIMIT 1
                """,
                (shortcode, owner_id),
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

    async def get_or_create_user_link(
        self,
        *,
        url: str,
        normalized_url: str,
        shortcode: str,
        owner_id: int,
        label: str | None,
        reuse: bool,
    ) -> tuple[LinkRecord, bool]:
        async with self._connect() as db:
            if reuse:
                cursor = await db.execute(
                    f"""
                    SELECT {LINK_COLUMNS} FROM links
                    WHERE owner_id = ?
                      AND normalized_url = ?
                      AND is_active = 1
                    ORDER BY id
                    LIMIT 1
                    """,
                    (owner_id, normalized_url),
                )
                existing = self._to_record(await cursor.fetchone())
                if existing is not None:
                    return existing, False
            try:
                cursor = await db.execute(
                    f"""
                    INSERT INTO links (
                        url, normalized_url, shortcode, owner_id, label, is_canonical
                    )
                    VALUES (?, ?, ?, ?, ?, 1)
                    RETURNING {LINK_COLUMNS}
                    """,
                    (url, normalized_url, shortcode, owner_id, label),
                )
            except aiosqlite.IntegrityError as exc:
                await db.rollback()
                raise ShortcodeCollisionError(shortcode) from exc
            link = self._to_record(await cursor.fetchone())
            await db.commit()
            assert link is not None
            return link, True

    async def list_owner_links(
        self,
        owner_id: int,
        *,
        is_active: bool | None,
        limit: int,
        offset: int,
        sort: str,
    ) -> tuple[list[LinkRecord], int]:
        clauses = ["owner_id = ?"]
        params: list[object] = [owner_id]
        if is_active is not None:
            clauses.append("is_active = ?")
            params.append(int(is_active))
        where = " AND ".join(clauses)
        direction = "ASC" if sort == "created_at_asc" else "DESC"
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM links WHERE {where}",
                params,
            )
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT {LINK_COLUMNS} FROM links
                WHERE {where}
                ORDER BY created_at {direction}, id {direction}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            rows = await cursor.fetchall()
            return [record for row in rows if (record := self._to_record(row))], total

    async def list_all_links(
        self,
        *,
        owner_id: int | None,
        is_active: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[tuple[LinkRecord, str | None]], int]:
        clauses: list[str] = []
        params: list[object] = []
        if owner_id is not None:
            clauses.append("links.owner_id = ?")
            params.append(owner_id)
        if is_active is not None:
            clauses.append("links.is_active = ?")
            params.append(int(is_active))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM links {where}",
                params,
            )
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT {QUALIFIED_LINK_COLUMNS}, users.email
                FROM links
                LEFT JOIN users ON users.id = links.owner_id
                {where}
                ORDER BY links.created_at DESC, links.id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            rows = await cursor.fetchall()
            records: list[tuple[LinkRecord, str | None]] = []
            for row in rows:
                link = self._to_record(row[:12])
                if link is not None:
                    records.append((link, row[12]))
            return records, total

    async def get_link_with_owner(
        self,
        shortcode: str,
    ) -> tuple[LinkRecord, str | None] | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                SELECT {QUALIFIED_LINK_COLUMNS}, users.email
                FROM links
                LEFT JOIN users ON users.id = links.owner_id
                WHERE links.shortcode = ?
                LIMIT 1
                """,
                (shortcode,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            link = self._to_record(row[:12])
            return (link, row[12]) if link is not None else None

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
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[object] = []
        if set_label:
            assignments.append("label = ?")
            params.append(label)
        if set_active:
            assignments.append("is_active = ?")
            params.append(int(bool(is_active)))
        where = "shortcode = ?"
        params.append(shortcode)
        if owner_id is not None:
            where += " AND owner_id = ?"
            params.append(owner_id)
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE links
                SET {", ".join(assignments)}
                WHERE {where}
                RETURNING {LINK_COLUMNS}
                """,
                params,
            )
            link = self._to_record(await cursor.fetchone())
            await db.commit()
            return link

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[UserRecord], int]:
        async with self._connect() as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT {USER_COLUMNS} FROM users
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()
            return [user for row in rows if (user := self._to_user(row))], total

    async def update_user_admin_fields(
        self,
        user_id: int,
        *,
        is_active: bool | None,
        set_active: bool,
        is_admin: bool | None,
        set_admin: bool,
    ) -> UserRecord | None:
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[object] = []
        if set_active:
            assignments.append("is_active = ?")
            params.append(int(bool(is_active)))
        if set_admin:
            assignments.append("is_admin = ?")
            params.append(int(bool(is_admin)))
        params.append(user_id)
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET {", ".join(assignments)}
                WHERE id = ?
                RETURNING {USER_COLUMNS}
                """,
                params,
            )
            user = self._to_user(await cursor.fetchone())
            if set_active and not is_active:
                await db.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP)
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
            await db.commit()
            return user

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
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1)),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                email_verified INTEGER NOT NULL DEFAULT 0
                    CHECK (email_verified IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
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
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user
            ON refresh_tokens(user_id, revoked_at)
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS action_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                purpose TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_action_tokens_user_purpose
            ON action_tokens(user_id, purpose, used_at)
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

    @staticmethod
    def _to_user(row: tuple | None) -> UserRecord | None:
        if row is None:
            return None
        return UserRecord(
            id=row[0],
            email=row[1],
            password_hash=row[2],
            is_admin=bool(row[3]),
            is_active=bool(row[4]),
            email_verified=bool(row[5]),
            created_at=row[6],
            updated_at=row[7],
        )
