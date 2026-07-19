import logging
import sqlite3
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.core.security import hash_token
from app.db.redis.links import LinkCache, RedisClient
from app.db.sql.crud import SQLClient
from app.services.auth import AuthService
from app.services.links import LinkCreationError, LinkService
from app.services.rate_limit import RateLimiter

ROUTE_DOCS = {
    "list_users": (
        "Получить список пользователей",
        "Возвращает пользователей с пагинацией. Доступно только администратору.",
    ),
    "get_user": (
        "Получить пользователя",
        "Возвращает профиль выбранного пользователя без пароля и секретов.",
    ),
    "update_user": (
        "Изменить роль или активность пользователя",
        "Администратор может включить или отключить аккаунт и изменить роль.",
    ),
    "list_links": (
        "Получить все короткие ссылки",
        "Возвращает гостевые и пользовательские ссылки с владельцами и статистикой.",
    ),
    "get_link": (
        "Получить любую короткую ссылку",
        "Возвращает ссылку и базовую статистику для административной модерации.",
    ),
    "update_link": (
        "Изменить чужую короткую ссылку",
        "Разрешены только label и активность. URL, shortcode и владелец неизменяемы.",
    ),
    "get_admin_settings": (
        "Получить глобальные настройки",
        "Возвращает срок работы ссылок после удаления аккаунта.",
    ),
    "update_admin_settings": (
        "Изменить глобальные настройки",
        "Изменяет срок работы ссылок будущих удалённых аккаунтов.",
    ),
    "register": (
        "Зарегистрировать аккаунт",
        "Создаёт аккаунт и в development возвращает token подтверждения email.",
    ),
    "verify_email": (
        "Подтвердить email",
        "Подтверждает email после регистрации или завершает смену email.",
    ),
    "login": (
        "Войти в аккаунт",
        "Возвращает access token и устанавливает rotating HttpOnly refresh cookie.",
    ),
    "verify_login_two_factor": (
        "Подтвердить вход кодом 2FA",
        "Завершает двухэтапный вход и создаёт пользовательскую сессию.",
    ),
    "refresh": (
        "Обновить сессию",
        "Ротирует HttpOnly refresh cookie и возвращает новый access token.",
    ),
    "logout": (
        "Выйти из аккаунта",
        "Отзывает текущую refresh-сессию и очищает cookie.",
    ),
    "request_password_reset": (
        "Запросить восстановление пароля",
        "Всегда возвращает нейтральный ответ; development также возвращает token.",
    ),
    "confirm_password_reset": (
        "Установить новый пароль",
        "Применяет token восстановления и отзывает существующие сессии.",
    ),
    "current_user": (
        "Получить текущий профиль",
        "Возвращает профиль владельца текущего access token.",
    ),
    "list_my_links": (
        "Получить свои ссылки",
        "Поддерживает поиск, папку, активность, сортировку и пагинацию.",
    ),
    "get_my_link": (
        "Получить свою ссылку",
        "Возвращает базовую статистику только владельцу ссылки.",
    ),
    "update_my_link": (
        "Изменить метаданные своей ссылки",
        "Разрешены label, активность и папка. URL и shortcode изменить нельзя.",
    ),
    "list_folders": (
        "Получить папки",
        "Возвращает папки текущего пользователя и число ссылок в каждой.",
    ),
    "create_folder": (
        "Создать папку",
        "Создаёт папку с именем и цветом из ограниченной палитры.",
    ),
    "get_folder": ("Получить папку", "Возвращает папку только её владельцу."),
    "update_folder": (
        "Изменить папку",
        "Изменяет имя или цвет папки текущего пользователя.",
    ),
    "delete_folder": (
        "Удалить папку",
        "Удаляет папку; ссылки остаются у пользователя без папки.",
    ),
    "get_my_analytics": (
        "Получить общую аналитику",
        "Возвращает summary, UTC-бакеты и топ ссылок за 24 часа, 7, 30 или 90 дней.",
    ),
    "get_my_link_analytics": (
        "Получить аналитику ссылки",
        "Возвращает агрегированную статистику выбранной ссылки только владельцу.",
    ),
    "update_profile": (
        "Изменить профиль",
        "Изменяет отображаемое имя или запускает подтверждаемую смену email.",
    ),
    "upload_avatar": (
        "Загрузить аватар",
        "Принимает PNG, JPEG или WebP размером не более 2 МБ.",
    ),
    "delete_avatar": ("Удалить аватар", "Удаляет текущий локально сохранённый аватар."),
    "read_avatar": ("Получить аватар", "Возвращает файл аватара по случайному имени."),
    "get_preferences": (
        "Получить настройки интерфейса",
        "Возвращает тему, язык и предпочтения уведомлений.",
    ),
    "update_preferences": (
        "Изменить настройки интерфейса",
        "Сохраняет тему, язык и предпочтения уведомлений аккаунта.",
    ),
    "change_password": (
        "Сменить пароль",
        "Проверяет текущий пароль и отзывает другие refresh-сессии.",
    ),
    "export_account": (
        "Экспортировать данные",
        "Скачивает JSON с профилем, ссылками, папками и агрегированной аналитикой.",
    ),
    "delete_account": (
        "Удалить аккаунт",
        "Анонимизирует профиль и фиксирует срок работы принадлежащих ссылок.",
    ),
    "list_notifications": (
        "Получить уведомления",
        "Возвращает серверные уведомления с фильтром непрочитанных и пагинацией.",
    ),
    "read_notification": (
        "Прочитать уведомление",
        "Помечает одно уведомление текущего пользователя прочитанным.",
    ),
    "read_all_notifications": (
        "Прочитать все уведомления",
        "Помечает все уведомления текущего пользователя прочитанными.",
    ),
    "request_enable_email_2fa": (
        "Запросить включение email 2FA",
        "В development возвращает код; production требует настроенный email provider.",
    ),
    "confirm_enable_email_2fa": (
        "Подтвердить включение email 2FA",
        "Проверяет одноразовый код и включает двухэтапный вход.",
    ),
    "disable_email_2fa": (
        "Отключить email 2FA",
        "Отключает двухэтапный вход для текущего аккаунта.",
    ),
    "create_link": (
        "Создать короткую ссылку",
        "Гостю доступен общий shortcode; пользователь может выбрать reuse/new, label и папку.",
    ),
    "resolve_link": (
        "Перейти по короткой ссылке",
        "Возвращает 307, атомарно увеличивает счётчик и обновляет аналитические бакеты.",
    ),
}


