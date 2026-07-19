from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.auth import user_response
from app.api.dependencies import (
    get_database,
    get_link_service,
    get_settings,
    require_admin,
    require_moderator_or_admin,
    require_support_or_admin,
)
from app.api.me import link_response
from app.api.rate_limit import admin_policy, enforce_rate_limit, rate_limit_subject
from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import hash_token, verify_password
from app.db.sql.crud import LinkRecord, SQLClient, UserRecord
from app.schemas.admin import (
    AdminLinkListResponse,
    AdminLinkResponse,
    AdminLinkUpdateRequest,
    AdminUserListResponse,
    AdminUserUpdateRequest,
    AuditLogResponse,
    DashboardResponse,
    LinkHistoryResponse,
    ModerationCategory,
    PasswordConfirmation,
    ReportCreateRequest,
    ReportListResponse,
    ReportResolveRequest,
    ReportResponse,
    ReportStatus,
    RetentionSettingsResponse,
    RetentionSettingsUpdateRequest,
    Role,
)
from app.schemas.auth import UserResponse
from app.schemas.links import ErrorResponse, ValidationErrorResponse
from app.services.links import LinkService
from app.services.rate_limit import RateLimiter
from app.api.dependencies import get_rate_limiter

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
public_router = APIRouter(prefix="/api/v1", tags=["reports"])
ADMIN_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ValidationErrorResponse},
    429: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def admin_link_response(
    link: LinkRecord, owner_email: str | None, settings: Settings
) -> AdminLinkResponse:
    return AdminLinkResponse(
        **link_response(link, settings).model_dump(),
        owner_id=link.owner_id,
        owner_email=owner_email,
    )


async def _limit(
    request: Request,
    response: Response,
    actor: UserRecord,
    limiter: RateLimiter,
    settings: Settings,
    mutation: bool = False,
) -> None:
    await enforce_rate_limit(
        limiter=limiter,
        policy=admin_policy(settings, mutation),
        subject=rate_limit_subject(request, actor.id),
        response=response,
    )


def _reauth(actor: UserRecord, password: str) -> None:
    if not verify_password(actor.password_hash, password):
        raise APIError(
            status_code=400,
            code="current_password_invalid",
            detail="Password confirmation is invalid",
        )


async def _audit(
    db: SQLClient,
    request: Request,
    actor: UserRecord,
    action: str,
    typ: str,
    ident: str,
    old=None,
    new=None,
) -> None:
    await db.add_audit_log(
        actor_id=actor.id,
        actor_role=actor.role,
        action=action,
        object_type=typ,
        object_id=ident,
        old_value=old,
        new_value=new,
        route=request.url.path,
        ip_hash=hash_token(request.client.host if request.client else "unknown"),
    )


@router.get("/dashboard", response_model=DashboardResponse, responses=ADMIN_RESPONSES)
async def dashboard(
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings)
    return await db.get_dashboard()


