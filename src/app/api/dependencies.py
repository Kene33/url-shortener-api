from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import decode_access_token
from app.db.redis.links import LinkCache
from app.db.sql.crud import SQLClient, UserRecord
from app.services.auth import AuthService
from app.services.links import LinkService

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_database(request: Request) -> SQLClient:
    return request.app.state.database


def get_cache(request: Request) -> LinkCache:
    return request.app.state.cache


def get_link_service(request: Request) -> LinkService:
    return request.app.state.link_service


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


async def get_optional_user(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> UserRecord | None:
    authorization = request.headers.get("Authorization")
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    user_id = decode_access_token(token, settings)
    if scheme.lower() != "bearer" or not token or user_id is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_access_token",
            detail="Access token is invalid or expired",
        )
    user = await database.get_user_by_id(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_access_token",
            detail="Access token is invalid or expired",
        )
    return user


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[SQLClient, Depends(get_database)],
) -> UserRecord:
    if credentials is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="authentication_required",
            detail="Authentication is required",
        )
    user_id = decode_access_token(credentials.credentials, settings)
    if credentials.scheme.lower() != "bearer" or user_id is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_access_token",
            detail="Access token is invalid or expired",
        )
    user = await database.get_user_by_id(user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_access_token",
            detail="Access token is invalid or expired",
        )
    return user


async def require_admin(
    user: Annotated[UserRecord, Depends(get_current_user)],
) -> UserRecord:
    if not user.is_admin:
        raise APIError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="admin_required",
            detail="Administrator privileges are required",
        )
    return user
