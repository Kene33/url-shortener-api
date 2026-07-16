from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.auth import UserResponse
from app.schemas.links import LinkResponse

FolderColor = Literal["blue", "cyan", "violet", "orange", "red", "green", "gray"]


class FolderResponse(BaseModel):
    id: int
    name: str
    color: Literal["blue", "cyan", "violet", "orange", "red", "green", "gray"]
    link_count: int
    created_at: str
    updated_at: str


class FolderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    color: FolderColor


class FolderUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: FolderColor | None = None


class PreferencesResponse(BaseModel):
    theme: Literal["light", "dark"]
    language: Literal["ru", "en"]
    email_notifications: bool
    system_notifications: bool
    created_at: str
    updated_at: str


class PreferencesUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal["light", "dark"] | None = None
    language: Literal["ru", "en"] | None = None
    email_notifications: bool | None = None
    system_notifications: bool | None = None


class ProfileUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class ProfileUpdateResponse(UserResponse):
    verification_token: str | None = None


class AnalyticsSummary(BaseModel):
    total_clicks: float
    active_links: float
    avg_clicks_per_link: float
    change_percent: float


class AnalyticsPointResponse(BaseModel):
    bucket_start: str
    count: int


class AnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    series: list[AnalyticsPointResponse]
    top_links: list[LinkResponse]


class NotificationResponse(BaseModel):
    id: int
    type: str
    key: str
    payload: dict[str, object]
    read_at: str | None
    created_at: str


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    limit: int
    offset: int


class ExportResponse(BaseModel):
    profile: dict[str, object]
    preferences: dict[str, object]
    folders: list[dict[str, object]]
    links: list[dict[str, object]]
    aggregate_analytics: dict[str, object]


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=8, max_length=128)


class AdminSettingsResponse(BaseModel):
    user_link_retention_days: int
    updated_at: str


class AdminSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_link_retention_days: int = Field(ge=1, le=3650)


class TwoFactorStatusResponse(BaseModel):
    enabled: bool


class MeResponse(UserResponse):
    pass
