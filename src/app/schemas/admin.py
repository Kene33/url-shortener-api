from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import UserResponse
from app.schemas.links import LinkResponse

Role = Literal["user", "support", "moderator", "admin"]
ReportStatus = Literal["open", "in_review", "resolved", "rejected"]
ModerationCategory = Literal[
    "malware", "phishing", "spam", "copyright", "illegal", "abuse", "other"
]


class PasswordConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password_confirmation: str = Field(min_length=8, max_length=128)


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    limit: int
    offset: int


class AdminUserUpdateRequest(PasswordConfirmation):
    role: Role | None = None
    is_active: bool | None = None


class AdminLinkUpdateRequest(PasswordConfirmation):
    label: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    category: ModerationCategory | None = None
    comment: str | None = Field(default=None, min_length=1, max_length=1000)


class AdminLinkResponse(LinkResponse):
    owner_id: int | None
    owner_email: str | None


class AdminLinkListResponse(BaseModel):
    items: list[AdminLinkResponse]
    total: int
    limit: int
    offset: int


class AuditEventResponse(BaseModel):
    id: int
    actor_id: int | None
    actor_role: str | None
    action: str
    object_type: str
    object_id: str
    old_value: dict[str, object] | None = None
    new_value: dict[str, object] | None = None
    route: str | None = None
    created_at: str


class AuditLogResponse(BaseModel):
    items: list[AuditEventResponse]
    total: int
    limit: int
    offset: int


class DashboardResponse(BaseModel):
    users_total: int
    links_total: int
    links_active: int
    links_disabled: int
    reports_total: int
    reports_open: int
    recent_actions: list[AuditEventResponse]


class ReportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    shortcode: str = Field(min_length=6, max_length=32)
    category: ModerationCategory
    comment: str = Field(min_length=5, max_length=2000)


class ReportResponse(BaseModel):
    id: int
    reporter_email: EmailStr
    shortcode: str
    category: str
    comment: str
    status: ReportStatus
    resolution_comment: str | None = None
    resolved_by: int | None = None
    resolved_at: str | None = None
    created_at: str
    updated_at: str


class ReportListResponse(BaseModel):
    items: list[ReportResponse]
    total: int
    limit: int
    offset: int


class ReportResolveRequest(PasswordConfirmation):
    status: ReportStatus
    comment: str | None = Field(default=None, max_length=1000)


class LinkHistoryResponse(BaseModel):
    id: int
    shortcode: str
    actor_id: int
    action: str
    category: str | None = None
    comment: str
    created_at: str


class RetentionSettingsResponse(BaseModel):
    audit_log_days: int
    report_days: int
    admin_access_attempt_days: int
    updated_at: str


class RetentionSettingsUpdateRequest(PasswordConfirmation):
    audit_log_days: int = Field(ge=1, le=3650)
    report_days: int = Field(ge=1, le=3650)
    admin_access_attempt_days: int = Field(ge=1, le=3650)
