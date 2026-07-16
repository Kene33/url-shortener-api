import asyncio
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import aiosqlite

from app.utils.urls import normalize_url

LINK_COLUMNS = """
    id, url, normalized_url, shortcode, owner_id, is_canonical, label, is_active,
    folder_id, created_at, updated_at, access_count, last_accessed_at, expires_at
"""
QUALIFIED_LINK_COLUMNS = """
    links.id, links.url, links.normalized_url, links.shortcode, links.owner_id,
    links.is_canonical, links.label, links.is_active, links.folder_id,
    links.created_at, links.updated_at, links.access_count, links.last_accessed_at,
    links.expires_at
"""
USER_COLUMNS = """
    id, email, password_hash, is_admin, is_active, email_verified,
    display_name, avatar_path, pending_email, deleted_at, links_expire_at,
    two_factor_enabled, created_at, updated_at
"""
FOLDER_COLUMNS = "id, user_id, name, color, created_at, updated_at"
PREFERENCES_COLUMNS = """
    user_id, theme, language, email_notifications, system_notifications,
    created_at, updated_at
"""
NOTIFICATION_COLUMNS = """
    id, user_id, type, key, payload_json, read_at, created_at
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
    folder_id: int | None
    created_at: str
    updated_at: str
    access_count: int
    last_accessed_at: str | None
    expires_at: str | None


@dataclass(frozen=True, slots=True)
class UserRecord:
    id: int
    email: str
    password_hash: str
    is_admin: bool
    is_active: bool
    email_verified: bool
    display_name: str | None
    avatar_path: str | None
    pending_email: str | None
    deleted_at: str | None
    links_expire_at: str | None
    two_factor_enabled: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class FolderRecord:
    id: int
    user_id: int
    name: str
    color: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class PreferenceRecord:
    user_id: int
    theme: str
    language: str
    email_notifications: bool
    system_notifications: bool
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class NotificationRecord:
    id: int
    user_id: int
    type: str
    key: str
    payload: dict[str, object]
    read_at: str | None
    created_at: str


@dataclass(frozen=True, slots=True)
class AdminSettingsRecord:
    user_link_retention_days: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class ActionTokenRecord:
    user: UserRecord
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class TwoFactorChallengeRecord:
    user_id: int
    purpose: str
    login_token: str | None


@dataclass(frozen=True, slots=True)
class AnalyticsPoint:
    bucket_start: str
    count: int


class ShortcodeCollisionError(Exception):
    pass


class SQLClient:
    def __init__(self, database_path: str = "data/links.db") -> None:
        self.database_path = database_path

    async def create_database(self) -> None:
        path = Path(self.database_path)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)

        async with self._connect() as db:
            await db.execute("PRAGMA journal_mode = WAL")
            await db.execute("PRAGMA foreign_keys = ON")
            columns = await self._table_columns(db, "links")
            if columns and "normalized_url" not in columns:
                await self._migrate_legacy_schema(db)
            elif columns and "is_canonical" not in columns:
                await self._upgrade_v2_schema(db)
            await self._create_schema(db)
            await self._ensure_user_columns(db)
            await self._ensure_link_columns(db)
            await db.execute("PRAGMA user_version = 5")
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
            await db.execute(
                """
                INSERT OR IGNORE INTO preferences (user_id)
                VALUES (last_insert_rowid())
                """
            )
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

    async def update_password(
        self,
        user_id: int,
        password_hash: str,
        *,
        keep_refresh_token_hash: str | None = None,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE users
                SET password_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (password_hash, user_id),
            )
            if keep_refresh_token_hash is None:
                await db.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND revoked_at IS NULL
                    """,
                    (user_id,),
                )
            else:
                await db.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                      AND revoked_at IS NULL
                      AND token_hash != ?
                    """,
                    (user_id, keep_refresh_token_hash),
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

    async def consume_refresh_token(self, token_hash: str) -> tuple[UserRecord, str] | None:
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
            return (user, token_hash) if user is not None else None

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

    async def revoke_all_refresh_tokens(self, user_id: int) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP)
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()

    async def store_action_token(
        self,
        user_id: int,
        purpose: str,
        token_hash: str,
        expires_at: str,
        *,
        payload: dict[str, object] | None = None,
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
                INSERT INTO action_tokens (
                    user_id, purpose, token_hash, expires_at, payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, purpose, token_hash, expires_at, json.dumps(payload or {})),
            )
            await db.commit()

    async def consume_action_token(
        self,
        purpose: str,
        token_hash: str,
    ) -> ActionTokenRecord | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT user_id, payload_json FROM action_tokens
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
            if user is None:
                return None
            return ActionTokenRecord(
                user=user,
                payload=json.loads(row[1] or "{}"),
            )

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
            return self._to_link(await cursor.fetchone())

    async def get_link_by_shortcode(self, shortcode: str) -> LinkRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT {LINK_COLUMNS} FROM links WHERE shortcode = ? LIMIT 1",
                (shortcode,),
            )
            return self._to_link(await cursor.fetchone())

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
            return self._to_link(await cursor.fetchone())

    async def get_or_create_guest_link(
        self,
        url: str,
        normalized_url: str,
        shortcode: str,
    ) -> tuple[LinkRecord, bool]:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                INSERT INTO links (url, normalized_url, shortcode, owner_id, is_canonical)
                VALUES (?, ?, ?, NULL, 1)
                ON CONFLICT DO NOTHING
                RETURNING {LINK_COLUMNS}
                """,
                (url, normalized_url, shortcode),
            )
            inserted = self._to_link(await cursor.fetchone())
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
            existing = self._to_link(await cursor.fetchone())
            await db.rollback()
            if existing is not None:
                return existing, False
            raise ShortcodeCollisionError(shortcode)

    async def insert_guest_link(self, url: str, normalized_url: str, shortcode: str) -> LinkRecord:
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
        folder_id: int | None,
        reuse: bool,
    ) -> tuple[LinkRecord, bool]:
        async with self._connect() as db:
            if folder_id is not None:
                await self._assert_folder_owner(db, folder_id, owner_id)
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
                existing = self._to_link(await cursor.fetchone())
                if existing is not None:
                    return existing, False
            try:
                cursor = await db.execute(
                    f"""
                    INSERT INTO links (
                        url, normalized_url, shortcode, owner_id, label, folder_id, is_canonical
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    RETURNING {LINK_COLUMNS}
                    """,
                    (url, normalized_url, shortcode, owner_id, label, folder_id),
                )
            except aiosqlite.IntegrityError as exc:
                await db.rollback()
                raise ShortcodeCollisionError(shortcode) from exc
            link = self._to_link(await cursor.fetchone())
            await db.commit()
            assert link is not None
            return link, True

    async def list_owner_links(
        self,
        owner_id: int,
        *,
        is_active: bool | None,
        q: str | None,
        folder_id: int | None,
        limit: int,
        offset: int,
        sort: str,
    ) -> tuple[list[LinkRecord], int]:
        clauses = ["owner_id = ?"]
        params: list[object] = [owner_id]
        if is_active is not None:
            clauses.append("is_active = ?")
            params.append(int(is_active))
        if folder_id is not None:
            clauses.append("folder_id = ?")
            params.append(folder_id)
        if q:
            clauses.append("(shortcode LIKE ? OR COALESCE(label, '') LIKE ? OR url LIKE ?)")
            needle = f"%{q.strip()}%"
            params.extend([needle, needle, needle])
        where = " AND ".join(clauses)
        order_by = {
            "created_at_desc": "created_at DESC, id DESC",
            "created_at_asc": "created_at ASC, id ASC",
            "access_count_desc": "access_count DESC, id DESC",
            "access_count_asc": "access_count ASC, id ASC",
        }[sort]
        async with self._connect() as db:
            cursor = await db.execute(f"SELECT COUNT(*) FROM links WHERE {where}", params)
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT {LINK_COLUMNS} FROM links
                WHERE {where}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            rows = await cursor.fetchall()
            return [record for row in rows if (record := self._to_link(row))], total

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
            cursor = await db.execute(f"SELECT COUNT(*) FROM links {where}", params)
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
                link = self._to_link(row[:14])
                if link is not None:
                    records.append((link, row[14]))
            return records, total

    async def get_link_with_owner(self, shortcode: str) -> tuple[LinkRecord, str | None] | None:
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
            link = self._to_link(row[:14])
            return (link, row[14]) if link is not None else None

    async def update_link_metadata(
        self,
        shortcode: str,
        *,
        owner_id: int | None,
        label: str | None,
        set_label: bool,
        is_active: bool | None,
        set_active: bool,
        folder_id: int | None,
        set_folder: bool,
    ) -> LinkRecord | None:
        async with self._connect() as db:
            params: list[object] = []
            assignments = ["updated_at = CURRENT_TIMESTAMP"]
            if set_label:
                assignments.append("label = ?")
                params.append(label)
            if set_active:
                assignments.append("is_active = ?")
                params.append(int(bool(is_active)))
            if set_folder:
                if owner_id is not None and folder_id is not None:
                    await self._assert_folder_owner(db, folder_id, owner_id)
                assignments.append("folder_id = ?")
                params.append(folder_id)
            where = "shortcode = ?"
            params.append(shortcode)
            if owner_id is not None:
                where += " AND owner_id = ?"
                params.append(owner_id)
            cursor = await db.execute(
                f"""
                UPDATE links
                SET {", ".join(assignments)}
                WHERE {where}
                RETURNING {LINK_COLUMNS}
                """,
                params,
            )
            link = self._to_link(await cursor.fetchone())
            await db.commit()
            return link

    async def list_users(self, *, limit: int, offset: int) -> tuple[list[UserRecord], int]:
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
            if user is not None and set_active and not is_active:
                await db.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP)
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                await self.create_notification(
                    user_id,
                    kind="system",
                    key="admin_user_deactivated",
                    payload={"user_id": user_id},
                    connection=db,
                )
            await db.commit()
            return user

    async def increment_access_count(self, shortcode: str) -> LinkRecord | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                UPDATE links
                SET access_count = access_count + 1,
                    last_accessed_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE shortcode = ?
                  AND is_active = 1
                  AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                RETURNING id, owner_id, url
                """,
                (shortcode,),
            )
            updated = await cursor.fetchone()
            if updated is None:
                await db.rollback()
                cursor = await db.execute(
                    f"SELECT {LINK_COLUMNS} FROM links WHERE shortcode = ? LIMIT 1",
                    (shortcode,),
                )
                return self._to_link(await cursor.fetchone())
            link_id, owner_id, _ = updated
            now = datetime.now(UTC)
            hour = now.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
            day = now.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            await db.execute(
                """
                INSERT INTO analytics_hourly (link_id, bucket_start, count)
                VALUES (?, ?, 1)
                ON CONFLICT(link_id, bucket_start)
                DO UPDATE SET count = count + 1
                """,
                (link_id, hour),
            )
            await db.execute(
                """
                INSERT INTO analytics_daily (link_id, bucket_start, count)
                VALUES (?, ?, 1)
                ON CONFLICT(link_id, bucket_start)
                DO UPDATE SET count = count + 1
                """,
                (link_id, day),
            )
            await db.commit()
            return await self.get_link_by_shortcode(shortcode)

    async def create_folder(self, user_id: int, name: str, color: str) -> FolderRecord:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                INSERT INTO folders (user_id, name, color)
                VALUES (?, ?, ?)
                RETURNING {FOLDER_COLUMNS}
                """,
                (user_id, name, color),
            )
            folder = self._to_folder(await cursor.fetchone())
            await db.commit()
            assert folder is not None
            return folder

    async def list_folders(self, user_id: int) -> list[tuple[FolderRecord, int]]:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                SELECT {FOLDER_COLUMNS},
                       (SELECT COUNT(*) FROM links WHERE folder_id = folders.id) AS link_count
                FROM folders
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            return [
                (folder, row[6]) for row in rows if (folder := self._to_folder(row[:6])) is not None
            ]

    async def get_folder(self, folder_id: int, user_id: int) -> FolderRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                SELECT {FOLDER_COLUMNS}
                FROM folders
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (folder_id, user_id),
            )
            return self._to_folder(await cursor.fetchone())

    async def update_folder(
        self,
        folder_id: int,
        user_id: int,
        *,
        name: str | None,
        color: str | None,
    ) -> FolderRecord | None:
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[object] = []
        if name is not None:
            assignments.append("name = ?")
            params.append(name)
        if color is not None:
            assignments.append("color = ?")
            params.append(color)
        params.extend([folder_id, user_id])
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE folders
                SET {", ".join(assignments)}
                WHERE id = ? AND user_id = ?
                RETURNING {FOLDER_COLUMNS}
                """,
                params,
            )
            folder = self._to_folder(await cursor.fetchone())
            await db.commit()
            return folder

    async def delete_folder(self, folder_id: int, user_id: int) -> bool:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                UPDATE links
                SET folder_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE folder_id = ?
                """,
                (folder_id,),
            )
            cursor = await db.execute(
                "DELETE FROM folders WHERE id = ? AND user_id = ?",
                (folder_id, user_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_preferences(self, user_id: int) -> PreferenceRecord:
        async with self._connect() as db:
            await db.execute("INSERT OR IGNORE INTO preferences (user_id) VALUES (?)", (user_id,))
            cursor = await db.execute(
                f"SELECT {PREFERENCES_COLUMNS} FROM preferences WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            await db.commit()
            assert row is not None
            return self._to_preferences(row)

    async def update_preferences(
        self,
        user_id: int,
        *,
        theme: str | None,
        language: str | None,
        email_notifications: bool | None,
        system_notifications: bool | None,
    ) -> PreferenceRecord:
        await self.get_preferences(user_id)
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[object] = []
        if theme is not None:
            assignments.append("theme = ?")
            params.append(theme)
        if language is not None:
            assignments.append("language = ?")
            params.append(language)
        if email_notifications is not None:
            assignments.append("email_notifications = ?")
            params.append(int(email_notifications))
        if system_notifications is not None:
            assignments.append("system_notifications = ?")
            params.append(int(system_notifications))
        params.append(user_id)
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE preferences
                SET {", ".join(assignments)}
                WHERE user_id = ?
                RETURNING {PREFERENCES_COLUMNS}
                """,
                params,
            )
            row = await cursor.fetchone()
            await db.commit()
            assert row is not None
            return self._to_preferences(row)

    async def update_profile(
        self,
        user_id: int,
        *,
        display_name: str | None = None,
        set_display_name: bool = False,
        avatar_path: str | None = None,
        set_avatar_path: bool = False,
        pending_email: str | None = None,
        set_pending_email: bool = False,
    ) -> UserRecord | None:
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[object] = []
        if set_display_name:
            assignments.append("display_name = ?")
            params.append(display_name)
        if set_avatar_path:
            assignments.append("avatar_path = ?")
            params.append(avatar_path)
        if set_pending_email:
            assignments.append("pending_email = ?")
            params.append(pending_email)
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
            await db.commit()
            return user

    async def apply_pending_email(self, user_id: int) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET email = pending_email,
                    pending_email = NULL,
                    email_verified = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND pending_email IS NOT NULL
                RETURNING {USER_COLUMNS}
                """,
                (user_id,),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

    async def set_two_factor_enabled(self, user_id: int, enabled: bool) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET two_factor_enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                RETURNING {USER_COLUMNS}
                """,
                (int(enabled), user_id),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

    async def create_notification(
        self,
        user_id: int,
        *,
        kind: str,
        key: str,
        payload: dict[str, object],
        connection: aiosqlite.Connection | None = None,
    ) -> NotificationRecord:
        db_cm = self._reuse_or_connect(connection)
        async with db_cm as db:
            cursor = await db.execute(
                f"""
                INSERT INTO notifications (user_id, type, key, payload_json)
                VALUES (?, ?, ?, ?)
                RETURNING {NOTIFICATION_COLUMNS}
                """,
                (user_id, kind, key, json.dumps(payload)),
            )
            row = await cursor.fetchone()
            if connection is None:
                await db.commit()
            assert row is not None
            return self._to_notification(row)

    async def list_notifications(
        self,
        user_id: int,
        *,
        unread_only: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[NotificationRecord], int]:
        where = "user_id = ?"
        params: list[object] = [user_id]
        if unread_only:
            where += " AND read_at IS NULL"
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM notifications WHERE {where}",
                params,
            )
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT {NOTIFICATION_COLUMNS}
                FROM notifications
                WHERE {where}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            )
            rows = await cursor.fetchall()
            return [self._to_notification(row) for row in rows], total

    async def mark_notification_read(
        self, notification_id: int, user_id: int
    ) -> NotificationRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE notifications
                SET read_at = COALESCE(read_at, CURRENT_TIMESTAMP)
                WHERE id = ? AND user_id = ?
                RETURNING {NOTIFICATION_COLUMNS}
                """,
                (notification_id, user_id),
            )
            row = await cursor.fetchone()
            await db.commit()
            return self._to_notification(row) if row is not None else None

    async def mark_all_notifications_read(self, user_id: int) -> int:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE notifications
                SET read_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND read_at IS NULL
                """,
                (user_id,),
            )
            await db.commit()
            return cursor.rowcount

    async def get_admin_settings(self) -> AdminSettingsRecord:
        async with self._connect() as db:
            await self._ensure_admin_settings(db)
            cursor = await db.execute(
                "SELECT user_link_retention_days, updated_at FROM admin_settings WHERE id = 1"
            )
            row = await cursor.fetchone()
            assert row is not None
            return AdminSettingsRecord(user_link_retention_days=row[0], updated_at=row[1])

    async def update_admin_settings(self, retention_days: int) -> AdminSettingsRecord:
        async with self._connect() as db:
            await self._ensure_admin_settings(db)
            cursor = await db.execute(
                """
                UPDATE admin_settings
                SET user_link_retention_days = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = 1
                RETURNING user_link_retention_days, updated_at
                """,
                (retention_days,),
            )
            row = await cursor.fetchone()
            await db.commit()
            assert row is not None
            return AdminSettingsRecord(user_link_retention_days=row[0], updated_at=row[1])

    async def delete_account(self, user_id: int, retention_days: int) -> UserRecord | None:
        expires_at = (datetime.now(UTC) + timedelta(days=retention_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        placeholder = f"deleted-user-{user_id}@deleted.local"
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                f"""
                UPDATE users
                SET is_active = 0,
                    email = ?,
                    display_name = NULL,
                    avatar_path = NULL,
                    pending_email = NULL,
                    deleted_at = CURRENT_TIMESTAMP,
                    links_expire_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                RETURNING {USER_COLUMNS}
                """,
                (placeholder, expires_at, user_id),
            )
            user = self._to_user(await cursor.fetchone())
            if user is None:
                await db.rollback()
                return None
            await db.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP)
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.execute(
                """
                UPDATE links
                SET expires_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE owner_id = ? AND expires_at IS NULL
                """,
                (expires_at, user_id),
            )
            await self.create_notification(
                user_id,
                kind="system",
                key="account_deleted",
                payload={"links_expire_at": expires_at},
                connection=db,
            )
            await db.commit()
            return user

    async def create_two_factor_challenge(
        self,
        user_id: int,
        purpose: str,
        code_hash: str,
        expires_at: str,
        *,
        login_token_hash: str | None = None,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                UPDATE two_factor_challenges
                SET used_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND purpose = ? AND used_at IS NULL
                """,
                (user_id, purpose),
            )
            await db.execute(
                """
                INSERT INTO two_factor_challenges (
                    user_id, purpose, code_hash, expires_at, login_token_hash
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, purpose, code_hash, expires_at, login_token_hash),
            )
            await db.commit()

    async def consume_two_factor_challenge(
        self,
        purpose: str,
        code_hash: str,
        *,
        login_token_hash: str | None = None,
    ) -> TwoFactorChallengeRecord | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            query = """
                SELECT user_id, login_token_hash
                FROM two_factor_challenges
                WHERE purpose = ?
                  AND code_hash = ?
                  AND used_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
            """
            params: list[object] = [purpose, code_hash]
            if login_token_hash is None:
                query += " AND login_token_hash IS NULL"
            else:
                query += " AND login_token_hash = ?"
                params.append(login_token_hash)
            query += " LIMIT 1"
            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            if row is None:
                await db.rollback()
                return None
            await db.execute(
                """
                UPDATE two_factor_challenges
                SET used_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND purpose = ? AND code_hash = ? AND used_at IS NULL
                """,
                (row[0], purpose, code_hash),
            )
            await db.commit()
            return TwoFactorChallengeRecord(user_id=row[0], purpose=purpose, login_token=None)

    async def get_owner_analytics(
        self,
        user_id: int,
        *,
        period: str,
        timezone: str,
    ) -> tuple[dict[str, float], list[AnalyticsPoint], list[LinkRecord]]:
        return await self._analytics_for_scope(
            "links.owner_id = ?",
            [user_id],
            period=period,
            timezone=timezone,
        )

    async def get_link_analytics(
        self,
        shortcode: str,
        owner_id: int,
        *,
        period: str,
        timezone: str,
    ) -> tuple[dict[str, float], list[AnalyticsPoint], list[LinkRecord]] | None:
        link = await self.get_owned_link(shortcode, owner_id)
        if link is None:
            return None
        result = await self._analytics_for_scope(
            "links.id = ? AND links.owner_id = ?",
            [link.id, owner_id],
            period=period,
            timezone=timezone,
        )
        return result

    async def export_account(self, user_id: int) -> dict[str, object]:
        user = await self.get_user_by_id(user_id)
        preferences = await self.get_preferences(user_id)
        folders = await self.list_folders(user_id)
        links, _ = await self.list_owner_links(
            user_id,
            is_active=None,
            q=None,
            folder_id=None,
            limit=10000,
            offset=0,
            sort="created_at_desc",
        )
        analytics, _, top_links = await self.get_owner_analytics(
            user_id,
            period="90d",
            timezone="UTC",
        )
        assert user is not None
        return {
            "profile": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "avatar_path": user.avatar_path,
                "pending_email": user.pending_email,
                "email_verified": user.email_verified,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            },
            "preferences": self._preferences_to_dict(preferences),
            "folders": [
                {
                    "id": folder.id,
                    "name": folder.name,
                    "color": folder.color,
                    "link_count": count,
                    "created_at": folder.created_at,
                    "updated_at": folder.updated_at,
                }
                for folder, count in folders
            ],
            "links": [self._link_to_export_dict(link) for link in links],
            "aggregate_analytics": {
                **analytics,
                "top_links": [self._link_to_export_dict(link) for link in top_links],
            },
        }

    async def ping(self) -> None:
        async with self._connect() as db:
            await db.execute("SELECT 1")

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self.database_path, timeout=5)

    def _reuse_or_connect(self, connection: aiosqlite.Connection | None):
        if connection is not None:
            return _ConnectionWrapper(connection)
        return self._connect()

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
            SELECT id, url, shortcode, createdAt, updatedAt, accessCount
            FROM links_legacy
            ORDER BY id
            """
        )
        canonical_urls: set[str] = set()
        for row in await cursor.fetchall():
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
                    label, is_active, folder_id, created_at, updated_at,
                    access_count, last_accessed_at, expires_at
                )
                VALUES (?, ?, ?, ?, NULL, ?, NULL, 1, NULL, ?, ?, ?, NULL, NULL)
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
                email_verified INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0, 1)),
                display_name TEXT,
                avatar_path TEXT,
                pending_email TEXT UNIQUE COLLATE NOCASE,
                deleted_at TEXT,
                links_expire_at TEXT,
                two_factor_enabled INTEGER NOT NULL DEFAULT 0
                    CHECK (two_factor_enabled IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                color TEXT NOT NULL,
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
                owner_id INTEGER REFERENCES users(id),
                is_canonical INTEGER NOT NULL DEFAULT 1 CHECK (is_canonical IN (0, 1)),
                label TEXT,
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                folder_id INTEGER REFERENCES folders(id),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT,
                expires_at TEXT
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
            CREATE TABLE IF NOT EXISTS action_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                purpose TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                used_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                theme TEXT NOT NULL DEFAULT 'light',
                language TEXT NOT NULL DEFAULT 'ru',
                email_notifications INTEGER NOT NULL DEFAULT 1
                    CHECK (email_notifications IN (0, 1)),
                system_notifications INTEGER NOT NULL DEFAULT 1
                    CHECK (system_notifications IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                type TEXT NOT NULL,
                key TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                read_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_hourly (
                link_id INTEGER NOT NULL REFERENCES links(id),
                bucket_start TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (link_id, bucket_start)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics_daily (
                link_id INTEGER NOT NULL REFERENCES links(id),
                bucket_start TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (link_id, bucket_start)
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                user_link_retention_days INTEGER NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS two_factor_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                purpose TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                login_token_hash TEXT,
                used_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_links_owner_created
            ON links(owner_id, created_at DESC)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_links_owner_access
            ON links(owner_id, access_count DESC)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_notifications_user_created
            ON notifications(user_id, created_at DESC)
            """
        )

    async def _ensure_user_columns(self, db: aiosqlite.Connection) -> None:
        columns = await self._table_columns(db, "users")
        additions = {
            "display_name": "ALTER TABLE users ADD COLUMN display_name TEXT",
            "avatar_path": "ALTER TABLE users ADD COLUMN avatar_path TEXT",
            "pending_email": "ALTER TABLE users ADD COLUMN pending_email TEXT",
            "deleted_at": "ALTER TABLE users ADD COLUMN deleted_at TEXT",
            "links_expire_at": "ALTER TABLE users ADD COLUMN links_expire_at TEXT",
            "two_factor_enabled": """
                ALTER TABLE users
                ADD COLUMN two_factor_enabled INTEGER NOT NULL DEFAULT 0
                CHECK (two_factor_enabled IN (0, 1))
            """,
        }
        for key, statement in additions.items():
            if key not in columns:
                await db.execute(statement)
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_pending_email ON users(pending_email)"
        )

    async def _ensure_link_columns(self, db: aiosqlite.Connection) -> None:
        columns = await self._table_columns(db, "links")
        additions = {
            "folder_id": "ALTER TABLE links ADD COLUMN folder_id INTEGER REFERENCES folders(id)",
            "expires_at": "ALTER TABLE links ADD COLUMN expires_at TEXT",
        }
        for key, statement in additions.items():
            if key not in columns:
                await db.execute(statement)

    async def _ensure_admin_settings(self, db: aiosqlite.Connection) -> None:
        await db.execute(
            """
            INSERT OR IGNORE INTO admin_settings (id, user_link_retention_days)
            VALUES (1, 365)
            """
        )
        await db.commit()

    async def _assert_folder_owner(
        self,
        db: aiosqlite.Connection,
        folder_id: int,
        owner_id: int,
    ) -> None:
        cursor = await db.execute(
            "SELECT 1 FROM folders WHERE id = ? AND user_id = ? LIMIT 1",
            (folder_id, owner_id),
        )
        if await cursor.fetchone() is None:
            raise sqlite3.IntegrityError("folder does not belong to owner")

    async def _analytics_for_scope(
        self,
        where: str,
        params: list[object],
        *,
        period: str,
        timezone: str,
    ) -> tuple[dict[str, float], list[AnalyticsPoint], list[LinkRecord]]:
        tz = ZoneInfo(timezone)
        days = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}[period]
        now = datetime.now(UTC)
        start = now - timedelta(days=days)
        prev_start = start - timedelta(days=days)
        bucket_table = "analytics_hourly" if period == "24h" else "analytics_daily"
        bucket_floor = start.replace(minute=0, second=0, microsecond=0)
        if period != "24h":
            bucket_floor = bucket_floor.replace(hour=0)

        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT COUNT(*), COALESCE(SUM(access_count), 0) FROM links WHERE {where}",
                params,
            )
            link_count, total_clicks = await cursor.fetchone()
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM links WHERE {where} AND is_active = 1",
                params,
            )
            active_links = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT COALESCE(SUM({bucket_table}.count), 0)
                FROM {bucket_table}
                JOIN links ON links.id = {bucket_table}.link_id
                WHERE {where}
                  AND {bucket_table}.bucket_start >= ?
                  AND {bucket_table}.bucket_start < ?
                """,
                [*params, start.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")],
            )
            current_total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT COALESCE(SUM({bucket_table}.count), 0)
                FROM {bucket_table}
                JOIN links ON links.id = {bucket_table}.link_id
                WHERE {where}
                  AND {bucket_table}.bucket_start >= ?
                  AND {bucket_table}.bucket_start < ?
                """,
                [
                    *params,
                    prev_start.strftime("%Y-%m-%d %H:%M:%S"),
                    start.strftime("%Y-%m-%d %H:%M:%S"),
                ],
            )
            previous_total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"""
                SELECT {bucket_table}.bucket_start, SUM({bucket_table}.count)
                FROM {bucket_table}
                JOIN links ON links.id = {bucket_table}.link_id
                WHERE {where}
                  AND {bucket_table}.bucket_start >= ?
                  AND {bucket_table}.bucket_start < ?
                GROUP BY {bucket_table}.bucket_start
                ORDER BY {bucket_table}.bucket_start ASC
                """,
                [
                    *params,
                    bucket_floor.strftime("%Y-%m-%d %H:%M:%S"),
                    now.strftime("%Y-%m-%d %H:%M:%S"),
                ],
            )
            raw_series = [
                (datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC), row[1])
                for row in await cursor.fetchall()
            ]
            cursor = await db.execute(
                f"""
                SELECT {LINK_COLUMNS}
                FROM links
                WHERE {where}
                ORDER BY access_count DESC, id DESC
                LIMIT 5
                """,
                params,
            )
            top_links = [self._to_link(row) for row in await cursor.fetchall()]

        avg_clicks = float(total_clicks / link_count) if link_count else 0.0
        change_percent = 100.0 if previous_total == 0 and current_total > 0 else 0.0
        if previous_total:
            change_percent = ((current_total - previous_total) / previous_total) * 100
        grouped: dict[str, int] = {}
        bucket_format = "%Y-%m-%d %H:%M:%S" if period == "24h" else "%Y-%m-%d 00:00:00"
        for point_time, count in raw_series:
            local = point_time.astimezone(tz)
            if period == "24h":
                local = local.replace(minute=0, second=0, microsecond=0)
            else:
                local = local.replace(hour=0, minute=0, second=0, microsecond=0)
            key = local.strftime(bucket_format)
            grouped[key] = grouped.get(key, 0) + int(count)
        series = [
            AnalyticsPoint(bucket_start=key, count=value) for key, value in sorted(grouped.items())
        ]
        return (
            {
                "total_clicks": float(total_clicks),
                "active_links": float(active_links),
                "avg_clicks_per_link": avg_clicks,
                "change_percent": round(change_percent, 2),
            },
            series,
            [link for link in top_links if link is not None],
        )

    @staticmethod
    def _to_link(row: tuple | None) -> LinkRecord | None:
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
            folder_id=row[8],
            created_at=row[9],
            updated_at=row[10],
            access_count=row[11],
            last_accessed_at=row[12],
            expires_at=row[13],
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
            display_name=row[6],
            avatar_path=row[7],
            pending_email=row[8],
            deleted_at=row[9],
            links_expire_at=row[10],
            two_factor_enabled=bool(row[11]),
            created_at=row[12],
            updated_at=row[13],
        )

    @staticmethod
    def _to_folder(row: tuple | None) -> FolderRecord | None:
        if row is None:
            return None
        return FolderRecord(
            id=row[0],
            user_id=row[1],
            name=row[2],
            color=row[3],
            created_at=row[4],
            updated_at=row[5],
        )

    @staticmethod
    def _to_preferences(row: tuple) -> PreferenceRecord:
        return PreferenceRecord(
            user_id=row[0],
            theme=row[1],
            language=row[2],
            email_notifications=bool(row[3]),
            system_notifications=bool(row[4]),
            created_at=row[5],
            updated_at=row[6],
        )

    @staticmethod
    def _to_notification(row: tuple) -> NotificationRecord:
        return NotificationRecord(
            id=row[0],
            user_id=row[1],
            type=row[2],
            key=row[3],
            payload=json.loads(row[4]),
            read_at=row[5],
            created_at=row[6],
        )

    @staticmethod
    def _preferences_to_dict(preferences: PreferenceRecord) -> dict[str, object]:
        return {
            "theme": preferences.theme,
            "language": preferences.language,
            "email_notifications": preferences.email_notifications,
            "system_notifications": preferences.system_notifications,
            "created_at": preferences.created_at,
            "updated_at": preferences.updated_at,
        }

    @staticmethod
    def _link_to_export_dict(link: LinkRecord) -> dict[str, object]:
        return {
            "shortcode": link.shortcode,
            "url": link.url,
            "label": link.label,
            "is_active": link.is_active,
            "folder_id": link.folder_id,
            "access_count": link.access_count,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
            "last_accessed_at": link.last_accessed_at,
            "expires_at": link.expires_at,
        }


class _ConnectionWrapper:
    def __init__(self, connection: aiosqlite.Connection) -> None:
        self.connection = connection

    async def __aenter__(self) -> aiosqlite.Connection:
        return self.connection

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False
