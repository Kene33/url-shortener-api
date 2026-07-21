# ruff: noqa: E501
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
    two_factor_enabled, role, deletion_requested_at, deletion_scheduled_for,
    anonymized_at, created_at, updated_at
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
    role: str
    deletion_requested_at: str | None
    deletion_scheduled_for: str | None
    anonymized_at: str | None
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
    def __init__(
        self,
        database_path: str = "data/links.db",
        *,
        user_link_retention_days_default: int = 365,
        database_url: str | None = None,
    ) -> None:
        self.database_path = database_path
        self.database_url = database_url
        self.user_link_retention_days_default = user_link_retention_days_default

    async def create_database(self) -> None:
        if self.database_url:
            from app.db.sql.postgres import table_columns

            columns = await table_columns(self.database_url, "links")
            async with self._connect() as db:
                if columns and "normalized_url" not in columns:
                    raise RuntimeError("Unsupported legacy PostgreSQL links schema")
                await self._create_schema(db)
                await self._ensure_user_columns(db)
                await self._ensure_link_columns(db)
                await self._ensure_action_token_columns(db)
                await self._ensure_governance_schema(db)
                await self._ensure_admin_settings(db)
                await db.commit()
            return
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
            await self._ensure_action_token_columns(db)
            await self._ensure_governance_schema(db)
            await db.execute("PRAGMA user_version = 6")
            await db.commit()

    async def create_user(
        self,
        email: str,
        password_hash: str,
        *,
        is_admin: bool = False,
        email_verified: bool = False,
    ) -> UserRecord:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                INSERT INTO users (email, password_hash, is_admin, role, email_verified)
                VALUES (?, ?, ?, ?, ?)
                RETURNING {USER_COLUMNS}
                """,
                (
                    email,
                    password_hash,
                    int(is_admin),
                    "admin" if is_admin else "user",
                    int(email_verified),
                ),
            )
            user = self._to_user(await cursor.fetchone())
            await db.execute(
                """
                INSERT OR IGNORE INTO preferences (user_id)
                VALUES (?)
                """,
                (user.id,),
            )
            await db.commit()
            assert user is not None
            return user

    async def upsert_seed_user(
        self,
        email: str,
        password_hash: str,
        *,
        is_admin: bool,
        display_name: str,
        email_verified: bool = True,
        is_active: bool = True,
        two_factor_enabled: bool = False,
    ) -> UserRecord:
        async with self._connect() as db:
            cursor = await db.execute(
                f"SELECT {USER_COLUMNS} FROM users WHERE email = ? COLLATE NOCASE LIMIT 1",
                (email,),
            )
            existing = self._to_user(await cursor.fetchone())
            if existing is None:
                cursor = await db.execute(
                    f"""
                    INSERT INTO users (
                        email,
                        password_hash,
                        is_admin,
                        is_active,
                        email_verified,
                        display_name,
                        two_factor_enabled
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    RETURNING {USER_COLUMNS}
                    """,
                    (
                        email,
                        password_hash,
                        int(is_admin),
                        int(is_active),
                        int(email_verified),
                        display_name,
                        int(two_factor_enabled),
                    ),
                )
            else:
                cursor = await db.execute(
                    f"""
                    UPDATE users
                    SET password_hash = ?,
                        is_admin = ?,
                        is_active = ?,
                        email_verified = ?,
                        display_name = ?,
                        avatar_path = NULL,
                        pending_email = NULL,
                        deleted_at = NULL,
                        links_expire_at = NULL,
                        two_factor_enabled = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    RETURNING {USER_COLUMNS}
                    """,
                    (
                        password_hash,
                        int(is_admin),
                        int(is_active),
                        int(email_verified),
                        display_name,
                        int(two_factor_enabled),
                        existing.id,
                    ),
                )
            user = self._to_user(await cursor.fetchone())
            assert user is not None
            await db.execute(
                "INSERT OR IGNORE INTO preferences (user_id) VALUES (?)",
                (user.id,),
            )
            await db.commit()
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

    async def update_user_governance_fields(
        self, user_id: int, *, role: str | None, is_active: bool | None
    ) -> UserRecord | None:
        assignments = ["updated_at = CURRENT_TIMESTAMP"]
        params: list[object] = []
        if role is not None:
            assignments.extend(["role = ?", "is_admin = ?"])
            params.extend([role, int(role == "admin")])
        if is_active is not None:
            assignments.append("is_active = ?")
            params.append(int(is_active))
        params.append(user_id)
        async with self._connect() as db:
            cursor = await db.execute(
                f"UPDATE users SET {', '.join(assignments)} WHERE id = ? RETURNING {USER_COLUMNS}",
                params,
            )
            user = self._to_user(await cursor.fetchone())
            if user is not None and is_active is False:
                await db.execute(
                    "UPDATE refresh_tokens SET revoked_at = COALESCE(revoked_at, CURRENT_TIMESTAMP) WHERE user_id = ?",
                    (user_id,),
                )
            await db.commit()
            return user

    async def list_users_governance(
        self,
        *,
        q: str | None,
        role: str | None,
        is_active: bool | None,
        email_verified: bool | None,
        deletion_state: str | None,
        registered_from: str | None,
        registered_to: str | None,
        sort: str,
        limit: int,
        offset: int,
    ) -> tuple[list[UserRecord], int]:
        clauses: list[str] = []
        params: list[object] = []
        if q:
            clauses.append("email LIKE ?")
            params.append(f"%{q.strip()}%")
        for column, value in (
            ("role", role),
            ("is_active", None if is_active is None else int(is_active)),
            ("email_verified", None if email_verified is None else int(email_verified)),
        ):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if deletion_state == "requested":
            clauses.append("deletion_requested_at IS NOT NULL AND anonymized_at IS NULL")
        elif deletion_state == "anonymized":
            clauses.append("anonymized_at IS NOT NULL")
        elif deletion_state == "none":
            clauses.append("deletion_requested_at IS NULL AND anonymized_at IS NULL")
        if registered_from:
            clauses.append("created_at >= ?")
            params.append(registered_from)
        if registered_to:
            clauses.append("created_at <= ?")
            params.append(registered_to)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        ordering = {
            "created_at_desc": "created_at DESC, id DESC",
            "created_at_asc": "created_at ASC, id ASC",
            "email_asc": "email ASC",
            "email_desc": "email DESC",
        }[sort]
        async with self._connect() as db:
            cursor = await db.execute(f"SELECT COUNT(*) FROM users {where}", params)
            total = (await cursor.fetchone())[0]
            cursor = await db.execute(
                f"SELECT {USER_COLUMNS} FROM users {where} ORDER BY {ordering} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
            return [u for row in await cursor.fetchall() if (u := self._to_user(row))], total

    async def request_account_deletion(self, user_id: int) -> UserRecord | None:
        scheduled = (datetime.now(UTC) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                f"""UPDATE users SET is_active=0, deletion_requested_at=CURRENT_TIMESTAMP,
                deletion_scheduled_for=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND anonymized_at IS NULL RETURNING {USER_COLUMNS}""",
                (scheduled, user_id),
            )
            user = self._to_user(await cursor.fetchone())
            if user is None:
                await db.rollback()
                return None
            await db.execute(
                "UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,CURRENT_TIMESTAMP) WHERE user_id=?",
                (user_id,),
            )
            await db.execute(
                "UPDATE links SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE owner_id=?",
                (user_id,),
            )
            await db.commit()
            return user

    async def cancel_account_deletion(self, user_id: int) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""UPDATE users SET is_active=1, deletion_requested_at=NULL,
                deletion_scheduled_for=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=? AND deletion_scheduled_for>CURRENT_TIMESTAMP
                AND anonymized_at IS NULL RETURNING {USER_COLUMNS}""",
                (user_id,),
            )
            user = self._to_user(await cursor.fetchone())
            if user:
                await db.execute(
                    "UPDATE links SET is_active=1, updated_at=CURRENT_TIMESTAMP WHERE owner_id=?",
                    (user_id,),
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
                DO UPDATE SET count = analytics_hourly.count + 1
                """,
                (link_id, hour),
            )
            await db.execute(
                """
                INSERT INTO analytics_daily (link_id, bucket_start, count)
                VALUES (?, ?, 1)
                ON CONFLICT(link_id, bucket_start)
                DO UPDATE SET count = analytics_daily.count + 1
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

    async def clear_seed_user_data(self, user_id: int) -> None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                """
                DELETE FROM analytics_hourly
                WHERE link_id IN (SELECT id FROM links WHERE owner_id = ?)
                """,
                (user_id,),
            )
            await db.execute(
                """
                DELETE FROM analytics_daily
                WHERE link_id IN (SELECT id FROM links WHERE owner_id = ?)
                """,
                (user_id,),
            )
            await db.execute("DELETE FROM links WHERE owner_id = ?", (user_id,))
            await db.execute("DELETE FROM folders WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM action_tokens WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM refresh_tokens WHERE user_id = ?", (user_id,))
            await db.execute("DELETE FROM two_factor_challenges WHERE user_id = ?", (user_id,))
            await db.execute(
                """
                UPDATE preferences
                SET theme = 'light',
                    language = 'ru',
                    email_notifications = 1,
                    system_notifications = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
                """,
                (user_id,),
            )
            await db.commit()

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
            cursor = await db.execute(
                "SELECT 1 FROM folders WHERE id = ? AND user_id = ? LIMIT 1",
                (folder_id, user_id),
            )
            if await cursor.fetchone() is None:
                await db.rollback()
                return False
            await db.execute(
                """
                UPDATE links
                SET folder_id = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE folder_id = ? AND owner_id = ?
                """,
                (folder_id, user_id),
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

    async def update_avatar(
        self,
        user_id: int,
        *,
        avatar_path: str,
        avatar_content_type: str,
        avatar_data: bytes,
    ) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET avatar_path = ?, avatar_content_type = ?, avatar_data = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                RETURNING {USER_COLUMNS}
                """,
                (avatar_path, avatar_content_type, avatar_data, user_id),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

    async def clear_avatar(self, user_id: int) -> UserRecord | None:
        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                UPDATE users
                SET avatar_path = NULL, avatar_content_type = NULL, avatar_data = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                RETURNING {USER_COLUMNS}
                """,
                (user_id,),
            )
            user = self._to_user(await cursor.fetchone())
            await db.commit()
            return user

    async def get_avatar(self, avatar_path: str) -> tuple[bytes, str] | None:
        async with self._connect() as db:
            cursor = await db.execute(
                "SELECT avatar_data, avatar_content_type FROM users "
                "WHERE avatar_path = ? AND avatar_data IS NOT NULL LIMIT 1",
                (avatar_path,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return bytes(row[0]), row[1]

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

    async def anonymize_account(self, user_id: int) -> UserRecord | None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                f"""UPDATE users SET is_active=0, email=?, password_hash=?, display_name=NULL,
                avatar_path=NULL, pending_email=NULL, email_verified=0, two_factor_enabled=0,
                deleted_at=COALESCE(deleted_at,CURRENT_TIMESTAMP), anonymized_at=CURRENT_TIMESTAMP,
                deletion_scheduled_for=NULL, updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND anonymized_at IS NULL RETURNING {USER_COLUMNS}""",
                (f"deleted-user-{user_id}@deleted.local", f"anonymized:{user_id}", user_id),
            )
            user = self._to_user(await cursor.fetchone())
            if user is None:
                await db.rollback()
                return None
            await db.execute(
                "UPDATE refresh_tokens SET revoked_at=COALESCE(revoked_at,CURRENT_TIMESTAMP) WHERE user_id=?",
                (user_id,),
            )
            await db.execute(
                "UPDATE links SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE owner_id=?",
                (user_id,),
            )
            await db.commit()
            return user

    async def create_report(
        self, *, email: str, shortcode: str, category: str, comment: str
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO reports (reporter_email, shortcode, category, comment) VALUES (?, ?, ?, ?)",
                (email, shortcode, category, comment),
            )
            await db.commit()

    async def list_reports(
        self, *, report_status: str | None, category: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, object]], int]:
        clauses = []
        params = []
        if report_status:
            clauses.append("status=?")
            params.append(report_status)
        if category:
            clauses.append("category=?")
            params.append(category)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self._connect() as db:
            total = (
                await (await db.execute(f"SELECT COUNT(*) FROM reports {where}", params)).fetchone()
            )[0]
            rows = await (
                await db.execute(
                    f"SELECT id,reporter_email,shortcode,category,comment,status,resolution_comment,resolved_by,resolved_at,created_at,updated_at FROM reports {where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                    [*params, limit, offset],
                )
            ).fetchall()
            keys = (
                "id",
                "reporter_email",
                "shortcode",
                "category",
                "comment",
                "status",
                "resolution_comment",
                "resolved_by",
                "resolved_at",
                "created_at",
                "updated_at",
            )
            return [dict(zip(keys, row, strict=True)) for row in rows], total

    async def get_report(self, report_id: int) -> dict[str, object] | None:
        rows, _ = await self.list_reports(report_status=None, category=None, limit=100000, offset=0)
        return next((row for row in rows if row["id"] == report_id), None)

    async def resolve_report(
        self, report_id: int, *, report_status: str, comment: str | None, actor_id: int
    ) -> dict[str, object] | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """UPDATE reports SET status=?,resolution_comment=?,resolved_by=?,resolved_at=CASE WHEN ? IN ('resolved','rejected') THEN CURRENT_TIMESTAMP ELSE NULL END,updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING id,reporter_email,shortcode,category,comment,status,resolution_comment,resolved_by,resolved_at,created_at,updated_at""",
                (report_status, comment, actor_id, report_status, report_id),
            )
            row = await cursor.fetchone()
            await db.commit()
            if row is None:
                return None
            keys = (
                "id",
                "reporter_email",
                "shortcode",
                "category",
                "comment",
                "status",
                "resolution_comment",
                "resolved_by",
                "resolved_at",
                "created_at",
                "updated_at",
            )
            return dict(zip(keys, row, strict=True))

    async def add_moderation_action(
        self, *, shortcode: str, actor_id: int, action: str, category: str | None, comment: str
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO link_moderation_actions (shortcode,actor_id,action,category,comment) VALUES (?,?,?,?,?)",
                (shortcode, actor_id, action, category, comment),
            )
            await db.commit()

    async def get_link_history(self, shortcode: str) -> list[dict[str, object]]:
        async with self._connect() as db:
            rows = await (
                await db.execute(
                    "SELECT id,shortcode,actor_id,action,category,comment,created_at FROM link_moderation_actions WHERE shortcode=? ORDER BY created_at DESC,id DESC",
                    (shortcode,),
                )
            ).fetchall()
            keys = ("id", "shortcode", "actor_id", "action", "category", "comment", "created_at")
            return [dict(zip(keys, row, strict=True)) for row in rows]

    async def add_audit_log(
        self,
        *,
        actor_id: int | None,
        actor_role: str | None,
        action: str,
        object_type: str,
        object_id: str,
        old_value: dict[str, object] | None = None,
        new_value: dict[str, object] | None = None,
        route: str | None = None,
        ip_hash: str | None = None,
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO audit_log (actor_id,actor_role,action,object_type,object_id,old_value_json,new_value_json,route,ip_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    actor_id,
                    actor_role,
                    action,
                    object_type,
                    object_id,
                    json.dumps(old_value) if old_value else None,
                    json.dumps(new_value) if new_value else None,
                    route,
                    ip_hash,
                ),
            )
            await db.commit()

    async def list_audit_log(
        self,
        *,
        actor_id: int | None,
        action: str | None,
        object_type: str | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, object]], int]:
        clauses = []
        params = []
        for col, val in (("actor_id", actor_id), ("action", action), ("object_type", object_type)):
            if val is not None:
                clauses.append(f"{col}=?")
                params.append(val)
        if date_from:
            clauses.append("created_at>=?")
            params.append(date_from)
        if date_to:
            clauses.append("created_at<=?")
            params.append(date_to)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self._connect() as db:
            total = (
                await (
                    await db.execute(f"SELECT COUNT(*) FROM audit_log {where}", params)
                ).fetchone()
            )[0]
            rows = await (
                await db.execute(
                    f"SELECT id,actor_id,actor_role,action,object_type,object_id,old_value_json,new_value_json,route,created_at FROM audit_log {where} ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                    [*params, limit, offset],
                )
            ).fetchall()
            return [
                {
                    "id": r[0],
                    "actor_id": r[1],
                    "actor_role": r[2],
                    "action": r[3],
                    "object_type": r[4],
                    "object_id": r[5],
                    "old_value": json.loads(r[6]) if r[6] else None,
                    "new_value": json.loads(r[7]) if r[7] else None,
                    "route": r[8],
                    "created_at": r[9],
                }
                for r in rows
            ], total

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

    async def replace_link_analytics(
        self,
        link_id: int,
        *,
        access_count: int,
        last_accessed_at: str | None,
        hourly_counts: dict[str, int],
        daily_counts: dict[str, int],
    ) -> None:
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            await db.execute("DELETE FROM analytics_hourly WHERE link_id = ?", (link_id,))
            await db.execute("DELETE FROM analytics_daily WHERE link_id = ?", (link_id,))
            await db.execute(
                """
                UPDATE links
                SET access_count = ?,
                    last_accessed_at = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (access_count, last_accessed_at, link_id),
            )
            for bucket_start, count in hourly_counts.items():
                await db.execute(
                    """
                    INSERT INTO analytics_hourly (link_id, bucket_start, count)
                    VALUES (?, ?, ?)
                    """,
                    (link_id, bucket_start, count),
                )
            for bucket_start, count in daily_counts.items():
                await db.execute(
                    """
                    INSERT INTO analytics_daily (link_id, bucket_start, count)
                    VALUES (?, ?, ?)
                    """,
                    (link_id, bucket_start, count),
                )
            await db.commit()

    async def ping(self) -> None:
        async with self._connect() as db:
            await db.execute("SELECT 1")

    def _connect(self) -> aiosqlite.Connection:
        if self.database_url:
            from app.db.sql.postgres import connect

            return connect(self.database_url)
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
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','support','moderator','admin')),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                email_verified INTEGER NOT NULL DEFAULT 0 CHECK (email_verified IN (0, 1)),
                display_name TEXT,
                avatar_path TEXT,
                avatar_content_type TEXT,
                avatar_data BYTEA,
                pending_email TEXT UNIQUE COLLATE NOCASE,
                deleted_at TEXT,
                links_expire_at TEXT,
                deletion_requested_at TEXT,
                deletion_scheduled_for TEXT,
                anonymized_at TEXT,
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
            "is_admin": "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "is_active": "ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1",
            "email_verified": "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0",
            "display_name": "ALTER TABLE users ADD COLUMN display_name TEXT",
            "avatar_path": "ALTER TABLE users ADD COLUMN avatar_path TEXT",
            "avatar_content_type": "ALTER TABLE users ADD COLUMN avatar_content_type TEXT",
            "avatar_data": "ALTER TABLE users ADD COLUMN avatar_data BYTEA",
            "pending_email": "ALTER TABLE users ADD COLUMN pending_email TEXT",
            "deleted_at": "ALTER TABLE users ADD COLUMN deleted_at TEXT",
            "links_expire_at": "ALTER TABLE users ADD COLUMN links_expire_at TEXT",
            "two_factor_enabled": """
                ALTER TABLE users
                ADD COLUMN two_factor_enabled INTEGER NOT NULL DEFAULT 0
                CHECK (two_factor_enabled IN (0, 1))
            """,
            "role": "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'",
            "deletion_requested_at": "ALTER TABLE users ADD COLUMN deletion_requested_at TEXT",
            "deletion_scheduled_for": "ALTER TABLE users ADD COLUMN deletion_scheduled_for TEXT",
            "anonymized_at": "ALTER TABLE users ADD COLUMN anonymized_at TEXT",
        }
        for key, statement in additions.items():
            if key not in columns:
                await db.execute(statement)
        await db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_pending_email ON users(pending_email)"
        )
        await db.execute(
            "UPDATE users SET role = CASE WHEN is_admin = 1 THEN 'admin' ELSE 'user' END WHERE role IS NULL OR role NOT IN ('user','support','moderator','admin')"
        )

    async def _ensure_governance_schema(self, db: aiosqlite.Connection) -> None:
        await db.execute("""CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, reporter_email TEXT NOT NULL, shortcode TEXT NOT NULL,
            category TEXT NOT NULL, comment TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
            resolution_comment TEXT, resolved_by INTEGER REFERENCES users(id), resolved_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS link_moderation_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, shortcode TEXT NOT NULL, actor_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL, category TEXT, comment TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER REFERENCES users(id), actor_role TEXT,
            action TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL, old_value_json TEXT,
            new_value_json TEXT, route TEXT, ip_hash TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS retention_settings (
            id INTEGER PRIMARY KEY CHECK(id=1), audit_log_days INTEGER NOT NULL DEFAULT 365,
            report_days INTEGER NOT NULL DEFAULT 365, admin_access_attempt_days INTEGER NOT NULL DEFAULT 90,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS admin_access_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id INTEGER REFERENCES users(id), route TEXT NOT NULL,
            reason TEXT NOT NULL, ip_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        await db.execute("INSERT OR IGNORE INTO retention_settings (id) VALUES (1)")
        await db.execute(
            "CREATE INDEX IF NOT EXISTS ix_reports_status_created ON reports(status, created_at DESC)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS ix_audit_log_created ON audit_log(created_at DESC)"
        )

    async def get_retention_settings(self) -> dict[str, object]:
        async with self._connect() as db:
            row = await (
                await db.execute(
                    "SELECT audit_log_days,report_days,admin_access_attempt_days,updated_at FROM retention_settings WHERE id=1"
                )
            ).fetchone()
            assert row is not None
            return dict(
                zip(
                    ("audit_log_days", "report_days", "admin_access_attempt_days", "updated_at"),
                    row,
                    strict=True,
                )
            )

    async def update_retention_settings(
        self, *, audit_log_days: int, report_days: int, admin_access_attempt_days: int
    ) -> dict[str, object]:
        async with self._connect() as db:
            row = await (
                await db.execute(
                    "UPDATE retention_settings SET audit_log_days=?,report_days=?,admin_access_attempt_days=?,updated_at=CURRENT_TIMESTAMP WHERE id=1 RETURNING audit_log_days,report_days,admin_access_attempt_days,updated_at",
                    (audit_log_days, report_days, admin_access_attempt_days),
                )
            ).fetchone()
            await db.commit()
            assert row is not None
            return dict(
                zip(
                    ("audit_log_days", "report_days", "admin_access_attempt_days", "updated_at"),
                    row,
                    strict=True,
                )
            )

    async def get_dashboard(self) -> dict[str, object]:
        async with self._connect() as db:
            users = (
                await (
                    await db.execute("SELECT COUNT(*) FROM users WHERE anonymized_at IS NULL")
                ).fetchone()
            )[0]
            links = await (
                await db.execute(
                    "SELECT COUNT(*),SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) FROM links"
                )
            ).fetchone()
            reports = await (
                await db.execute(
                    "SELECT COUNT(*),SUM(CASE WHEN status IN ('open','in_review') THEN 1 ELSE 0 END) FROM reports"
                )
            ).fetchone()
            recent = await (
                await db.execute(
                    "SELECT id,actor_id,actor_role,action,object_type,object_id,created_at FROM audit_log ORDER BY created_at DESC,id DESC LIMIT 10"
                )
            ).fetchall()
            return {
                "users_total": users,
                "links_total": links[0],
                "links_active": links[1] or 0,
                "links_disabled": links[0] - (links[1] or 0),
                "reports_total": reports[0],
                "reports_open": reports[1] or 0,
                "recent_actions": [
                    dict(
                        zip(
                            (
                                "id",
                                "actor_id",
                                "actor_role",
                                "action",
                                "object_type",
                                "object_id",
                                "created_at",
                            ),
                            r,
                            strict=True,
                        )
                    )
                    for r in recent
                ],
            }

    async def record_admin_access_attempt(
        self, *, actor_id: int | None, route: str, reason: str, ip_hash: str
    ) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO admin_access_attempts(actor_id,route,reason,ip_hash) VALUES(?,?,?,?)",
                (actor_id, route, reason, ip_hash),
            )
            await db.commit()

    async def run_governance_housekeeping(self) -> None:
        async with self._connect() as db:
            rows = await (
                await db.execute(
                    "SELECT id FROM users WHERE deletion_scheduled_for <= CURRENT_TIMESTAMP AND anonymized_at IS NULL"
                )
            ).fetchall()
            await db.commit()
        for row in rows:
            await self.anonymize_account(row[0])
        settings = await self.get_retention_settings()
        async with self._connect() as db:
            for table, column, days in (
                ("audit_log", "created_at", settings["audit_log_days"]),
                ("reports", "created_at", settings["report_days"]),
                ("admin_access_attempts", "created_at", settings["admin_access_attempt_days"]),
            ):
                await db.execute(
                    f"DELETE FROM {table} WHERE {column} < datetime('now', ?)", (f"-{days} days",)
                )
            await db.commit()

    async def _ensure_link_columns(self, db: aiosqlite.Connection) -> None:
        columns = await self._table_columns(db, "links")
        additions = {
            "folder_id": "ALTER TABLE links ADD COLUMN folder_id INTEGER REFERENCES folders(id)",
            "expires_at": "ALTER TABLE links ADD COLUMN expires_at TEXT",
        }
        for key, statement in additions.items():
            if key not in columns:
                await db.execute(statement)

    async def _ensure_action_token_columns(self, db: aiosqlite.Connection) -> None:
        columns = await self._table_columns(db, "action_tokens")
        if "payload_json" not in columns:
            await db.execute(
                "ALTER TABLE action_tokens ADD COLUMN payload_json TEXT NOT NULL DEFAULT '{}'"
            )

    async def _ensure_admin_settings(self, db: aiosqlite.Connection) -> None:
        await db.execute(
            """
            INSERT OR IGNORE INTO admin_settings (id, user_link_retention_days)
            VALUES (1, ?)
            """,
            (self.user_link_retention_days_default,),
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
            raw_series = []
            for row in await cursor.fetchall():
                point_time = datetime.fromisoformat(row[0])
                if point_time.tzinfo is None:
                    point_time = point_time.replace(tzinfo=UTC)
                raw_series.append((point_time, row[1]))
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
            role=row[12],
            deletion_requested_at=row[13],
            deletion_scheduled_for=row[14],
            anonymized_at=row[15],
            created_at=row[16],
            updated_at=row[17],
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
