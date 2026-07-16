from fastapi import Request, Response, status

from app.core.config import Settings
from app.core.errors import APIError
from app.core.security import hash_token
from app.services.rate_limit import (
    RateLimitExceededError,
    RateLimiter,
    RateLimitPolicy,
    RateLimitStatus,
)


def guest_link_policy(settings: Settings) -> RateLimitPolicy:
    return RateLimitPolicy(
        scope="guest_link_create",
        limit=settings.guest_link_rate_limit_requests,
        window_seconds=settings.guest_link_rate_limit_window_seconds,
    )


def auth_action_policy(settings: Settings, scope: str) -> RateLimitPolicy:
    return RateLimitPolicy(
        scope=scope,
        limit=settings.auth_action_rate_limit_requests,
        window_seconds=settings.auth_action_rate_limit_window_seconds,
    )


def rate_limit_subject(request: Request, *identifiers: str | int | None) -> str:
    parts = [f"ip:{request_client_ip(request)}"]
    for identifier in identifiers:
        if identifier is None:
            continue
        normalized = str(identifier).strip().lower()
        if normalized:
            parts.append(f"id:{hash_token(normalized)[:16]}")
    return "|".join(parts)


async def enforce_rate_limit(
    *,
    limiter: RateLimiter,
    policy: RateLimitPolicy,
    subject: str,
    response: Response,
) -> None:
    try:
        limit = await limiter.consume(policy, subject)
    except RateLimitExceededError as exc:
        _apply_limit_headers(response, exc.status)
        response.headers["Retry-After"] = str(exc.status.reset_after_seconds)
        raise APIError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="rate_limit_exceeded",
            detail=f"Too many requests; retry in {exc.status.reset_after_seconds} seconds",
        ) from exc
    _apply_limit_headers(response, limit)


def request_client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _apply_limit_headers(response: Response, status_value: RateLimitStatus) -> None:
    response.headers["X-RateLimit-Limit"] = str(status_value.limit)
    response.headers["X-RateLimit-Remaining"] = str(status_value.remaining)
    response.headers["X-RateLimit-Reset"] = str(status_value.reset_after_seconds)
