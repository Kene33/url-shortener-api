import asyncio
import re
import sqlite3

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def assert_validation_error(response) -> None:
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert response.json()["detail"] == "Request validation failed"
    assert response.json()["errors"]


@pytest.mark.asyncio
async def test_create_guest_link_returns_201_then_deduplicates_with_200(app_factory):
    async with app_factory() as harness:
        first = await harness.client.post(
            "/api/v1/links",
            json={"url": "  https://Example.COM  "},
        )
        duplicate = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/"},
        )

    assert first.status_code == 201
    assert duplicate.status_code == 200

    first_body = first.json()
    duplicate_body = duplicate.json()
    assert set(first_body) == {"shortcode", "short_url", "created"}
    assert re.fullmatch(r"[A-Za-z0-9]{8}", first_body["shortcode"])
    assert first_body == {
        "shortcode": first_body["shortcode"],
        "short_url": f"https://sho.rt/{first_body['shortcode']}",
        "created": True,
    }
    assert duplicate_body == {**first_body, "created": False}


@pytest.mark.asyncio
async def test_concurrent_guest_requests_share_one_shortcode(app_factory):
    async with app_factory() as harness:
        first, second = await asyncio.gather(
            harness.client.post(
                "/api/v1/links",
                json={"url": "https://example.com/concurrent"},
            ),
            harness.client.post(
                "/api/v1/links",
                json={"url": "https://example.com/concurrent"},
            ),
        )

    assert sorted([first.status_code, second.status_code]) == [200, 201]
    assert first.json()["shortcode"] == second.json()["shortcode"]
    assert {first.json()["created"], second.json()["created"]} == {False, True}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "https://user:secret@example.com/private",
    ],
)
async def test_create_guest_link_rejects_invalid_urls(app_factory, url):
    async with app_factory() as harness:
        response = await harness.client.post("/api/v1/links", json={"url": url})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_create_guest_link_accepts_a_bare_domain_as_https(app_factory):
    async with app_factory() as harness:
        first = await harness.client.post("/api/v1/links", json={"url": "google.com"})
        duplicate = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://google.com/"},
        )
        redirect = await harness.client.get(f"/{first.json()['shortcode']}")

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert first.json()["shortcode"] == duplicate.json()["shortcode"]
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://google.com/"


@pytest.mark.asyncio
async def test_create_guest_link_rejects_urls_over_2048_characters(app_factory):
    oversized_url = "https://example.com/" + ("a" * 2048)

    async with app_factory() as harness:
        response = await harness.client.post(
            "/api/v1/links",
            json={"url": oversized_url},
        )

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_create_guest_link_rejects_extra_json_fields(app_factory):
    async with app_factory() as harness:
        response = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com", "label": "not supported"},
        )

    assert_validation_error(response)
    assert response.json()["errors"] == [
        {
            "loc": ["body", "label"],
            "msg": "Extra inputs are not permitted",
            "type": "extra_forbidden",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/internal",
        "http://api.localhost/internal",
        "http://127.0.0.1/internal",
        "http://10.0.0.1/internal",
        "http://192.0.2.1/documentation",
        "http://224.0.0.1/multicast",
        "http://[ff02::1]/multicast",
        "http://[fec0::1]/site-local",
    ],
)
async def test_create_guest_link_rejects_local_and_non_global_destinations(
    app_factory,
    url,
):
    async with app_factory() as harness:
        response = await harness.client.post("/api/v1/links", json={"url": url})

    assert_validation_error(response)


@pytest.mark.asyncio
async def test_resolve_redirects_temporarily_and_records_access(app_factory):
    async with app_factory() as harness:
        created = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/docs"},
        )
        shortcode = created.json()["shortcode"]

        response = await harness.client.get(f"/{shortcode}")
        stored = await harness.database.get_link_by_shortcode(shortcode)

    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/docs"
    assert stored is not None
    assert stored.access_count == 1
    assert stored.last_accessed_at is not None


@pytest.mark.asyncio
async def test_resolve_unknown_shortcode_returns_404(app_factory):
    async with app_factory() as harness:
        response = await harness.client.get("/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {
        "code": "link_not_found",
        "detail": "Short link not found",
    }


@pytest.mark.asyncio
async def test_stale_redis_value_is_corrected_from_sqlite(app_factory, memory_cache):
    async with app_factory(cache=memory_cache) as harness:
        created = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/source-of-truth"},
        )
        shortcode = created.json()["shortcode"]
        memory_cache.values[shortcode] = "https://attacker.example/poisoned"

        response = await harness.client.get(f"/{shortcode}")

    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com/source-of-truth"
    assert memory_cache.values[shortcode] == "https://example.com/source-of-truth"


@pytest.mark.asyncio
async def test_inactive_link_in_redis_cache_returns_410(app_factory, memory_cache):
    async with app_factory(cache=memory_cache) as harness:
        created = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/disabled"},
        )
        shortcode = created.json()["shortcode"]
        connection = sqlite3.connect(harness.database.database_path)
        try:
            connection.execute(
                "UPDATE links SET is_active = 0 WHERE shortcode = ?",
                (shortcode,),
            )
            connection.commit()
        finally:
            connection.close()

        response = await harness.client.get(f"/{shortcode}")

    assert response.status_code == 410
    assert response.json() == {
        "code": "link_disabled",
        "detail": "Short link is disabled",
    }
    assert shortcode not in memory_cache.values


@pytest.mark.asyncio
async def test_redis_outage_uses_sqlite_and_reports_degraded_health(
    app_factory,
    unavailable_cache,
):
    async with app_factory(cache=unavailable_cache) as harness:
        created = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/fallback"},
        )
        shortcode = created.json()["shortcode"]
        resolved = await harness.client.get(f"/{shortcode}")
        health = await harness.client.get("/health/ready")

    assert created.status_code == 201
    assert resolved.status_code == 307
    assert resolved.headers["location"] == "https://example.com/fallback"
    assert health.status_code == 200
    assert health.json() == {
        "status": "degraded",
        "database": "up",
        "cache": "down",
    }


@pytest.mark.asyncio
async def test_health_endpoints_report_live_and_ready(app_factory):
    async with app_factory() as harness:
        live = await harness.client.get("/health/live")
        ready = await harness.client.get("/health/ready")

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "database": "up", "cache": "up"}


@pytest.mark.asyncio
async def test_readiness_returns_503_when_sqlite_is_unavailable(app_factory):
    class UnavailableDatabase:
        async def ping(self) -> None:
            raise sqlite3.OperationalError("database unavailable")

    async with app_factory() as harness:
        harness.app.state.database = UnavailableDatabase()
        response = await harness.client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "database": "down",
        "cache": "unknown",
    }


@pytest.mark.asyncio
async def test_openapi_declares_all_create_link_outcomes(app_factory):
    async with app_factory() as harness:
        specification = (await harness.client.get("/openapi.json")).json()

    responses = specification["paths"]["/api/v1/links"]["post"]["responses"]
    assert {"200", "201", "409", "422", "503"} <= set(responses)
    ready_responses = specification["paths"]["/health/ready"]["get"]["responses"]
    assert {"200", "503"} <= set(ready_responses)
    redirect_responses = specification["paths"]["/{shortcode}"]["get"]["responses"]
    assert {"307", "404", "410", "422", "503"} <= set(redirect_responses)
    assert "Location" in redirect_responses["307"]["headers"]


def test_settings_reject_invalid_public_base_url():
    with pytest.raises(ValidationError):
        Settings(public_base_url="not-a-url")
