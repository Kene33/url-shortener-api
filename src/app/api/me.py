from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_current_user, get_database, get_link_service, get_settings
from app.core.config import Settings
from app.core.errors import APIError
from app.db.sql.crud import LinkRecord, SQLClient, UserRecord
from app.schemas.links import (
    ErrorResponse,
    LinkListResponse,
    LinkResponse,
    UpdateLinkRequest,
    ValidationErrorResponse,
)
from app.services.links import LinkService

router = APIRouter(prefix="/api/v1/me/links", tags=["profile links"])

PRIVATE_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Пустое или недопустимое изменение"},
    401: {"model": ErrorResponse, "description": "Требуется access token"},
    404: {"model": ErrorResponse, "description": "Ссылка не найдена у владельца"},
    422: {"model": ValidationErrorResponse, "description": "Некорректный запрос"},
    503: {"model": ErrorResponse, "description": "SQLite недоступна"},
}


def link_response(link: LinkRecord, settings: Settings) -> LinkResponse:
    base_url = str(settings.public_base_url).rstrip("/")
    return LinkResponse(
        shortcode=link.shortcode,
        url=link.url,
        short_url=f"{base_url}/{link.shortcode}",
        label=link.label,
        is_active=link.is_active,
        access_count=link.access_count,
        created_at=link.created_at,
        updated_at=link.updated_at,
        last_accessed_at=link.last_accessed_at,
    )


@router.get(
    "",
    response_model=LinkListResponse,
    summary="Получить свои ссылки",
    description="Пагинация, фильтр активности и сортировка по дате создания.",
    responses=PRIVATE_RESPONSES,
)
async def list_my_links(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    is_active: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[
        Literal["created_at_desc", "created_at_asc"],
        Query(),
    ] = "created_at_desc",
) -> LinkListResponse:
    links, total = await database.list_owner_links(
        user.id,
        is_active=is_active,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    return LinkListResponse(
        items=[link_response(link, settings) for link in links],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{shortcode}",
    response_model=LinkResponse,
    summary="Получить свою ссылку и статистику",
    responses=PRIVATE_RESPONSES,
)
async def get_my_link(
    shortcode: str,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LinkResponse:
    link = await database.get_owned_link(shortcode, user.id)
    if link is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="link_not_found",
            detail="Short link not found",
        )
    return link_response(link, settings)


@router.patch(
    "/{shortcode}",
    response_model=LinkResponse,
    summary="Изменить название или активность своей ссылки",
    description="Целевой URL и shortcode отсутствуют в update-модели и неизменяемы.",
    responses=PRIVATE_RESPONSES,
)
async def update_my_link(
    shortcode: str,
    payload: UpdateLinkRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    service: Annotated[LinkService, Depends(get_link_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LinkResponse:
    fields = payload.model_fields_set
    if not fields:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_update",
            detail="At least one of label or is_active is required",
        )
    link = await service.update_link_metadata(
        shortcode,
        owner_id=user.id,
        label=payload.label,
        set_label="label" in fields,
        is_active=payload.is_active,
        set_active="is_active" in fields,
    )
    if link is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="link_not_found",
            detail="Short link not found",
        )
    return link_response(link, settings)
