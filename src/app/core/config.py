from functools import lru_cache

from pydantic import Field, HttpUrl, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "URL Shortener API"
    environment: str = "development"
    public_base_url: HttpUrl = HttpUrl("http://localhost:8000")
    database_path: str = "data/links.db"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = Field(default=3600, ge=1)
    shortcode_length: int = Field(default=8, ge=6, le=32)
    shortcode_max_attempts: int = Field(default=10, ge=1, le=100)
    auth_secret_key: str = Field(default="development-only-change-me", min_length=24)
    access_token_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_days: int = Field(default=30, ge=1, le=365)
    email_verification_hours: int = Field(default=24, ge=1, le=168)
    password_reset_minutes: int = Field(default=30, ge=5, le=1440)
    admin_emails: list[str] = []
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
    def validate_production_auth_secret(self) -> "Settings":
        if (
            self.environment.lower() == "production"
            and self.auth_secret_key == "development-only-change-me"
        ):
            raise ValueError("AUTH_SECRET_KEY must be changed in production")
        self.admin_emails = [email.strip().lower() for email in self.admin_emails]
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