@router.get("/users", response_model=AdminUserListResponse, responses=ADMIN_RESPONSES)
async def list_users(
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_support_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    q: str | None = None,
    role: Role | None = None,
    is_active: bool | None = None,
    email_verified: bool | None = None,
    deletion_state: Annotated[str | None, Query(pattern="^(requested|anonymized|none)$")] = None,
    registered_from: str | None = None,
    registered_to: str | None = None,
    sort: Annotated[
        str, Query(pattern="^(created_at_desc|created_at_asc|email_asc|email_desc)$")
    ] = "created_at_desc",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    await _limit(request, response, actor, limiter, settings)
    users, total = await db.list_users_governance(
        q=q,
        role=role,
        is_active=is_active,
        email_verified=email_verified,
        deletion_state=deletion_state,
        registered_from=registered_from,
        registered_to=registered_to,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return AdminUserListResponse(
        items=[user_response(u, settings) for u in users], total=total, limit=limit, offset=offset
    )


@router.get("/users/{user_id}", response_model=UserResponse, responses=ADMIN_RESPONSES)
async def get_user(
    user_id: int,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_support_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
):
    await _limit(request, response, actor, limiter, settings)
    user = await db.get_user_by_id(user_id)
    if user is None:
        raise APIError(status_code=404, code="user_not_found", detail="User not found")
    return user_response(user, settings)


@router.patch("/users/{user_id}", response_model=UserResponse, responses=ADMIN_RESPONSES)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
):
    await _limit(request, response, actor, limiter, settings, True)
    _reauth(actor, payload.password_confirmation)
    if payload.role is None and payload.is_active is None:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    if user_id == actor.id and (payload.role not in (None, "admin") or payload.is_active is False):
        raise APIError(
            status_code=409, code="cannot_modify_self", detail="Cannot demote or disable self"
        )
    before = await db.get_user_by_id(user_id)
    user = await db.update_user_governance_fields(
        user_id, role=payload.role, is_active=payload.is_active
    )
    if user is None:
        raise APIError(status_code=404, code="user_not_found", detail="User not found")
    await _audit(
        db,
        request,
        actor,
        "user.updated",
        "user",
        str(user_id),
        {"role": before.role, "is_active": before.is_active} if before else None,
        {"role": user.role, "is_active": user.is_active},
    )
    return user_response(user, settings)


@router.post(
    "/users/{user_id}/deletion/request", response_model=UserResponse, responses=ADMIN_RESPONSES
)
async def admin_delete(
    user_id: int,
    payload: PasswordConfirmation,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
):
    await _limit(request, response, actor, limiter, settings, True)
    _reauth(actor, payload.password_confirmation)
    user = await db.request_account_deletion(user_id)
    if user is None:
        raise APIError(status_code=404, code="user_not_found", detail="User not found")
    await _audit(db, request, actor, "user.deletion_requested", "user", str(user_id))
    return user_response(user, settings)


@router.post("/users/{user_id}/anonymize", response_model=UserResponse, responses=ADMIN_RESPONSES)
async def anonymize(
    user_id: int,
    payload: PasswordConfirmation,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
):
    await _limit(request, response, actor, limiter, settings, True)
    _reauth(actor, payload.password_confirmation)
    user = await db.anonymize_account(user_id)
    if user is None:
        raise APIError(status_code=404, code="user_not_found", detail="User not found")
    await _audit(db, request, actor, "user.anonymized", "user", str(user_id))
    return user_response(user, settings)


@router.get("/links", response_model=AdminLinkListResponse, responses=ADMIN_RESPONSES)
async def list_links(
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    owner_id: int | None = None,
    is_active: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    await _limit(request, response, actor, limiter, settings)
    links, total = await db.list_all_links(
        owner_id=owner_id, is_active=is_active, limit=limit, offset=offset
    )
    return AdminLinkListResponse(
        items=[admin_link_response(x, email, settings) for x, email in links],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/links/{shortcode}", response_model=AdminLinkResponse, responses=ADMIN_RESPONSES)
async def get_link(
    shortcode: str,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings)
    item = await db.get_link_with_owner(shortcode)
    if item is None:
        raise APIError(status_code=404, code="link_not_found", detail="Short link not found")
    return admin_link_response(*item, settings)


@router.patch("/links/{shortcode}", response_model=AdminLinkResponse, responses=ADMIN_RESPONSES)
async def update_link(
    shortcode: str,
    payload: AdminLinkUpdateRequest,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    service: Annotated[LinkService, Depends(get_link_service)],
    db: Annotated[SQLClient, Depends(get_database)],
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
):
    await _limit(request, response, actor, limiter, settings, True)
    _reauth(actor, payload.password_confirmation)
    fields = payload.model_fields_set - {"password_confirmation", "category", "comment"}
    if not fields:
        raise APIError(status_code=400, code="invalid_update", detail="No update fields provided")
    if "is_active" in fields and (payload.category is None or not payload.comment):
        raise APIError(
            status_code=400,
            code="moderation_reason_required",
            detail="Category and comment are required when changing status",
        )
    before = await db.get_link_with_owner(shortcode)
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
    if "is_active" in fields:
        await db.add_moderation_action(
            shortcode=shortcode,
            actor_id=actor.id,
            action="unblocked" if payload.is_active else "blocked",
            category=payload.category,
            comment=payload.comment or "",
        )
    await _audit(
        db,
        request,
        actor,
        "link.updated",
        "link",
        shortcode,
        {"label": before[0].label, "is_active": before[0].is_active} if before else None,
        {"label": link.label, "is_active": link.is_active},
    )
    result = await db.get_link_with_owner(shortcode)
    assert result
    return admin_link_response(*result, settings)


@router.get(
    "/links/{shortcode}/history",
    response_model=list[LinkHistoryResponse],
    responses=ADMIN_RESPONSES,
)
async def link_history(
    shortcode: str,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings)
    return await db.get_link_history(shortcode)


@public_router.post("/reports", status_code=202, response_model=None)
async def create_report(
    payload: ReportCreateRequest,
    request: Request,
    response: Response,
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    from app.api.rate_limit import report_policies

    for policy, subject in report_policies(settings, request, str(payload.email)):
        await enforce_rate_limit(limiter=limiter, policy=policy, subject=subject, response=response)
    await db.create_report(
        email=str(payload.email),
        shortcode=payload.shortcode,
        category=payload.category,
        comment=payload.comment,
    )


@router.get("/reports", response_model=ReportListResponse, responses=ADMIN_RESPONSES)
async def reports(
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
    status_filter: ReportStatus | None = None,
    category: ModerationCategory | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    await _limit(request, response, actor, limiter, settings)
    items, total = await db.list_reports(
        report_status=status_filter, category=category, limit=limit, offset=offset
    )
    return ReportListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/reports/{report_id}", response_model=ReportResponse, responses=ADMIN_RESPONSES)
async def report(
    report_id: int,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings)
    item = await db.get_report(report_id)
    if item is None:
        raise APIError(status_code=404, code="report_not_found", detail="Report not found")
    return item


@router.patch("/reports/{report_id}", response_model=ReportResponse, responses=ADMIN_RESPONSES)
async def resolve_report(
    report_id: int,
    payload: ReportResolveRequest,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_moderator_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings, True)
    _reauth(actor, payload.password_confirmation)
    item = await db.resolve_report(
        report_id, report_status=payload.status, comment=payload.comment, actor_id=actor.id
    )
    if item is None:
        raise APIError(status_code=404, code="report_not_found", detail="Report not found")
    await _audit(
        db,
        request,
        actor,
        "report.updated",
        "report",
        str(report_id),
        new={"status": payload.status},
    )
    return item


@router.get("/audit-log", response_model=AuditLogResponse, responses=ADMIN_RESPONSES)
async def audit_log(
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_support_or_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
    actor_id: int | None = None,
    action: str | None = None,
    object_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    await _limit(request, response, actor, limiter, settings)
    items, total = await db.list_audit_log(
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AuditLogResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/settings/retention", response_model=RetentionSettingsResponse, responses=ADMIN_RESPONSES
)
async def retention(
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings)
    return await db.get_retention_settings()


@router.patch(
    "/settings/retention", response_model=RetentionSettingsResponse, responses=ADMIN_RESPONSES
)
async def update_retention(
    payload: RetentionSettingsUpdateRequest,
    request: Request,
    response: Response,
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    await _limit(request, response, actor, limiter, settings, True)
    _reauth(actor, payload.password_confirmation)
    item = await db.update_retention_settings(
        audit_log_days=payload.audit_log_days,
        report_days=payload.report_days,
        admin_access_attempt_days=payload.admin_access_attempt_days,
    )
    await _audit(db, request, actor, "retention.updated", "retention", "1", new=item)
    return item


@router.get("/settings", responses=ADMIN_RESPONSES, deprecated=True)
async def legacy_settings(
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
):
    item = await db.get_admin_settings()
    return {
        "user_link_retention_days": item.user_link_retention_days,
        "updated_at": item.updated_at,
    }


@router.patch("/settings", responses=ADMIN_RESPONSES, deprecated=True)
async def legacy_update_settings(
    payload: dict,
    actor: Annotated[UserRecord, Depends(require_admin)],
    db: Annotated[SQLClient, Depends(get_database)],
):
    value = payload.get("user_link_retention_days")
    if not isinstance(value, int):
        raise APIError(
            status_code=400, code="invalid_update", detail="user_link_retention_days is required"
        )
    item = await db.update_admin_settings(value)
    return {
        "user_link_retention_days": item.user_link_retention_days,
        "updated_at": item.updated_at,
    }
