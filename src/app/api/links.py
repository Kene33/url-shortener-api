from typing import Annotated

from fastapi import APIRouter, Body, Depends, Response, status
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_link_service, get_optional_user, get_settings
from app.core.config import Settings
from app.core.errors import APIError
from app.db.sql.crud import UserRecord
from app.schemas.links import (
    CreateLinkRequest,
    CreateLinkResponse,
    ErrorResponse,
    ValidationErrorResponse,
)
from app.services.links import LinkDisabledError, LinkService

router = APIRouter(tags=["links"])


@router.post(
    "/api/v1/links",
    response_model=CreateLinkResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Создать короткую ссылку",
    description=(
        "Принимает полный HTTP/HTTPS URL или домен без схемы. Домен без схемы "
        "автоматически получает `https://`. Одинаковые нормализованные гостевые "
        "URL используют один shortcode."
    ),
    response_description="Новая гостевая короткая ссылка",
    operation_id="create_short_link",
    responses={
        200: {
            "model": CreateLinkResponse,
            "description": "Гостевая ссылка уже существовала",
            "content": {
                "application/json": {
                    "example": {
                        "shortcode": "aB3dE7xQ",
                        "short_url": "http://localhost:8000/aB3dE7xQ",
                        "created": False,
                    }
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "URL зарезервирован отключённой ссылкой",
            "content": {
                "application/json": {
                    "example": {
                        "code": "link_disabled",
                        "detail": "This destination is reserved by a disabled link",
                    }
                }
            },
        },
        401: {
            "model": ErrorResponse,
            "description": "Поля аккаунта переданы без access token",
        },
        422: {
            "model": ValidationErrorResponse,
            "description": "Запрос или URL не прошёл валидацию",
        },
        503: {
            "model": ErrorResponse,
            "description": "SQLite недоступна или shortcode не удалось выделить",
            "content": {
                "application/json": {
                    "examples": {
                        "storage_unavailable": {
                            "summary": "SQLite недоступна",
                            "value": {
                                "code": "storage_unavailable",
                                "detail": "Storage is temporarily unavailable",
                            },
                        },
                        "shortcode_unavailable": {
                            "summary": "Не удалось выделить shortcode",
                            "value": {
                                "code": "shortcode_unavailable",
                                "detail": "A short link could not be created",
                            },
                        },
                    }
                }
            },
        },
    },
)
async def create_link(
    payload: Annotated[
        CreateLinkRequest,
        Body(
            openapi_examples={
                "bare_domain": {
                    "summary": "Домен без схемы",
                    "description": "Будет обработан как https://google.com/",
                    "value": {"url": "google.com"},
                },
                "full_url": {
                    "summary": "Полный HTTPS URL",
                    "value": {"url": "https://example.com/long/path"},
                },
            }
        ),
    ],
    response: Response,
    service: LinkService = Depends(get_link_service),
    settings: Settings = Depends(get_settings),
    user: UserRecord | None = Depends(get_optional_user),
) -> CreateLinkResponse:
    if user is None and (payload.mode != "reuse" or payload.label is not None):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_required",
            detail="mode and label require an authenticated account",
        )
    try:
        if user is None:
            result = await service.create_guest_link(payload.url, payload.normalized_url)
        else:
            result = await service.create_user_link(
                url=payload.url,
                normalized_url=payload.normalized_url,
                owner_id=user.id,
                label=payload.label,
                reuse=payload.mode == "reuse",
            )
    except LinkDisabledError as exc:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="link_disabled",
            detail="This destination is reserved by a disabled link",
        ) from exc
    response.status_code = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    public_base_url = str(settings.public_base_url).rstrip("/")
    short_url = f"{public_base_url}/{result.link.shortcode}"
    return CreateLinkResponse(
        shortcode=result.link.shortcode,
        short_url=short_url,
        created=result.created,
        owner_id=user.id if user is not None else None,
        label=result.link.label if user is not None else None,
    )


@router.get(
    "/{shortcode}",
    response_class=RedirectResponse,
    summary="Перейти по короткой ссылке",
    description=(
        "Возвращает временный редирект `307` на неизменяемый целевой URL и "
        "атомарно увеличивает внутренний счётчик переходов."
    ),
    operation_id="resolve_short_link",
    responses={
        307: {
            "description": "Редирект на неизменяемый целевой URL",
            "headers": {
                "Location": {
                    "description": "Destination URL",
                    "schema": {"type": "string", "format": "uri"},
                }
            },
        },
        404: {
            "model": ErrorResponse,
            "description": "Shortcode не найден",
            "content": {
                "application/json": {
                    "example": {
                        "code": "link_not_found",
                        "detail": "Short link not found",
                    }
                }
            },
        },
        410: {
            "model": ErrorResponse,
            "description": "Ссылка временно отключена",
            "content": {
                "application/json": {
                    "example": {
                        "code": "link_disabled",
                        "detail": "Short link is disabled",
                    }
                }
            },
        },
        422: {"model": ValidationErrorResponse, "description": "Некорректный путь"},
        503: {"model": ErrorResponse, "description": "SQLite недоступна"},
    },
)
async def resolve_link(
    shortcode: str,
    service: LinkService = Depends(get_link_service),
) -> RedirectResponse:
    link = await service.resolve(shortcode)
    if link is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="link_not_found",
            detail="Short link not found",
        )
    if not link.is_active:
        raise APIError(
            status_code=status.HTTP_410_GONE,
            code="link_disabled",
            detail="Short link is disabled",
        )
    return RedirectResponse(url=link.url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
