from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserResponse
from app.schemas.links import LinkResponse


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
    limit: int
    offset: int


class AdminUserUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool | None = None
    is_admin: bool | None = None


class AdminLinkUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class AdminLinkResponse(LinkResponse):
    owner_id: int | None
    owner_email: str | None


class AdminLinkListResponse(BaseModel):
    items: list[AdminLinkResponse]
    total: int
    limit: int
    offset: int
