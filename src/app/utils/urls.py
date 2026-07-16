from pydantic import HttpUrl, TypeAdapter

http_url_adapter = TypeAdapter(HttpUrl)


def normalize_url(value: str) -> str:
    return str(http_url_adapter.validate_python(value))
