import pytest


async def register_verify_login(
    client,
    email: str,
    password: str = "StrongPass123!",
):
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    assert registered.status_code == 201
    verification_token = registered.json()["verification_token"]
    if verification_token:
        verified = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": verification_token},
        )
        assert verified.status_code == 200

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    return registered.json()["user"], login.json()


def bearer(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.asyncio
async def test_registration_login_refresh_and_logout_without_email_verification(app_factory):
    async with app_factory() as harness:
        registered = await harness.client.post(
            "/api/v1/auth/register",
            json={"email": "User@Example.com", "password": "StrongPass123!"},
        )
        assert registered.status_code == 201
        assert registered.json()["user"]["email"] == "user@example.com"
        assert registered.json()["verification_required"] is False
        assert registered.json()["verification_token"] is None

        login = await harness.client.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "StrongPass123!"},
        )
        assert login.status_code == 200

        duplicate = await harness.client.post(
            "/api/v1/auth/register",
            json={"email": "user@example.com", "password": "StrongPass123!"},
        )
        assert duplicate.status_code == 409

        tokens = login.json()
        first_cookie = harness.client.cookies.get("linkcutter_refresh")
        assert first_cookie
        assert "refresh_token" not in tokens

        me = await harness.client.get("/api/v1/me", headers=bearer(tokens))
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"

        refreshed = await harness.client.post("/api/v1/auth/refresh")
        assert refreshed.status_code == 200
        second_cookie = harness.client.cookies.get("linkcutter_refresh")
        assert second_cookie and second_cookie != first_cookie

        logout = await harness.client.post("/api/v1/auth/logout")
        assert logout.status_code == 200
        assert harness.client.cookies.get("linkcutter_refresh") is None

        after_logout = await harness.client.post("/api/v1/auth/refresh")
        assert after_logout.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_changes_password_and_revokes_sessions(app_factory):
    async with app_factory() as harness:
        _, tokens = await register_verify_login(harness.client, "reset@example.com")
        assert harness.client.cookies.get("linkcutter_refresh")

        requested = await harness.client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "reset@example.com"},
        )
        assert requested.status_code == 200
        reset_token = requested.json()["action_token"]

        confirmed = await harness.client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": reset_token, "new_password": "NewStrongPass456!"},
        )
        assert confirmed.status_code == 200

        revoked = await harness.client.post("/api/v1/auth/refresh")
        assert revoked.status_code == 401

        old_login = await harness.client.post(
            "/api/v1/auth/login",
            json={"email": "reset@example.com", "password": "StrongPass123!"},
        )
        assert old_login.status_code == 401
        new_login = await harness.client.post(
            "/api/v1/auth/login",
            json={"email": "reset@example.com", "password": "NewStrongPass456!"},
        )
        assert new_login.status_code == 200
        assert new_login.json()["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_owned_links_reuse_new_statistics_and_immutability(app_factory):
    async with app_factory() as harness:
        _, first_user = await register_verify_login(harness.client, "owner@example.com")
        _, second_user = await register_verify_login(harness.client, "other@example.com")

        folder = await harness.client.post(
            "/api/v1/me/folders",
            headers=bearer(first_user),
            json={"name": "Campaigns", "color": "cyan"},
        )
        folder_id = folder.json()["id"]

        first = await harness.client.post(
            "/api/v1/links",
            headers=bearer(first_user),
            json={
                "url": "example.com/campaign",
                "label": "Campaign A",
                "folder_id": folder_id,
            },
        )
        reused = await harness.client.post(
            "/api/v1/links",
            headers=bearer(first_user),
            json={"url": "https://example.com/campaign", "mode": "reuse"},
        )
        separate = await harness.client.post(
            "/api/v1/links",
            headers=bearer(first_user),
            json={
                "url": "https://example.com/campaign",
                "mode": "new",
                "label": "Campaign B",
            },
        )
        other_owner = await harness.client.post(
            "/api/v1/links",
            headers=bearer(second_user),
            json={"url": "https://example.com/campaign"},
        )

        assert [first.status_code, reused.status_code, separate.status_code] == [201, 200, 201]
        assert reused.json()["shortcode"] == first.json()["shortcode"]
        assert separate.json()["shortcode"] != first.json()["shortcode"]
        assert other_owner.json()["shortcode"] not in {
            first.json()["shortcode"],
            separate.json()["shortcode"],
        }

        shortcode = first.json()["shortcode"]
        redirect = await harness.client.get(f"/{shortcode}")
        assert redirect.status_code == 307

        detail = await harness.client.get(
            f"/api/v1/me/links/{shortcode}",
            headers=bearer(first_user),
        )
        assert detail.status_code == 200
        assert detail.json()["access_count"] == 1
        assert detail.json()["folder_id"] == folder_id

        listing = await harness.client.get(
            f"/api/v1/me/links?q=Campaign&folder_id={folder_id}&sort=access_count_desc",
            headers=bearer(first_user),
        )
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        foreign = await harness.client.get(
            f"/api/v1/me/links/{shortcode}",
            headers=bearer(second_user),
        )
        assert foreign.status_code == 404

        immutable = await harness.client.patch(
            f"/api/v1/me/links/{shortcode}",
            headers=bearer(first_user),
            json={"url": "https://attacker.example"},
        )
        assert immutable.status_code == 422

        disabled = await harness.client.patch(
            f"/api/v1/me/links/{shortcode}",
            headers=bearer(first_user),
            json={"label": "Paused campaign", "is_active": False, "folder_id": None},
        )
        assert disabled.status_code == 200
        assert disabled.json()["is_active"] is False
        assert disabled.json()["folder_id"] is None
        assert (await harness.client.get(f"/{shortcode}")).status_code == 410

        enabled = await harness.client.patch(
            f"/api/v1/me/links/{shortcode}",
            headers=bearer(first_user),
            json={"is_active": True},
        )
        assert enabled.status_code == 200
        assert (await harness.client.get(f"/{shortcode}")).status_code == 307


@pytest.mark.asyncio
async def test_admin_can_manage_users_and_moderate_all_links_and_settings(app_factory):
    async with app_factory() as harness:
        admin_user, admin_tokens = await register_verify_login(
            harness.client,
            "admin@example.com",
        )
        regular_user, regular_tokens = await register_verify_login(
            harness.client,
            "regular@example.com",
        )
        owned = await harness.client.post(
            "/api/v1/links",
            headers=bearer(regular_tokens),
            json={"url": "https://example.com/owned", "label": "Owner label"},
        )
        guest = await harness.client.post(
            "/api/v1/links",
            json={"url": "https://example.com/guest"},
        )

        denied = await harness.client.get(
            "/api/v1/admin/users",
            headers=bearer(regular_tokens),
        )
        unauthenticated = await harness.client.get("/api/v1/admin/users")
        assert unauthenticated.status_code == 401
        assert unauthenticated.json()["code"] == "authentication_required"
        assert denied.status_code == 403
        assert denied.json()["code"] == "admin_required"

        users = await harness.client.get(
            "/api/v1/admin/users",
            headers=bearer(admin_tokens),
        )
        assert users.status_code == 200
        assert users.json()["total"] == 2

        links = await harness.client.get(
            "/api/v1/admin/links",
            headers=bearer(admin_tokens),
        )
        assert links.status_code == 200
        assert links.json()["total"] == 2
        assert {item["shortcode"] for item in links.json()["items"]} == {
            owned.json()["shortcode"],
            guest.json()["shortcode"],
        }

        moderated = await harness.client.patch(
            f"/api/v1/admin/links/{owned.json()['shortcode']}",
            headers=bearer(admin_tokens),
            json={
                "label": "Moderated",
                "is_active": False,
                "category": "abuse",
                "comment": "Confirmed abuse",
                "password_confirmation": "StrongPass123!",
            },
        )
        assert moderated.status_code == 200
        assert moderated.json()["owner_email"] == "regular@example.com"
        assert moderated.json()["is_active"] is False

        rejected_folder_update = await harness.client.patch(
            f"/api/v1/admin/links/{owned.json()['shortcode']}",
            headers=bearer(admin_tokens),
            json={"folder_id": 1},
        )
        assert rejected_folder_update.status_code == 422

        disabled_user = await harness.client.patch(
            f"/api/v1/admin/users/{regular_user['id']}",
            headers=bearer(admin_tokens),
            json={"is_active": False, "password_confirmation": "StrongPass123!"},
        )
        assert disabled_user.status_code == 200
        assert disabled_user.json()["is_active"] is False

        settings_get = await harness.client.get(
            "/api/v1/admin/settings",
            headers=bearer(admin_tokens),
        )
        assert settings_get.status_code == 200

        settings_patch = await harness.client.patch(
            "/api/v1/admin/settings",
            headers=bearer(admin_tokens),
            json={"user_link_retention_days": 730},
        )
        assert settings_patch.status_code == 200
        assert settings_patch.json()["user_link_retention_days"] == 730

        self_demote = await harness.client.patch(
            f"/api/v1/admin/users/{admin_user['id']}",
            headers=bearer(admin_tokens),
            json={"role": "user", "password_confirmation": "StrongPass123!"},
        )
        assert self_demote.status_code == 409
