from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_auth_service, get_current_user, get_settings
from app.core.config import Settings
from app.core.errors import APIError
from app.db.sql.crud import UserRecord
from app.schemas.auth import (
    ActionMessageResponse,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.schemas.links import ErrorResponse, ValidationErrorResponse
from app.services.auth import (
    AuthService,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    IssuedTokens,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])

AUTH_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Авторизация не пройдена"},
    422: {"model": ValidationErrorResponse, "description": "Некорректный запрос"},
    503: {"model": ErrorResponse, "description": "SQLite недоступна"},
}


def token_response(tokens: IssuedTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=UserResponse.model_validate(tokens.user),
    )


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать аккаунт",
    responses={
        409: {"model": ErrorResponse, "description": "Email уже зарегистрирован"},
        422: AUTH_RESPONSES[422],
        503: AUTH_RESPONSES[503],
    },
)
async def register(
    payload: RegisterRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegisterResponse:
    try:
        user, verification_token = await service.register(
            str(payload.email),
            payload.password,
        )
    except EmailAlreadyRegisteredError as exc:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_already_registered",
            detail="An account with this email already exists",
        ) from exc
    return RegisterResponse(
        user=UserResponse.model_validate(user),
        verification_required=True,
        verification_token=(
            verification_token if settings.environment.lower() != "production" else None
        ),
    )


@router.post(
    "/auth/verify-email",
    response_model=UserResponse,
    summary="Подтвердить email",
    responses={400: AUTH_RESPONSES[401], 422: AUTH_RESPONSES[422]},
)
async def verify_email(
    payload: VerifyEmailRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    try:
        user = await service.verify_email(payload.token)
    except InvalidTokenError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_action_token",
            detail="Verification token is invalid or expired",
        ) from exc
    return UserResponse.model_validate(user)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Войти в аккаунт",
    responses=AUTH_RESPONSES,
)
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        tokens = await service.authenticate(str(payload.email), payload.password)
    except InvalidCredentialsError as exc:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            detail="Email or password is incorrect",
        ) from exc
    except EmailNotVerifiedError as exc:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="email_not_verified",
            detail="Email address must be verified before login",
        ) from exc
    except InactiveUserError as exc:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="user_inactive",
            detail="User account is disabled",
        ) from exc
    return token_response(tokens)


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Обновить сессию",
    responses=AUTH_RESPONSES,
)
async def refresh(
    payload: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    try:
        tokens = await service.rotate_refresh_token(payload.refresh_token)
    except InvalidTokenError as exc:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_refresh_token",
            detail="Refresh token is invalid, expired or already used",
        ) from exc
    except (EmailNotVerifiedError, InactiveUserError) as exc:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="user_inactive",
            detail="User account cannot start a session",
        ) from exc
    return token_response(tokens)


@router.post(
    "/auth/logout",
    response_model=ActionMessageResponse,
    response_model_exclude_none=True,
    summary="Завершить сессию",
)
async def logout(
    payload: LogoutRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ActionMessageResponse:
    await service.logout(payload.refresh_token)
    return ActionMessageResponse(message="Session revoked")


@router.post(
    "/auth/password-reset/request",
    response_model=ActionMessageResponse,
    response_model_exclude_none=True,
    summary="Запросить восстановление пароля",
)
async def request_password_reset(
    payload: PasswordResetRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    token = await service.request_password_reset(str(payload.email))
    return ActionMessageResponse(
        message="If the account exists, password reset instructions were created",
        action_token=token if settings.environment.lower() != "production" else None,
    )


@router.post(
    "/auth/password-reset/confirm",
    response_model=ActionMessageResponse,
    response_model_exclude_none=True,
    summary="Установить новый пароль",
    responses={400: AUTH_RESPONSES[401], 422: AUTH_RESPONSES[422]},
)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ActionMessageResponse:
    try:
        await service.reset_password(payload.token, payload.new_password)
    except InvalidTokenError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_action_token",
            detail="Password reset token is invalid or expired",
        ) from exc
    return ActionMessageResponse(message="Password updated; existing sessions revoked")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Получить текущего пользователя",
    responses={401: AUTH_RESPONSES[401]},
)
async def current_user(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> UserResponse:
    return UserResponse.model_validate(user)
