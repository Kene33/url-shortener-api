import secrets
import sqlite3
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse

from app.api.auth import user_response
from app.api.dependencies import (
    get_auth_service,
    get_current_user,
    get_database,
    get_link_service,
    get_rate_limiter,
    get_settings,
)
from app.api.rate_limit import auth_action_policy, enforce_rate_limit, rate_limit_subject
from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import verify_password
from app.db.sql.crud import FolderRecord, LinkRecord, NotificationRecord, SQLClient, UserRecord
from app.schemas.auth import (
    ActionMessageResponse,
    ChangePasswordRequest,
    TwoFactorCodeRequest,
    UserResponse,
)
from app.schemas.links import (
    ErrorResponse,
    LinkListResponse,
    LinkResponse,
    UpdateLinkRequest,
    ValidationErrorResponse,
)
from app.schemas.me import (
    AnalyticsPointResponse,
    AnalyticsResponse,
    AnalyticsSummary,
    DeleteAccountRequest,
    DeletionRequest,
    ExportResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderUpdateRequest,
    NotificationListResponse,
    NotificationResponse,
    PreferencesResponse,
    PreferencesUpdateRequest,
    ProfileUpdateResponse,
    ProfileUpdateRequest,
    TwoFactorStatusResponse,
)
from app.services.auth import (
    AuthService,
    CurrentPasswordInvalidError,
    EmailAlreadyInUseError,
    EmailDeliveryUnavailableError,
    InvalidTwoFactorCodeError,
)
from app.services.links import LinkService
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/api/v1/me", tags=["profile links"])

PRIVATE_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ValidationErrorResponse},
    503: {"model": ErrorResponse},
}


def link_response(link: LinkRecord, settings: Settings) -> LinkResponse:
    base_url = str(settings.public_base_url).rstrip("/")
    return LinkResponse(
        shortcode=link.shortcode,
        url=link.url,
        short_url=f"{base_url}/{link.shortcode}",
        label=link.label,
        is_active=link.is_active,
        folder_id=link.folder_id,
        access_count=link.access_count,
        created_at=link.created_at,
        updated_at=link.updated_at,
        last_accessed_at=link.last_accessed_at,
        expires_at=link.expires_at,
    )


def folder_response(folder: FolderRecord, link_count: int) -> FolderResponse:
    return FolderResponse(
        id=folder.id,
        name=folder.name,
        color=folder.color,
        link_count=link_count,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def notification_response(notification: NotificationRecord) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        type=notification.type,
        key=notification.key,
        payload=notification.payload,
        read_at=notification.read_at,
        created_at=notification.created_at,
    )


def preferences_response(preferences) -> PreferencesResponse:
    return PreferencesResponse(
        theme=preferences.theme,
        language=preferences.language,
        email_notifications=preferences.email_notifications,
        system_notifications=preferences.system_notifications,
        created_at=preferences.created_at,
        updated_at=preferences.updated_at,
    )


