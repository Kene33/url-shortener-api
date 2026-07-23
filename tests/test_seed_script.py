import pytest

from app.core.config import Settings
from app.db.sql.crud import SQLClient
from app.services.demo_seed import DemoSeedError, DemoSeedService
@pytest.mark.asyncio
async def test_demo_seed_requires_password(tmp_path):
    settings = Settings(
        public_base_url="https://sho.rt",
        database_path=str(tmp_path / "demo.db"),
        database_url="postgresql://user:password@example.com:5432/app",
        redis_url="rediss://default:password@example.com:6379",
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
        database_url="postgresql://user:password@example.com:5432/app",
        redis_url="rediss://default:password@example.com:6379",
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
