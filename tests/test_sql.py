import asyncio
import sqlite3

import pytest

from app.db.sql.crud import SQLClient


@pytest.mark.asyncio
async def test_access_count_increment_is_atomic_under_concurrency(tmp_path):
    database = SQLClient(str(tmp_path / "atomic-access-count.db"))
    await database.create_database()
    await database.insert_guest_link(
        url="https://example.com/atomic",
        normalized_url="https://example.com/atomic",
        shortcode="atomic01",
    )

    increments = 25
    await asyncio.gather(
        *(database.increment_access_count("atomic01") for _ in range(increments))
    )
    stored = await database.get_link_by_shortcode("atomic01")

    assert stored is not None
    assert stored.access_count == increments
    assert stored.last_accessed_at is not None


@pytest.mark.asyncio
async def test_startup_migrates_legacy_camelcase_links_schema(tmp_path, app_factory):
    database_path = tmp_path / "legacy-links.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                shortcode TEXT UNIQUE,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                accessCount INTEGER DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            INSERT INTO links (url, shortcode, createdAt, updatedAt, accessCount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "https://example.com/legacy",
                "legacy01",
                "2025-01-02 03:04:05",
                "2025-01-03 04:05:06",
                7,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLClient(str(database_path))
    async with app_factory(database=database):
        migrated = await database.get_link_by_shortcode("legacy01")

    assert migrated is not None
    assert migrated.url == "https://example.com/legacy"
    assert migrated.normalized_url == "https://example.com/legacy"
    assert migrated.is_active is True
    assert migrated.access_count == 7
    assert migrated.created_at == "2025-01-02 03:04:05"
    assert migrated.updated_at == "2025-01-03 04:05:06"


@pytest.mark.asyncio
async def test_legacy_duplicate_urls_keep_all_shortcodes_and_one_canonical_link(
    tmp_path,
    app_factory,
):
    database_path = tmp_path / "legacy-duplicates.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                shortcode TEXT UNIQUE,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                accessCount INTEGER DEFAULT 0
            )
            """
        )
        connection.executemany(
            "INSERT INTO links (url, shortcode) VALUES (?, ?)",
            [
                ("https://Example.COM", "first001"),
                ("https://example.com/", "second02"),
            ],
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLClient(str(database_path))
    async with app_factory(database=database) as harness:
        first = await database.get_link_by_shortcode("first001")
        second = await database.get_link_by_shortcode("second02")
        canonical = await database.get_guest_link_by_url("https://example.com/")
        first_redirect = await harness.client.get("/first001")
        second_redirect = await harness.client.get("/second02")
        duplicate = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/"},
        )

    assert first is not None and first.is_canonical is True
    assert second is not None and second.is_canonical is False
    assert canonical is not None and canonical.shortcode == "first001"
    assert first_redirect.status_code == 307
    assert second_redirect.status_code == 307
    assert duplicate.status_code == 200
    assert duplicate.json()["shortcode"] == "first001"


@pytest.mark.asyncio
async def test_startup_upgrades_v2_schema_with_canonical_column(tmp_path, app_factory):
    database_path = tmp_path / "v2-links.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                normalized_url TEXT NOT NULL,
                shortcode TEXT NOT NULL UNIQUE,
                owner_id INTEGER,
                label TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX ux_guest_link_url
            ON links(normalized_url)
            WHERE owner_id IS NULL
            """
        )
        connection.execute(
            """
            INSERT INTO links (url, normalized_url, shortcode)
            VALUES ('https://example.com/v2', 'https://example.com/v2', 'v2code01')
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = SQLClient(str(database_path))
    async with app_factory(database=database):
        connection = sqlite3.connect(database_path)
        try:
            columns = connection.execute("PRAGMA table_info(links)").fetchall()
        finally:
            connection.close()
        migrated = await database.get_link_by_shortcode("v2code01")

    assert "is_canonical" in {column[1] for column in columns}
    assert migrated is not None and migrated.is_canonical is True


@pytest.mark.asyncio
async def test_startup_creates_account_and_session_tables(tmp_path):
    database_path = tmp_path / "account-schema.db"
    database = SQLClient(str(database_path))

    await database.create_database()

    connection = sqlite3.connect(database_path)
    try:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    finally:
        connection.close()

    assert {"links", "users", "refresh_tokens", "action_tokens"} <= tables
    assert user_version == 4
