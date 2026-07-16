from urllib.parse import urlsplit

from pydantic import HttpUrl, TypeAdapter

http_url_adapter = TypeAdapter(HttpUrl)


def add_default_scheme(value: str) -> str:
    """Treat a bare host entered by a user as an HTTPS URL."""
    candidate = value.strip()
    if not candidate.startswith("//") and not urlsplit(candidate).scheme:
        return f"https://{candidate}"
    return candidate


def normalize_url(value: str) -> str:
    return str(http_url_adapter.validate_python(add_default_scheme(value)))
