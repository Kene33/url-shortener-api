import pytest


def bearer(tokens: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def register_verify_login(client, email: str):
    registered = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "StrongPass123!"}
    )
    assert registered.status_code == 201
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "StrongPass123!"}
    )
    assert login.status_code == 200
    return registered.json()["user"], login.json()


@pytest.mark.asyncio
async def test_staff_roles_reports_audit_and_deletion_cancel(app_factory):
    async with app_factory() as harness:
        _, admin_tokens = await register_verify_login(harness.client, "admin@example.com")
        member, member_tokens = await register_verify_login(harness.client, "member@example.com")

        role_change = await harness.client.patch(
            f"/api/v1/admin/users/{member['id']}",
            headers=bearer(admin_tokens),
            json={"role": "moderator", "password_confirmation": "StrongPass123!"},
        )
        assert role_change.status_code == 200
        assert role_change.json()["role"] == "moderator"

        report = await harness.client.post(
            "/api/v1/reports",
            json={
                "email": "reporter@example.com",
                "shortcode": "doesnotexist",
                "category": "spam",
                "comment": "Unwanted advertising link",
            },
        )
        assert report.status_code == 202
        reports = await harness.client.get("/api/v1/admin/reports", headers=bearer(member_tokens))
        assert reports.status_code == 200
        report_id = reports.json()["items"][0]["id"]
        resolved = await harness.client.patch(
            f"/api/v1/admin/reports/{report_id}",
            headers=bearer(member_tokens),
            json={
                "status": "resolved",
                "comment": "Reviewed",
                "password_confirmation": "StrongPass123!",
            },
        )
        assert resolved.status_code == 200

        dashboard = await harness.client.get(
            "/api/v1/admin/dashboard", headers=bearer(member_tokens)
        )
        assert dashboard.status_code == 200
        assert dashboard.json()["reports_total"] == 1
        audit = await harness.client.get("/api/v1/admin/audit-log", headers=bearer(admin_tokens))
        assert audit.status_code == 200
        assert audit.json()["total"] >= 2

        deletion = await harness.client.post(
            "/api/v1/me/deletion/request",
            headers=bearer(member_tokens),
            json={"password_confirmation": "StrongPass123!"},
        )
        assert deletion.status_code == 200
        token = deletion.json()["action_token"]
        assert token
        cancelled = await harness.client.post(
            "/api/v1/auth/cancel-deletion", json={"action_token": token}
        )
        assert cancelled.status_code == 200
