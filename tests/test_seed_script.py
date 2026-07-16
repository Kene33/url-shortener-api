from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import Settings
from app.db.sql.crud import SQLClient
from app.services.demo_seed import DemoSeedError, DemoSeedService
from scripts import seed_db


@pytest.mark.asyncio
async def test_seed_skips_existing_urls_and_only_inserts_missing_ones(monkeypatch):
    fake_client = AsyncMock()
    fake_client.create_database = AsyncMock()
    fake_client.get_guest_link_by_url = AsyncMock(
        side_effect=[
            object(),
            None,
            object(),
            *([None] * (len(seed_db.TEST_LINKS) - 3)),
        ],
    )
    fake_client.insert_guest_link = AsyncMock()
    sql_client = Mock(return_value=fake_client)

    monkeypatch.setattr(seed_db, "SQLClient", sql_client)

    await seed_db.seed("/tmp/seed-links.db")

    sql_client.assert_called_once_with("/tmp/seed-links.db")
    fake_client.create_database.assert_awaited_once()
    assert fake_client.get_guest_link_by_url.await_count == len(seed_db.TEST_LINKS)
    assert fake_client.insert_guest_link.await_count == len(seed_db.TEST_LINKS) - 2
    fake_client.insert_guest_link.assert_any_await(
        "https://github.com",
        "https://github.com",
        "ghub2",
    )


@pytest.mark.asyncio
async def test_demo_seed_requires_password(tmp_path):
    settings = Settings(
        public_base_url="https://sho.rt",
        database_path=str(tmp_path / "demo.db"),
        redis_url="redis://unused.invalid:6379/0",
        cors_origins=[],
        auth_secret_key="test-secret-key-with-at-least-24-characters",
    )
    service = DemoSeedService(SQLClient(settings.database_path), settings)

    with pytest.raises(DemoSeedError, match="DEMO_SEED_PASSWORD must be set"):
        await service.seed("")


@pytest.mark.asyncio
async def test_demo_seed_refuses_production(tmp_path):
    settings = Settings(
        environment="production",
        public_base_url="https://sho.rt",
        database_path=str(tmp_path / "demo.db"),
        redis_url="redis://unused.invalid:6379/0",
        cors_origins=[],
        auth_secret_key="production-secret-key-with-at-least-24-chars",
        demo_seed_password="DemoPass123!",
        refresh_cookie_secure=True,
    )
    service = DemoSeedService(SQLClient(settings.database_path), settings)

    with pytest.raises(DemoSeedError, match="refuses to run in production"):
        await service.seed(settings.demo_seed_password or "")


@pytest.mark.asyncio
async def test_demo_seed_creates_verified_admin_and_user(tmp_path):
    settings = Settings(
        public_base_url="https://sho.rt",
        database_path=str(tmp_path / "demo.db"),
        redis_url="redis://unused.invalid:6379/0",
        cors_origins=[],
        auth_secret_key="test-secret-key-with-at-least-24-characters",
        demo_seed_password="DemoPass123!",
    )
    database = SQLClient(settings.database_path)

    result = await DemoSeedService(database, settings).seed(settings.demo_seed_password or "")

    admin = await database.get_user_by_email("demo-admin@example.com")
    user = await database.get_user_by_email("demo-user@example.com")
    assert admin is not None and admin.is_admin is True and admin.email_verified is True
    assert user is not None and user.is_admin is False and user.email_verified is True
    assert len(result.accounts) == 2
    folders = await database.list_folders(user.id)
    assert {folder.name for folder, _ in folders} == {"Campaigns", "Archive"}
