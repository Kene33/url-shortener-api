from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.dependencies import get_auth_service, get_current_user, get_rate_limiter, get_settings
from app.api.rate_limit import auth_action_policy, enforce_rate_limit, rate_limit_subject
from app.core.config import Settings
from app.core.errors import APIError
from app.db.sql.crud import UserRecord
from app.schemas.auth import (
    ActionMessageResponse,
    LoginChallengeResponse,
    LoginRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    TwoFactorVerifyRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.schemas.links import ErrorResponse, ValidationErrorResponse
from app.services.auth import (
    AuthService,
    EmailAlreadyInUseError,
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    InvalidTwoFactorCodeError,
    IssuedTokens,
    TwoFactorRequiredError,
)
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/api/v1", tags=["auth"])

AUTH_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Авторизация не пройдена"},
    429: {"model": ErrorResponse, "description": "Слишком много запросов"},
    422: {"model": ValidationErrorResponse, "description": "Некорректный запрос"},
    503: {"model": ErrorResponse, "description": "SQLite недоступна"},
}


def user_response(user: UserRecord, settings: Settings) -> UserResponse:
    avatar_url = None
    if user.avatar_path:
        base_url = str(settings.public_base_url).rstrip("/")
        avatar_url = f"{base_url}/api/v1/me/avatar/{user.avatar_path}"
    return UserResponse(
        id=user.id,
        email=user.email,
        is_admin=user.is_admin,
        is_active=user.is_active,
        email_verified=user.email_verified,
        display_name=user.display_name,
        avatar_url=avatar_url,
        pending_email=user.pending_email,
        two_factor_enabled=user.two_factor_enabled,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.refresh_cookie_domain,
        path=settings.refresh_cookie_path,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


def token_response(tokens: IssuedTokens, settings: Settings) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=user_response(tokens.user, settings),
    )


@router.post("/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegisterResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_register"),
        subject=rate_limit_subject(request, payload.email),
        response=response,
    )
    try:
        user, verification_token = await service.register(str(payload.email), payload.password)
    except EmailAlreadyRegisteredError as exc:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_already_registered",
            detail="An account with this email already exists",
        ) from exc
    return RegisterResponse(
        user=user_response(user, settings),
        verification_required=settings.email_verification_required,
        verification_token=(
            verification_token
            if settings.email_verification_required and settings.environment.lower() != "production"
            else None
        ),
    )


@router.post("/auth/verify-email", response_model=UserResponse)
async def verify_email(
    payload: VerifyEmailRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_verify_email"),
        subject=rate_limit_subject(request, payload.token),
        response=response,
    )
    try:
        user = await service.verify_email(payload.token)
    except InvalidTokenError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_action_token",
            detail="Verification token is invalid or expired",
        ) from exc
    except EmailAlreadyInUseError as exc:
        raise APIError(
            status_code=status.HTTP_409_CONFLICT,
            code="email_already_in_use",
            detail="Email is already in use",
        ) from exc
    return user_response(user, settings)


@router.post(
    "/auth/login",
    response_model=TokenResponse | LoginChallengeResponse,
    responses={**AUTH_RESPONSES, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse | LoginChallengeResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_login"),
        subject=rate_limit_subject(request, payload.email),
        response=response,
    )
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
    except TwoFactorRequiredError as exc:
        return LoginChallengeResponse(
            login_token=exc.login_token,
            expires_in=exc.expires_in,
            debug_code=exc.debug_code,
        )
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return token_response(tokens, settings)


@router.post("/auth/2fa/verify", response_model=TokenResponse, responses=AUTH_RESPONSES)
async def verify_login_two_factor(
    payload: TwoFactorVerifyRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_two_factor_verify"),
        subject=rate_limit_subject(request, payload.login_token),
        response=response,
    )
    try:
        tokens = await service.verify_login_two_factor(payload.login_token, payload.code)
    except InvalidTwoFactorCodeError as exc:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_two_factor_code",
            detail="Two-factor code is invalid or expired",
        ) from exc
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return token_response(tokens, settings)


@router.post("/auth/refresh", response_model=TokenResponse, responses=AUTH_RESPONSES)
async def refresh(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_refresh_token",
            detail="Refresh token cookie is missing",
        )
    try:
        tokens = await service.rotate_refresh_token(refresh_token)
    except InvalidTokenError as exc:
        _clear_refresh_cookie(response, settings)
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_refresh_token",
            detail="Refresh token is invalid, expired or already used",
        ) from exc
    except (EmailNotVerifiedError, InactiveUserError) as exc:
        _clear_refresh_cookie(response, settings)
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="user_inactive",
            detail="User account cannot start a session",
        ) from exc
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return token_response(tokens, settings)


@router.post("/auth/logout", response_model=ActionMessageResponse)
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    await service.logout(request.cookies.get(settings.refresh_cookie_name))
    _clear_refresh_cookie(response, settings)
    return ActionMessageResponse(message="Session revoked")


@router.post("/auth/password-reset/request", response_model=ActionMessageResponse)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_password_reset_request"),
        subject=rate_limit_subject(request, payload.email),
        response=response,
    )
    token = await service.request_password_reset(str(payload.email))
    return ActionMessageResponse(
        message="If the account exists, password reset instructions were created",
        action_token=token if settings.environment.lower() != "production" else None,
    )


@router.post("/auth/password-reset/confirm", response_model=ActionMessageResponse)
async def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
    rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ActionMessageResponse:
    await enforce_rate_limit(
        limiter=rate_limiter,
        policy=auth_action_policy(settings, "auth_password_reset_confirm"),
        subject=rate_limit_subject(request, payload.token),
        response=response,
    )
    try:
        await service.reset_password(payload.token, payload.new_password)
    except InvalidTokenError as exc:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_action_token",
            detail="Password reset token is invalid or expired",
        ) from exc
    return ActionMessageResponse(message="Password updated; existing sessions revoked")


@router.get("/me", response_model=UserResponse)
async def current_user(
    user: Annotated[UserRecord, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserResponse:
    return user_response(user, settings)
