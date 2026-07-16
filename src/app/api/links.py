from datetime import UTC, datetime

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


def link_short_url(shortcode: str, settings: Settings) -> str:
    return f"{str(settings.public_base_url).rstrip('/')}/{shortcode}"


@router.post(
    "/api/v1/links",
    response_model=CreateLinkResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": CreateLinkResponse},
        401: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ValidationErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def create_link(
    payload: Annotated[CreateLinkRequest, Body()],
    response: Response,
    service: Annotated[LinkService, Depends(get_link_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[UserRecord | None, Depends(get_optional_user)],
) -> CreateLinkResponse:
    if user is None and (
        payload.mode != "reuse" or payload.label is not None or payload.folder_id is not None
    ):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_required",
            detail="mode, label and folder_id require an authenticated account",
        )
    try:
        if user is None:
            link, created = await service.create_guest_link(payload.url, payload.normalized_url)
        else:
            link, created = await service.create_user_link(
                url=payload.url,
                normalized_url=payload.normalized_url,
                owner_id=user.id,
                label=payload.label,
                folder_id=payload.folder_id,
                reuse=payload.mode == "reuse",
            )
    except LinkDisabledError as exc:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="link_disabled",
            detail="This destination is reserved by a disabled link",
        ) from exc
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return CreateLinkResponse(
        shortcode=link.shortcode,
        short_url=link_short_url(link.shortcode, settings),
        created=created,
        owner_id=user.id if user else None,
        label=link.label if user else None,
        folder_id=link.folder_id if user else None,
    )


@router.get(
    "/{shortcode}",
    response_class=RedirectResponse,
    responses={
        404: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
        422: {"model": ValidationErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def resolve_link(
    shortcode: str,
    service: Annotated[LinkService, Depends(get_link_service)],
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
    if link.expires_at is not None and datetime.strptime(
        link.expires_at, "%Y-%m-%d %H:%M:%S"
    ).replace(tzinfo=UTC) <= datetime.now(UTC):
        raise APIError(
            status_code=status.HTTP_410_GONE,
            code="link_expired",
            detail="Short link expired after account deletion",
        )
    return RedirectResponse(url=link.url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
