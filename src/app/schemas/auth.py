from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Password


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


class TwoFactorCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=4, max_length=12)


class TwoFactorVerifyRequest(TwoFactorCodeRequest):
    login_token: str = Field(min_length=32, max_length=512)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    is_admin: bool
    is_active: bool
    email_verified: bool
    display_name: str | None
    avatar_url: str | None = None
    pending_email: EmailStr | None
    two_factor_enabled: bool
    created_at: str
    updated_at: str


class RegisterResponse(BaseModel):
    user: UserResponse
    verification_required: bool
    verification_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LoginChallengeResponse(BaseModel):
    requires_two_factor: Literal[True] = True
    login_token: str
    expires_in: int
    debug_code: str | None = None


class ActionMessageResponse(BaseModel):
    message: str
    action_token: str | None = None
    debug_code: str | None = None


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: Password
    new_password: Password
