import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import Settings, get_settings
from app.core.errors import APIError
from app.db.redis.links import LinkCache, RedisClient
from app.db.sql.crud import SQLClient
from app.services.links import LinkCreationError, LinkService


def create_app(
    settings: Settings | None = None,
    database: SQLClient | None = None,
    cache: LinkCache | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    app_database = database or SQLClient(app_settings.database_path)
    app_cache = cache or RedisClient(
        app_settings.redis_url,
        ttl_seconds=app_settings.cache_ttl_seconds,
    )
    owns_cache = cache is None

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
        application.state.link_service = LinkService(
            database=app_database,
            cache=app_cache,
            shortcode_length=app_settings.shortcode_length,
            max_attempts=app_settings.shortcode_max_attempts,
        )
        try:
            yield
        finally:
            if owns_cache:
                await app_cache.close()

    application = FastAPI(
        title=app_settings.app_name,
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(api_router)

    if app_settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
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
