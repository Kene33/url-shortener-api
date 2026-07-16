from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import RedirectResponse

from app.api.dependencies import get_link_service, get_settings
from app.core.config import Settings
from app.core.errors import APIError
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
    status_code=status.HTTP_201_CREATED,
    operation_id="create_short_link",
    responses={
        200: {"model": CreateLinkResponse, "description": "Existing guest link"},
        409: {"model": ErrorResponse, "description": "Link is disabled"},
        422: {"model": ValidationErrorResponse, "description": "Invalid request"},
        503: {
            "model": ErrorResponse,
            "description": "Storage or shortcode allocation unavailable",
        },
    },
)
async def create_link(
    payload: CreateLinkRequest,
    response: Response,
    service: LinkService = Depends(get_link_service),
    settings: Settings = Depends(get_settings),
) -> CreateLinkResponse:
    try:
        result = await service.create_guest_link(payload.url, payload.normalized_url)
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
    )


@router.get(
    "/{shortcode}",
    response_class=RedirectResponse,
    operation_id="resolve_short_link",
    responses={
        307: {
            "description": "Redirect to the immutable destination URL",
            "headers": {
                "Location": {
                    "description": "Destination URL",
                    "schema": {"type": "string", "format": "uri"},
                }
            },
        },
        404: {"model": ErrorResponse, "description": "Link not found"},
        410: {"model": ErrorResponse, "description": "Link disabled"},
        422: {"model": ValidationErrorResponse, "description": "Invalid path"},
        503: {"model": ErrorResponse, "description": "Storage unavailable"},
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
