from ipaddress import ip_address
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
)

from app.utils.urls import add_default_scheme, http_url_adapter, normalize_url

MAX_URL_LENGTH = 2048
SHORTCODE_PATTERN = r"^[A-Za-z0-9]+$"


class CreateLinkRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"url": "google.com"}]},
    )

    url: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_URL_LENGTH,
            description=(
                "Целевой HTTP/HTTPS URL. Для домена без схемы автоматически "
                "используется HTTPS."
            ),
            examples=["google.com", "https://example.com/long/path"],
        ),
    ]

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        candidate = add_default_scheme(value)
        parsed = http_url_adapter.validate_python(candidate)

        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URL credentials are not allowed")

        hostname = (parsed.host or "").strip("[]").rstrip(".").lower()
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("Local destinations are not allowed")
        try:
            address = ip_address(hostname)
        except ValueError:
            pass
        else:
            if not address.is_global or address.is_multicast or address.is_site_local:
                raise ValueError("Private and reserved IP destinations are not allowed")

        if len(str(parsed)) > MAX_URL_LENGTH:
            raise ValueError(f"URL must not exceed {MAX_URL_LENGTH} characters")
        return str(parsed)

    @property
    def normalized_url(self) -> str:
        return normalize_url(self.url)


class CreateLinkResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "shortcode": "aB3dE7xQ",
                "short_url": "http://localhost:8000/aB3dE7xQ",
                "created": True,
            }
        }
    )

    shortcode: Annotated[
        str,
        StringConstraints(min_length=6, max_length=32, pattern=SHORTCODE_PATTERN),
        Field(description="Зарезервированный код короткой ссылки"),
    ]
    short_url: Annotated[HttpUrl, Field(description="Готовая короткая ссылка")]
    created: Annotated[
        bool,
        Field(description="true для новой ссылки; false при повторном гостевом URL"),
    ]


class ErrorResponse(BaseModel):
    code: Literal[
        "link_not_found",
        "link_disabled",
        "storage_unavailable",
        "shortcode_unavailable",
    ]
    detail: Annotated[str, Field(description="Человекочитаемое описание ошибки")]


class ValidationErrorResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "validation_error",
                "detail": "Request validation failed",
                "errors": [
                    {
                        "loc": ["body", "url"],
                        "msg": "URL input should be a valid URL",
                        "type": "url_parsing",
                    }
                ],
            }
        }
    )

    code: Literal["validation_error"]
    detail: str
    errors: list[dict[str, Any]]


class LivenessResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"status": "ok"}})

    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"status": "ok", "database": "up", "cache": "up"},
                {"status": "degraded", "database": "up", "cache": "down"},
            ]
        }
    )

    status: Literal["ok", "degraded", "unavailable"]
    database: Literal["up", "down"]
    cache: Literal["up", "down", "unknown"]
