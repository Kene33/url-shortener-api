import asyncio
import sys

from app.core.config import get_settings
from app.db.sql.crud import SQLClient
from app.services.demo_seed import DemoSeedError, DemoSeedService


async def seed_demo() -> None:
    settings = get_settings()
    if not settings.demo_seed_password:
        raise DemoSeedError("DEMO_SEED_PASSWORD must be set")
    database = SQLClient(
        settings.database_path,
        user_link_retention_days_default=settings.user_link_retention_days_default,
    )
    result = await DemoSeedService(database, settings).seed(settings.demo_seed_password)
    print("Demo seed complete.")
    for account in result.accounts:
        role = "admin" if account.is_admin else "user"
        print(f"{account.email} [{role}]")
        print(f"  folders: {', '.join(account.folders)}")
        print(f"  links: {', '.join(account.shortcodes)}")


def main() -> int:
    try:
        asyncio.run(seed_demo())
    except DemoSeedError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
