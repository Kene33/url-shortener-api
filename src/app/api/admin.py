from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.auth import user_response
from app.api.dependencies import get_database, get_link_service, get_settings, require_admin
from app.api.me import link_response
from app.core.config import Settings
from app.core.errors import APIError
from app.db.sql.crud import LinkRecord, SQLClient, UserRecord
from app.schemas.admin import (
    AdminLinkListResponse,
    AdminLinkResponse,
    AdminUserListResponse,
    AdminUserUpdateRequest,
)
from app.schemas.auth import UserResponse
from app.schemas.links import ErrorResponse, UpdateLinkRequest, ValidationErrorResponse
from app.schemas.me import AdminSettingsResponse, AdminSettingsUpdateRequest
from app.services.links import LinkService

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

ADMIN_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ValidationErrorResponse},
    503: {"model": ErrorResponse},
}


def admin_link_response(
    link: LinkRecord,
    owner_email: str | None,
    settings: Settings,
) -> AdminLinkResponse:
    base = link_response(link, settings)
    return AdminLinkResponse(
        **base.model_dump(),
        owner_id=link.owner_id,
        owner_email=owner_email,
    )


@router.get("/users", response_model=AdminUserListResponse, responses=ADMIN_RESPONSES)
async def list_users(
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminUserListResponse:
    del admin
    users, total = await database.list_users(limit=limit, offset=offset)
    return AdminUserListResponse(
        items=[user_response(user, settings) for user in users],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", response_model=UserResponse, responses=ADMIN_RESPONSES)
async def get_user(
    user_id: int,
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    del admin
    user = await database.get_user_by_id(user_id)
    if user is None:
        raise APIError(
            status_code=status.HTTP_404_NOT_FOUND,
            code="user_not_found",
            detail="User not found",
        )
    return user_response(user, settings)


@router.patch("/users/{user_id}", response_model=UserResponse, responses=ADMIN_RESPONSES)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    fields = payload.model_fields_set
    if not fields:
        raise APIError(
            status_code=400,
            code="invalid_update",
            detail="At least one admin field is required",
        )
    if user_id == admin.id and (payload.is_active is False or payload.is_admin is False):
        raise APIError(
            status_code=409,
            code="cannot_modify_self",
            detail="Cannot disable or demote self",
        )
    user = await database.update_user_admin_fields(
        user_id,
        is_active=payload.is_active,
        set_active="is_active" in fields,
        is_admin=payload.is_admin,
        set_admin="is_admin" in fields,
    )
    if user is None:
        raise APIError(status_code=404, code="user_not_found", detail="User not found")
    return user_response(user, settings)


@router.get("/links", response_model=AdminLinkListResponse, responses=ADMIN_RESPONSES)
async def list_links(
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    owner_id: Annotated[int | None, Query(ge=1)] = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdminLinkListResponse:
    del admin
    links, total = await database.list_all_links(
        owner_id=owner_id,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return AdminLinkListResponse(
        items=[admin_link_response(link, owner_email, settings) for link, owner_email in links],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/links/{shortcode}", response_model=AdminLinkResponse, responses=ADMIN_RESPONSES)
async def get_link(
    shortcode: str,
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminLinkResponse:
    del admin
    result = await database.get_link_with_owner(shortcode)
    if result is None:
        raise APIError(status_code=404, code="link_not_found", detail="Short link not found")
    return admin_link_response(*result, settings)


@router.patch("/links/{shortcode}", response_model=AdminLinkResponse, responses=ADMIN_RESPONSES)
async def update_link(
    shortcode: str,
    payload: UpdateLinkRequest,
    admin: Annotated[UserRecord, Depends(require_admin)],
    service: Annotated[LinkService, Depends(get_link_service)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminLinkResponse:
    del admin
    fields = payload.model_fields_set
    if not fields:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    link = await service.update_link_metadata(
        shortcode,
        owner_id=None,
        label=payload.label,
        set_label="label" in fields,
        is_active=payload.is_active,
        set_active="is_active" in fields,
        folder_id=None,
        set_folder=False,
    )
    if link is None:
        raise APIError(status_code=404, code="link_not_found", detail="Short link not found")
    result = await database.get_link_with_owner(shortcode)
    assert result is not None
    return admin_link_response(*result, settings)


@router.get("/settings", response_model=AdminSettingsResponse, responses=ADMIN_RESPONSES)
async def get_admin_settings(
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> AdminSettingsResponse:
    del admin
    settings = await database.get_admin_settings()
    return AdminSettingsResponse(
        user_link_retention_days=settings.user_link_retention_days,
        updated_at=settings.updated_at,
    )


@router.patch("/settings", response_model=AdminSettingsResponse, responses=ADMIN_RESPONSES)
async def update_admin_settings(
    payload: AdminSettingsUpdateRequest,
    admin: Annotated[UserRecord, Depends(require_admin)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> AdminSettingsResponse:
    del admin
    settings = await database.update_admin_settings(payload.user_link_retention_days)
    return AdminSettingsResponse(
        user_link_retention_days=settings.user_link_retention_days,
        updated_at=settings.updated_at,
    )