def create_app(
    settings: Settings | None = None,
    database: SQLClient | None = None,
    cache: LinkCache | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    app_database = database or SQLClient(
        app_settings.database_path,
        user_link_retention_days_default=app_settings.user_link_retention_days_default,
    )
    app_cache = cache or RedisClient(
        app_settings.redis_url,
        ttl_seconds=app_settings.cache_ttl_seconds,
    )
    app_rate_limiter = rate_limiter or RateLimiter(
        app_settings.redis_url,
        prefix=app_settings.rate_limit_prefix,
    )
    owns_cache = cache is None
    owns_rate_limiter = rate_limiter is None

    logging.basicConfig(
        level=getattr(logging, app_settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await app_database.create_database()
        application.state.settings = app_settings
        application.state.database = app_database
        application.state.cache = app_cache
        application.state.rate_limiter = app_rate_limiter
        application.state.link_service = LinkService(
            database=app_database,
            cache=app_cache,
            shortcode_length=app_settings.shortcode_length,
            max_attempts=app_settings.shortcode_max_attempts,
        )
        application.state.auth_service = AuthService(
            database=app_database,
            settings=app_settings,
        )

        async def governance_housekeeping() -> None:
            while True:
                await asyncio.sleep(3600)
                await app_database.run_governance_housekeeping()

        await app_database.run_governance_housekeeping()
        housekeeping_task = asyncio.create_task(governance_housekeeping())
        try:
            yield
        finally:
            housekeeping_task.cancel()
            with __import__("contextlib").suppress(asyncio.CancelledError):
                await housekeeping_task
            if owns_cache:
                await app_cache.close()
            if owns_rate_limiter:
                await app_rate_limiter.close()

    application = FastAPI(
        title=app_settings.app_name,
        description=(
            "URL Shortener API с гостевым режимом, аккаунтами, личными ссылками, "
            "базовой статистикой и защищённой административной модерацией."
        ),
        version="1.0.0",
        openapi_tags=[
            {
                "name": "links",
                "description": (
                    "Создание гостевых коротких ссылок и переход по shortcode. "
                    "Домен без схемы автоматически получает HTTPS."
                ),
            },
            {
                "name": "health",
                "description": "Проверки работоспособности API, SQLite и Redis.",
            },
            {
                "name": "auth",
                "description": (
                    "Регистрация, подтверждение email, вход, refresh/logout и "
                    "восстановление пароля."
                ),
            },
            {
                "name": "profile links",
                "description": (
                    "Личные ссылки, фильтры, базовая статистика и безопасное "
                    "изменение label/is_active."
                ),
            },
            {"name": "folders", "description": "Папки личных ссылок пользователя."},
            {
                "name": "analytics",
                "description": "Агрегированная аналитика без IP, устройств и referrer.",
            },
            {
                "name": "account",
                "description": "Профиль, аватар, настройки, экспорт и удаление аккаунта.",
            },
            {
                "name": "notifications",
                "description": "Серверные уведомления и состояние прочтения.",
            },
            {
                "name": "admin",
                "description": (
                    "Управление пользователями и модерация всех ссылок. "
                    "URL и shortcode не подлежат изменению."
                ),
            },
        ],
        license_info={"name": "MIT"},
        lifespan=lifespan,
    )
    application.include_router(api_router)
    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        metadata = ROUTE_DOCS.get(route.endpoint.__name__)
        if metadata:
            route.summary, route.description = metadata
        path = route.path
        if "/folders" in path:
            route.tags = ["folders"]
        elif "/analytics" in path:
            route.tags = ["analytics"]
        elif "/notifications" in path:
            route.tags = ["notifications"]
        elif path.startswith("/api/v1/me") and "/links" not in path:
            route.tags = ["account"]

    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @application.exception_handler(sqlite3.Error)
    async def database_error_handler(request: Request, exc: sqlite3.Error) -> JSONResponse:
        logging.getLogger(__name__).exception(
            "Database request failed for %s",
            request.url.path,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "code": "storage_unavailable",
                "detail": "Storage is temporarily unavailable",
            },
        )

    @application.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        if request.url.path.startswith("/api/v1/admin/") and exc.status_code in {401, 403}:
            try:
                await app_database.record_admin_access_attempt(
                    actor_id=None,
                    route=request.url.path,
                    reason=exc.code,
                    ip_hash=hash_token(request.client.host if request.client else "unknown"),
                )
            except sqlite3.Error:
                logging.getLogger(__name__).warning("Could not record failed admin access")
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "detail": exc.detail},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            {
                "loc": list(error["loc"]),
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": "validation_error",
                "detail": "Request validation failed",
                "errors": errors,
            },
        )

    @application.exception_handler(LinkCreationError)
    async def link_creation_error_handler(
        request: Request,
        exc: LinkCreationError,
    ) -> JSONResponse:
        logging.getLogger(__name__).error(
            "Shortcode allocation failed for %s: %s",
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "code": "shortcode_unavailable",
                "detail": "A short link could not be created",
            },
        )

    return application


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
