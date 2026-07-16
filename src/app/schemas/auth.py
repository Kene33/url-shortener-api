from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Password = Annotated[
    str,
    Field(
        min_length=8,
        max_length=128,
        description="Пароль длиной от 8 до 128 символов",
    ),
]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=32, max_length=512)


class LogoutRequest(RefreshRequest):
    pass


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)
    new_password: Password


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool
    email_verified: bool
    created_at: str


class RegisterResponse(BaseModel):
    user: UserResponse
    verification_required: bool
    verification_token: str | None = Field(
        default=None,
        description="Возвращается только вне production, пока email-провайдер не подключён",
    )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class ActionMessageResponse(BaseModel):
    message: str
    action_token: str | None = Field(
        default=None,
        description="Отладочный токен возвращается только вне production",
    )