def avatar_dir(settings: Settings) -> Path:
    path = Path(settings.avatar_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def detect_image_extension(content: bytes) -> str | None:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    return None


def validate_timezone(timezone: str) -> str:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise APIError(
            status_code=400,
            code="invalid_timezone",
            detail="timezone must be a valid IANA timezone",
        ) from exc
    return timezone


@router.get("/links", response_model=LinkListResponse, responses=PRIVATE_RESPONSES)
async def list_my_links(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    q: str | None = None,
    folder_id: Annotated[int | None, Query(ge=1)] = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[
        Literal["created_at_desc", "created_at_asc", "access_count_desc", "access_count_asc"],
        Query(),
    ] = "created_at_desc",
) -> LinkListResponse:
    links, total = await database.list_owner_links(
        user.id,
        is_active=is_active,
        q=q,
        folder_id=folder_id,
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


@router.get("/links/{shortcode}", response_model=LinkResponse, responses=PRIVATE_RESPONSES)
async def get_my_link(
    shortcode: str,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LinkResponse:
    link = await database.get_owned_link(shortcode, user.id)
    if link is None:
        raise APIError(status_code=404, code="link_not_found", detail="Short link not found")
    return link_response(link, settings)


@router.patch("/links/{shortcode}", response_model=LinkResponse, responses=PRIVATE_RESPONSES)
async def update_my_link(
    shortcode: str,
    payload: UpdateLinkRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    service: Annotated[LinkService, Depends(get_link_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LinkResponse:
    fields = payload.model_fields_set
    if not fields:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    try:
        link = await service.update_link_metadata(
            shortcode,
            owner_id=user.id,
            label=payload.label,
            set_label="label" in fields,
            is_active=payload.is_active,
            set_active="is_active" in fields,
            folder_id=payload.folder_id if "folder_id" in fields else None,
            set_folder="folder_id" in fields,
        )
    except sqlite3.IntegrityError as exc:
        raise APIError(status_code=404, code="folder_not_found", detail="Folder not found") from exc
    if link is None:
        raise APIError(status_code=404, code="link_not_found", detail="Short link not found")
    return link_response(link, settings)


@router.get("/folders", response_model=list[FolderResponse], responses=PRIVATE_RESPONSES)
async def list_folders(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> list[FolderResponse]:
    return [
        folder_response(folder, count) for folder, count in await database.list_folders(user.id)
    ]


@router.post(
    "/folders", response_model=FolderResponse, status_code=201, responses=PRIVATE_RESPONSES
)
async def create_folder(
    payload: FolderCreateRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> FolderResponse:
    folder = await database.create_folder(user.id, payload.name, payload.color)
    return folder_response(folder, 0)


@router.get("/folders/{folder_id}", response_model=FolderResponse, responses=PRIVATE_RESPONSES)
async def get_folder(
    folder_id: int,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> FolderResponse:
    for folder, count in await database.list_folders(user.id):
        if folder.id == folder_id:
            return folder_response(folder, count)
    raise APIError(status_code=404, code="folder_not_found", detail="Folder not found")


@router.patch("/folders/{folder_id}", response_model=FolderResponse, responses=PRIVATE_RESPONSES)
async def update_folder(
    folder_id: int,
    payload: FolderUpdateRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> FolderResponse:
    if not payload.model_fields_set:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    folder = await database.update_folder(
        folder_id,
        user.id,
        name=payload.name if "name" in payload.model_fields_set else None,
        color=payload.color if "color" in payload.model_fields_set else None,
    )
    if folder is None:
        raise APIError(status_code=404, code="folder_not_found", detail="Folder not found")
    for current, count in await database.list_folders(user.id):
        if current.id == folder.id:
            return folder_response(current, count)
    raise APIError(status_code=404, code="folder_not_found", detail="Folder not found")


@router.delete("/folders/{folder_id}", status_code=204, responses=PRIVATE_RESPONSES)
async def delete_folder(
    folder_id: int,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> Response:
    deleted = await database.delete_folder(folder_id, user.id)
    if not deleted:
        raise APIError(status_code=404, code="folder_not_found", detail="Folder not found")
    return Response(status_code=204)


@router.get("/analytics", response_model=AnalyticsResponse, responses=PRIVATE_RESPONSES)
async def get_my_analytics(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    period: Literal["24h", "7d", "30d", "90d"] = "7d",
    timezone: str = "UTC",
) -> AnalyticsResponse:
    timezone = validate_timezone(timezone)
    summary, series, top_links = await database.get_owner_analytics(
        user.id, period=period, timezone=timezone
    )
    return AnalyticsResponse(
        summary=AnalyticsSummary(**summary),
        series=[
            AnalyticsPointResponse(bucket_start=item.bucket_start, count=item.count)
            for item in series
        ],
        top_links=[link_response(link, settings) for link in top_links],
    )


@router.get(
    "/links/{shortcode}/analytics", response_model=AnalyticsResponse, responses=PRIVATE_RESPONSES
)
async def get_my_link_analytics(
    shortcode: str,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    period: Literal["24h", "7d", "30d", "90d"] = "7d",
    timezone: str = "UTC",
) -> AnalyticsResponse:
    timezone = validate_timezone(timezone)
    result = await database.get_link_analytics(shortcode, user.id, period=period, timezone=timezone)
    if result is None:
        raise APIError(status_code=404, code="link_not_found", detail="Short link not found")
    summary, series, top_links = result
    return AnalyticsResponse(
        summary=AnalyticsSummary(**summary),
        series=[
            AnalyticsPointResponse(bucket_start=item.bucket_start, count=item.count)
            for item in series
        ],
        top_links=[link_response(link, settings) for link in top_links],
    )


@router.patch("/profile", response_model=ProfileUpdateResponse, responses=PRIVATE_RESPONSES)
async def update_profile(
    payload: ProfileUpdateRequest,
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProfileUpdateResponse:
    if not payload.model_fields_set:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    updated = user
    if "display_name" in payload.model_fields_set:
        updated = (
            await database.update_profile(
                user.id,
                display_name=payload.display_name,
                set_display_name=True,
            )
            or user
        )
    if (
        "email" in payload.model_fields_set
        and payload.email
        and payload.email.lower() != user.email.lower()
    ):
        await enforce_rate_limit(
            limiter=rate_limiter,
            policy=auth_action_policy(settings, "auth_profile_email_change"),
            subject=rate_limit_subject(request, user.id, payload.email),
            response=response,
        )
        try:
            token = await auth_service.request_email_change(updated, str(payload.email))
        except EmailAlreadyInUseError as exc:
            raise APIError(
                status_code=409, code="email_already_in_use", detail="Email is already in use"
            ) from exc
        updated = await database.get_user_by_id(user.id) or updated
        if settings.environment.lower() != "production":
            return ProfileUpdateResponse(
                **user_response(updated, settings).model_dump(),
                verification_token=token,
            )
    return ProfileUpdateResponse(**user_response(updated, settings).model_dump())


@router.post("/avatar", response_model=UserResponse, responses=PRIVATE_RESPONSES)
async def upload_avatar(
    file: UploadFile = File(...),
    user: Annotated[UserRecord, Depends(get_current_user)] = None,
    database: Annotated[SQLClient, Depends(get_database)] = None,
    settings: Annotated[Settings, Depends(get_settings)] = None,
) -> UserResponse:
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise APIError(status_code=400, code="invalid_update", detail="Avatar exceeds 2 MiB")
    extension = detect_image_extension(content)
    if extension is None:
        raise APIError(status_code=400, code="invalid_update", detail="Unsupported avatar format")
    filename = f"{secrets.token_hex(16)}.{extension}"
    path = avatar_dir(settings) / filename
    path.write_bytes(content)
    if user.avatar_path:
        old_path = avatar_dir(settings) / user.avatar_path
        old_path.unlink(missing_ok=True)
    updated = await database.update_profile(user.id, avatar_path=filename, set_avatar_path=True)
    assert updated is not None
    return user_response(updated, settings)


@router.delete("/avatar", response_model=UserResponse, responses=PRIVATE_RESPONSES)
async def delete_avatar(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    if user.avatar_path:
        (avatar_dir(settings) / user.avatar_path).unlink(missing_ok=True)
    updated = await database.update_profile(user.id, avatar_path=None, set_avatar_path=True)
    assert updated is not None
    return user_response(updated, settings)


@router.get("/avatar/{filename}")
async def read_avatar(
    filename: str, settings: Annotated[Settings, Depends(get_settings)]
) -> FileResponse:
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise APIError(status_code=404, code="link_not_found", detail="Avatar not found")
    path = avatar_dir(settings) / filename
    if not path.is_file():
        raise APIError(status_code=404, code="link_not_found", detail="Avatar not found")
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


@router.get("/preferences", response_model=PreferencesResponse, responses=PRIVATE_RESPONSES)
async def get_preferences(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> PreferencesResponse:
    preferences = await database.get_preferences(user.id)
    return preferences_response(preferences)


@router.patch("/preferences", response_model=PreferencesResponse, responses=PRIVATE_RESPONSES)
async def update_preferences(
    payload: PreferencesUpdateRequest,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> PreferencesResponse:
    if not payload.model_fields_set:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    preferences = await database.update_preferences(
        user.id,
        theme=payload.theme if "theme" in payload.model_fields_set else None,
        language=payload.language if "language" in payload.model_fields_set else None,
        email_notifications=(
            payload.email_notifications
            if "email_notifications" in payload.model_fields_set
            else None
        ),
        system_notifications=(
            payload.system_notifications
            if "system_notifications" in payload.model_fields_set
            else None
        ),
    )
    return preferences_response(preferences)


@router.post("/change-password", response_model=ActionMessageResponse, responses=PRIVATE_RESPONSES)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_change_password"),
        subject=rate_limit_subject(request, user.id),
        response=response,
    )
    try:
        await auth_service.change_password(
            user,
            payload.current_password,
            payload.new_password,
            request.cookies.get(settings.refresh_cookie_name),
        )
    except CurrentPasswordInvalidError as exc:
        raise APIError(
            status_code=400, code="current_password_invalid", detail="Current password is invalid"
        ) from exc
    return ActionMessageResponse(message="Password updated; other sessions revoked")


@router.get("/export", response_model=ExportResponse, responses=PRIVATE_RESPONSES)
async def export_account(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> Response:
    payload = await database.export_account(user.id)
    return Response(
        content=ExportResponse(**payload).model_dump_json(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="linkcutter-export.json"'},
    )


@router.post("/deletion/request", response_model=ActionMessageResponse, responses=PRIVATE_RESPONSES)
async def request_deletion(
    payload: DeletionRequest,
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_delete_account"),
        subject=rate_limit_subject(request, user.id),
        response=response,
    )
    if not verify_password(user.password_hash, payload.password_confirmation):
        raise APIError(
            status_code=400, code="current_password_invalid", detail="Password is invalid"
        )
    deleted = await database.request_account_deletion(user.id)
    assert deleted is not None
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )
    token = secrets.token_urlsafe(32)
    from app.core.security import hash_token
    from datetime import UTC, datetime, timedelta

    await database.store_action_token(
        user.id,
        "cancel_deletion",
        hash_token(token),
        (datetime.now(UTC) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),
    )
    return ActionMessageResponse(
        message="Account deletion scheduled for 30 days",
        action_token=token if settings.environment.lower() != "production" else None,
    )


@router.delete(
    "", response_model=ActionMessageResponse, responses=PRIVATE_RESPONSES, deprecated=True
)
async def delete_account(
    payload: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    return await request_deletion(
        DeletionRequest(password_confirmation=payload.password),
        request,
        response,
        user,
        database,
        rate_limiter,
        settings,
    )


@router.get("/notifications", response_model=NotificationListResponse, responses=PRIVATE_RESPONSES)
async def list_notifications(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NotificationListResponse:
    items, total = await database.list_notifications(
        user.id, unread_only=unread, limit=limit, offset=offset
    )
    return NotificationListResponse(
        items=[notification_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    responses=PRIVATE_RESPONSES,
)
async def read_notification(
    notification_id: int,
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> NotificationResponse:
    item = await database.mark_notification_read(notification_id, user.id)
    if item is None:
        raise APIError(
            status_code=404, code="notification_not_found", detail="Notification not found"
        )
    return notification_response(item)


@router.post(
    "/notifications/read-all", response_model=ActionMessageResponse, responses=PRIVATE_RESPONSES
)
async def read_all_notifications(
    user: Annotated[UserRecord, Depends(get_current_user)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> ActionMessageResponse:
    count = await database.mark_all_notifications_read(user.id)
    return ActionMessageResponse(message=f"Marked {count} notifications as read")


@router.post(
    "/2fa/email/request-enable", response_model=ActionMessageResponse, responses=PRIVATE_RESPONSES
)
async def request_enable_email_2fa(
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_enable_email_2fa_request"),
        subject=rate_limit_subject(request, user.id),
        response=response,
    )
    try:
        code = await auth_service.request_enable_email_2fa(user)
    except EmailDeliveryUnavailableError as exc:
        raise APIError(
            status_code=409,
            code="email_delivery_unavailable",
            detail="Email delivery provider is not configured",
        ) from exc
    return ActionMessageResponse(
        message="Verification code generated",
        debug_code=code if settings.environment.lower() != "production" else None,
    )


@router.post(
    "/2fa/email/confirm-enable", response_model=TwoFactorStatusResponse, responses=PRIVATE_RESPONSES
)
async def confirm_enable_email_2fa(
    payload: TwoFactorCodeRequest,
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TwoFactorStatusResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_enable_email_2fa_confirm"),
        subject=rate_limit_subject(request, user.id),
        response=response,
    )
    try:
        await auth_service.confirm_enable_email_2fa(user, payload.code)
    except InvalidTwoFactorCodeError as exc:
        raise APIError(
            status_code=401,
            code="invalid_two_factor_code",
            detail="Two-factor code is invalid or expired",
        ) from exc
    return TwoFactorStatusResponse(enabled=True)


@router.post(
    "/2fa/email/disable", response_model=TwoFactorStatusResponse, responses=PRIVATE_RESPONSES
)
async def disable_email_2fa(
    request: Request,
    response: Response,
    user: Annotated[UserRecord, Depends(get_current_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TwoFactorStatusResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_disable_email_2fa"),
        subject=rate_limit_subject(request, user.id),
        response=response,
    )
    await auth_service.disable_email_2fa(user)
    return TwoFactorStatusResponse(enabled=False)
