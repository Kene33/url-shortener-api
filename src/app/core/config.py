from functools import lru_cache

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "URL Shortener API"
    environment: str = "development"
    public_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    database_path: str = "data/links.db"
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_prefix: str = "ratelimit"
    guest_link_rate_limit_requests: int = Field(default=30, ge=1, le=10000)
    guest_link_rate_limit_window_seconds: int = Field(default=60, ge=1, le=86400)
    auth_action_rate_limit_requests: int = Field(default=10, ge=1, le=10000)
    auth_action_rate_limit_window_seconds: int = Field(default=300, ge=1, le=86400)
    rate_limit_fail_closed_in_production: bool = True
    cache_ttl_seconds: int = Field(default=3600, ge=1)
    shortcode_length: int = Field(default=8, ge=6, le=32)
    shortcode_max_attempts: int = Field(default=10, ge=1, le=100)
    auth_secret_key: str = Field(default="development-only-change-me", min_length=24)
    access_token_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_days: int = Field(default=30, ge=1, le=365)
    email_verification_hours: int = Field(default=24, ge=1, le=168)
    email_verification_required: bool = False
    password_reset_minutes: int = Field(default=30, ge=5, le=1440)
    avatar_dir: str = "data/avatars"
    refresh_cookie_name: str = "linkcutter_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_domain: str | None = None
    refresh_cookie_path: str = "/api/v1"
    user_link_retention_days_default: int = Field(default=365, ge=1, le=3650)
    email_2fa_code_minutes: int = Field(default=10, ge=1, le=60)
    email_provider_configured: bool = False
    admin_emails: list[str] = []
    demo_seed_password: str | None = None
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_runtime_security(self) -> "Settings":
        environment = self.environment.lower()
        if environment == "production":
            if self.auth_secret_key == "development-only-change-me":
                raise ValueError("AUTH_SECRET_KEY must be changed in production")
            if not self.database_url:
                raise ValueError("DATABASE_URL is required in production")
            if not self.redis_url or self.redis_url.startswith(("redis://localhost", "redis://redis:")):
                raise ValueError("REDIS_URL must point to a shared Redis service in production")
            if self.refresh_cookie_secure is not True:
                raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
            if str(self.public_base_url).lower().startswith("http://"):
                raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
            if any(not origin.lower().startswith("https://") for origin in self.cors_origins):
                raise ValueError("CORS_ORIGINS must contain only HTTPS origins in production")
            if "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must not contain a wildcard in production")
            if self.rate_limit_fail_closed_in_production is not True:
                raise ValueError("Rate limiting must fail closed in production")
        refresh_cookie_samesite = self.refresh_cookie_samesite.lower()
        if refresh_cookie_samesite not in {"lax", "strict", "none"}:
            raise ValueError("REFRESH_COOKIE_SAMESITE must be lax, strict or none")
        if refresh_cookie_samesite == "none" and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE must be true when SameSite=None")
        if self.environment.lower() == "production" and not self.refresh_cookie_secure:
            raise ValueError("REFRESH_COOKIE_SECURE must be true in production")
        self.refresh_cookie_samesite = refresh_cookie_samesite
        self.admin_emails = [email.strip().lower() for email in self.admin_emails]
        return self

    @property
    def debug_tokens_enabled(self) -> bool:
        """Enable fixtures' token shortcuts only in an explicitly isolated test app."""
        return self.environment.lower() == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
