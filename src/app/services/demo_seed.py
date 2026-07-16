from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.config import Settings
from app.core.security import hash_password
from app.db.sql.crud import FolderRecord, SQLClient, UserRecord
from app.utils.urls import normalize_url


class DemoSeedError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DemoSeedAccount:
    email: str
    is_admin: bool
    folders: tuple[str, ...]
    shortcodes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DemoSeedResult:
    accounts: tuple[DemoSeedAccount, ...]


@dataclass(frozen=True, slots=True)
class DemoLinkSpec:
    shortcode: str
    url: str
    label: str
    folder: str | None
    is_active: bool
    hourly_counts: tuple[int, ...]
    daily_counts: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class DemoAccountSpec:
    email: str
    display_name: str
    is_admin: bool
    preferences: tuple[str, str, bool, bool]
    folders: tuple[tuple[str, str], ...]
    links: tuple[DemoLinkSpec, ...]
    notifications: tuple[tuple[str, str, dict[str, object]], ...]


DEMO_ACCOUNTS: tuple[DemoAccountSpec, ...] = (
    DemoAccountSpec(
        email="demo-admin@example.com",
        display_name="Demo Admin",
        is_admin=True,
        preferences=("dark", "en", True, True),
        folders=(("Moderation", "violet"), ("Operations", "orange")),
        links=(
            DemoLinkSpec(
                shortcode="DMOADM01",
                url="https://status.openai.com/",
                label="Status page",
                folder="Operations",
                is_active=True,
                hourly_counts=(9, 6, 4, 2),
                daily_counts=(24, 18, 12, 9, 6),
            ),
            DemoLinkSpec(
                shortcode="DMOADM02",
                url="https://platform.openai.com/docs",
                label="Admin docs",
                folder="Moderation",
                is_active=False,
                hourly_counts=(2, 1),
                daily_counts=(8, 5, 4),
            ),
        ),
        notifications=(
            ("system", "seed_ready", {"message": "Demo admin account is ready"}),
            ("security", "password_changed", {}),
        ),
    ),
    DemoAccountSpec(
        email="demo-user@example.com",
        display_name="Demo User",
        is_admin=False,
        preferences=("light", "en", True, True),
        folders=(("Campaigns", "cyan"), ("Archive", "gray")),
        links=(
            DemoLinkSpec(
                shortcode="DMOUSR01",
                url="https://example.com/summer-sale",
                label="Summer sale",
                folder="Campaigns",
                is_active=True,
                hourly_counts=(14, 10, 8, 5, 3),
                daily_counts=(40, 32, 27, 22, 15, 11, 7),
            ),
            DemoLinkSpec(
                shortcode="DMOUSR02",
                url="https://example.com/product-launch",
                label="Product launch",
                folder="Campaigns",
                is_active=True,
                hourly_counts=(11, 7, 5),
                daily_counts=(26, 19, 14, 10),
            ),
            DemoLinkSpec(
                shortcode="DMOUSR03",
                url="https://example.com/old-promo",
                label="Old promo",
                folder="Archive",
                is_active=False,
                hourly_counts=(0,),
                daily_counts=(9, 7, 5),
            ),
        ),
        notifications=(
            ("system", "seed_ready", {"message": "Demo user account is ready"}),
            (
                "system",
                "campaign_snapshot",
                {"active_links": 2, "disabled_links": 1},
            ),
        ),
    ),
)


class DemoSeedService:
    def __init__(self, database: SQLClient, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    async def seed(self, password: str) -> DemoSeedResult:
        if self.settings.environment.lower() == "production":
            raise DemoSeedError("Demo seed refuses to run in production")
        if not password.strip():
            raise DemoSeedError("DEMO_SEED_PASSWORD must be set")

        await self.database.create_database()
        password_hash = hash_password(password)
        accounts: list[DemoSeedAccount] = []
        for spec in DEMO_ACCOUNTS:
            user = await self.database.upsert_seed_user(
                spec.email,
                password_hash,
                is_admin=spec.is_admin,
                display_name=spec.display_name,
            )
            await self.database.clear_seed_user_data(user.id)
            await self.database.update_preferences(
                user.id,
                theme=spec.preferences[0],
                language=spec.preferences[1],
                email_notifications=spec.preferences[2],
                system_notifications=spec.preferences[3],
            )
            accounts.append(await self._seed_account(user, spec))
        return DemoSeedResult(accounts=tuple(accounts))

    async def _seed_account(self, user: UserRecord, spec: DemoAccountSpec) -> DemoSeedAccount:
        folders: dict[str, FolderRecord] = {}
        for name, color in spec.folders:
            folders[name] = await self.database.create_folder(user.id, name, color)

        shortcodes: list[str] = []
        for link_spec in spec.links:
            existing = await self.database.get_link_by_shortcode(link_spec.shortcode)
            if existing is not None and existing.owner_id != user.id:
                raise DemoSeedError(f"Shortcode {link_spec.shortcode} is already in use")
            link, _ = await self.database.get_or_create_user_link(
                url=link_spec.url,
                normalized_url=normalize_url(link_spec.url),
                shortcode=link_spec.shortcode,
                owner_id=user.id,
                label=link_spec.label,
                folder_id=folders[link_spec.folder].id if link_spec.folder else None,
                reuse=False,
            )
            if not link_spec.is_active:
                updated = await self.database.update_link_metadata(
                    link.shortcode,
                    owner_id=user.id,
                    label=link.label,
                    set_label=False,
                    is_active=False,
                    set_active=True,
                    folder_id=link.folder_id,
                    set_folder=False,
                )
                assert updated is not None
                link = updated
            await self.database.replace_link_analytics(
                link.id,
                access_count=sum(link_spec.daily_counts),
                last_accessed_at=self._last_accessed_at(link_spec.hourly_counts),
                hourly_counts=self._hourly_counts(link_spec.hourly_counts),
                daily_counts=self._daily_counts(link_spec.daily_counts),
            )
            shortcodes.append(link.shortcode)

        created_notifications = []
        for kind, key, payload in spec.notifications:
            created_notifications.append(
                await self.database.create_notification(
                    user.id,
                    kind=kind,
                    key=key,
                    payload=payload,
                )
            )
        if created_notifications:
            await self.database.mark_notification_read(created_notifications[0].id, user.id)

        return DemoSeedAccount(
            email=user.email,
            is_admin=user.is_admin,
            folders=tuple(name for name, _ in spec.folders),
            shortcodes=tuple(shortcodes),
        )

    @staticmethod
    def _hourly_counts(counts: tuple[int, ...]) -> dict[str, int]:
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        return {
            (now - timedelta(hours=index + 1)).strftime("%Y-%m-%d %H:%M:%S"): count
            for index, count in enumerate(counts)
            if count > 0
        }

    @staticmethod
    def _daily_counts(counts: tuple[int, ...]) -> dict[str, int]:
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            (today - timedelta(days=index + 1)).strftime("%Y-%m-%d %H:%M:%S"): count
            for index, count in enumerate(counts)
            if count > 0
        }

    @staticmethod
    def _last_accessed_at(counts: tuple[int, ...]) -> str | None:
        for index, count in enumerate(counts):
            if count > 0:
                value = datetime.now(UTC).replace(minute=15, second=0, microsecond=0)
                value = value - timedelta(hours=index + 1)
                return value.strftime("%Y-%m-%d %H:%M:%S")
        return None
