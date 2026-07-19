import { expect, test } from "@playwright/test";

test("authenticated admin sees admin navigation on links page", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "admin-token",
        token_type: "bearer",
        expires_in: 3600,
        user: {
          id: 99,
          email: "admin@example.com",
          role: "admin",
          is_admin: true,
          is_active: true,
          email_verified: true,
          display_name: "Admin User",
          avatar_url: null,
          pending_email: null,
          two_factor_enabled: false,
          created_at: "2026-07-16T10:00:00Z",
          updated_at: "2026-07-16T10:00:00Z",
        },
      }),
    });
  });
  await page.route("**/api/v1/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 99,
        email: "admin@example.com",
        role: "admin",
        is_admin: true,
        is_active: true,
        email_verified: true,
        display_name: "Admin User",
        avatar_url: null,
        pending_email: null,
        two_factor_enabled: false,
        created_at: "2026-07-16T10:00:00Z",
        updated_at: "2026-07-16T10:00:00Z",
      }),
    });
  });
  await page.route("**/api/v1/me/preferences", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        theme: "dark",
        language: "ru",
        email_notifications: true,
        system_notifications: true,
        created_at: "2026-07-16T10:00:00Z",
        updated_at: "2026-07-16T10:00:00Z",
      }),
    });
  });
  await page.route("**/api/v1/me/links?*", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [],
        total: 0,
        limit: 8,
        offset: 0,
      }),
    });
  });
  await page.route("**/api/v1/me/folders", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.goto("/links");

  await expect(page.locator("p").filter({ hasText: "Управление" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Админ" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Пользователи" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Глобальные настройки" })).toBeVisible();
});
