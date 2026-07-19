import sqlite3

import pytest

from test_accounts import bearer, register_verify_login


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
    b"\x90wS\xde"
    b"\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\x0f\x1e\x8e"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.mark.asyncio
async def test_profile_preferences_folders_notifications_and_export(app_factory):
    async with app_factory() as harness:
        _, tokens = await register_verify_login(harness.client, "profile@example.com")

        folder = await harness.client.post(
            "/api/v1/me/folders",
            headers=bearer(tokens),
            json={"name": "Work", "color": "blue"},
        )
        assert folder.status_code == 201
        folder_id = folder.json()["id"]

        link = await harness.client.post(
            "/api/v1/links",
            headers=bearer(tokens),
            json={
                "url": "https://example.com/exportable",
                "label": "Exportable",
                "folder_id": folder_id,
            },
        )
        assert link.status_code == 201

        profile = await harness.client.patch(
            "/api/v1/me/profile",
            headers=bearer(tokens),
            json={"display_name": "Link Owner", "email": "pending@example.com"},
        )
        assert profile.status_code == 200
        assert profile.json()["display_name"] == "Link Owner"
        assert profile.json()["pending_email"] == "pending@example.com"
        verification_token = profile.json()["verification_token"]

        avatar = await harness.client.post(
            "/api/v1/me/avatar",
            headers=bearer(tokens),
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )
        assert avatar.status_code == 200
        avatar_url = avatar.json()["avatar_url"]
        assert avatar_url is not None
        avatar_read = await harness.client.get(avatar_url.replace("https://sho.rt", ""))
        assert avatar_read.status_code == 200
        assert avatar_read.headers["content-type"] == "image/png"

        preferences = await harness.client.patch(
            "/api/v1/me/preferences",
            headers=bearer(tokens),
            json={"theme": "dark", "language": "en", "email_notifications": False},
        )
        assert preferences.status_code == 200
        assert preferences.json()["theme"] == "dark"
        assert preferences.json()["language"] == "en"
        assert preferences.json()["email_notifications"] is False

        changed_password = await harness.client.post(
            "/api/v1/me/change-password",
            headers=bearer(tokens),
            json={
                "current_password": "StrongPass123!",
                "new_password": "EvenStronger456!",
            },
        )
        assert changed_password.status_code == 200

        notifications = await harness.client.get(
            "/api/v1/me/notifications?unread=true",
            headers=bearer(tokens),
        )
        assert notifications.status_code == 200
        assert notifications.json()["total"] >= 2

        first_notification = notifications.json()["items"][0]["id"]
        read_one = await harness.client.patch(
            f"/api/v1/me/notifications/{first_notification}/read",
            headers=bearer(tokens),
        )
        assert read_one.status_code == 200
        assert read_one.json()["read_at"] is not None

        read_all = await harness.client.post(
            "/api/v1/me/notifications/read-all",
            headers=bearer(tokens),
        )
        assert read_all.status_code == 200

        analytics = await harness.client.get(
            "/api/v1/me/analytics?period=7d&timezone=Europe/Moscow",
            headers=bearer(tokens),
        )
        assert analytics.status_code == 200
        assert analytics.json()["summary"]["active_links"] >= 1

        invalid_timezone = await harness.client.get(
            "/api/v1/me/analytics?period=7d&timezone=Not/A_Timezone",
            headers=bearer(tokens),
        )
        assert invalid_timezone.status_code == 400
        assert invalid_timezone.json()["code"] == "invalid_timezone"

        link_analytics = await harness.client.get(
            f"/api/v1/me/links/{link.json()['shortcode']}/analytics?period=24h&timezone=UTC",
            headers=bearer(tokens),
        )
        assert link_analytics.status_code == 200

        export_response = await harness.client.get(
            "/api/v1/me/export",
            headers=bearer(tokens),
        )
        assert export_response.status_code == 200
        assert export_response.headers["content-disposition"].startswith("attachment;")
        export_body = export_response.json()
        assert export_body["profile"]["display_name"] == "Link Owner"
        assert export_body["preferences"]["theme"] == "dark"
        assert export_body["folders"][0]["id"] == folder_id
        assert export_body["links"][0]["shortcode"] == link.json()["shortcode"]
        assert "password_hash" not in export_response.text

        verify_pending = await harness.client.post(
            "/api/v1/auth/verify-email",
            json={"token": verification_token},
        )
        assert verify_pending.status_code == 200
        assert verify_pending.json()["email"] == "pending@example.com"


@pytest.mark.asyncio
async def test_email_two_factor_flow_and_account_deletion_retention(app_factory):
    async with app_factory() as harness:
        _, tokens = await register_verify_login(harness.client, "secure@example.com")
        created = await harness.client.post(
            "/api/v1/links",
            headers=bearer(tokens),
            json={"url": "https://example.com/retained"},
        )
        shortcode = created.json()["shortcode"]

        enable = await harness.client.post(
            "/api/v1/me/2fa/email/request-enable",
            headers=bearer(tokens),
        )
        assert enable.status_code == 200
        code = enable.json()["debug_code"]
        confirm = await harness.client.post(
            "/api/v1/me/2fa/email/confirm-enable",
            headers=bearer(tokens),
            json={"code": code},
        )
        assert confirm.status_code == 200
        assert confirm.json()["enabled"] is True

        login = await harness.client.post(
            "/api/v1/auth/login",
            json={"email": "secure@example.com", "password": "StrongPass123!"},
        )
        assert login.status_code == 200
        challenge = login.json()
        assert challenge["requires_two_factor"] is True
        verify_2fa = await harness.client.post(
            "/api/v1/auth/2fa/verify",
            json={
                "login_token": challenge["login_token"],
                "code": challenge["debug_code"],
            },
        )
        assert verify_2fa.status_code == 200

        retention = await harness.client.patch(
            "/api/v1/admin/settings",
            headers=bearer(verify_2fa.json()),
            json={"user_link_retention_days": 1},
        )
        assert retention.status_code in {200, 403}

        disable = await harness.client.post(
            "/api/v1/me/2fa/email/disable",
            headers=bearer(verify_2fa.json()),
        )
        assert disable.status_code == 200
        assert disable.json()["enabled"] is False

        deleted = await harness.client.request(
            "DELETE",
            "/api/v1/me",
            headers=bearer(verify_2fa.json()),
            json={"password": "StrongPass123!"},
        )
        assert deleted.status_code == 200

        cannot_login = await harness.client.post(
            "/api/v1/auth/login",
            json={"email": "secure@example.com", "password": "StrongPass123!"},
        )
        assert cannot_login.status_code in {401, 403}

        still_resolves = await harness.client.get(f"/{shortcode}")
        assert still_resolves.status_code == 410

        connection = sqlite3.connect(harness.database.database_path)
        try:
            connection.execute(
                "UPDATE links SET expires_at = '2020-01-01 00:00:00' WHERE shortcode = ?",
                (shortcode,),
            )
            connection.commit()
        finally:
            connection.close()

        expired = await harness.client.get(f"/{shortcode}")
        assert expired.status_code == 410
        assert expired.json()["code"] == "link_disabled"
