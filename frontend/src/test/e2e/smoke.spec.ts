import { expect, test } from "@playwright/test";

test("public home toggles theme", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("Сокращайте ссылки без лишних шагов")).toBeVisible();
  await page.getByLabel("Включить темную тему").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", /light|dark/);
});

test("public home switches language and keeps the guest prompt visible", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }),
    });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Сменить язык" }).click();
  await expect(page.getByText("Shorten links without extra steps")).toBeVisible();
  await expect(page.getByText("Keep links in your dashboard")).toBeVisible();
  await expect(page.getByRole("link", { name: "Create account" })).toBeVisible();
});

test("mobile home keeps auth actions visible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }),
    });
  });

  await page.goto("/");
  await expect(page.getByText("Войти")).toBeVisible();
  await expect(page.getByText("Создать аккаунт")).toBeVisible();
});

test("guest navigation to protected pages redirects to login", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }),
    });
  });

  await page.goto("/links");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText("Введите email и пароль.")).toBeVisible();
});

test("mobile 404 page switches between Russian and English", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }),
    });
  });

  await page.goto("/missing-shortcode");
  await expect(page.getByRole("heading", { name: "Страница не найдена" })).toBeVisible();
  await page.getByRole("button", { name: "Сменить язык" }).click();
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await page.getByRole("button", { name: "Switch language" }).click();
  await expect(page.getByRole("heading", { name: "Страница не найдена" })).toBeVisible();
});

test("authenticated links page shows colored active and inactive status controls", async ({ page }) => {
  await page.route("**/api/v1/auth/refresh", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "token-1",
        token_type: "bearer",
        expires_in: 3600,
        user: {
          id: 1,
          email: "user@example.com",
          is_admin: false,
          is_active: true,
          email_verified: true,
          display_name: "Test User",
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
        id: 1,
        email: "user@example.com",
        is_admin: false,
        is_active: true,
        email_verified: true,
        display_name: "Test User",
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
        items: [
          {
            shortcode: "active1",
            url: "https://example.com/active",
            short_url: "http://127.0.0.1:8000/active1",
            label: "Active campaign",
            is_active: true,
            folder_id: null,
            access_count: 4,
            created_at: "2026-07-16T10:00:00Z",
            updated_at: "2026-07-16T10:00:00Z",
            last_accessed_at: null,
            expires_at: null,
          },
          {
            shortcode: "paused1",
            url: "https://example.com/paused",
            short_url: "http://127.0.0.1:8000/paused1",
            label: "Paused campaign",
            is_active: false,
            folder_id: null,
            access_count: 2,
            created_at: "2026-07-16T10:00:00Z",
            updated_at: "2026-07-16T10:00:00Z",
            last_accessed_at: null,
            expires_at: null,
          },
        ],
        total: 2,
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

  const activeToggle = page.getByRole("button", { name: "Отключить ссылку" });
  const inactiveToggle = page.getByRole("button", { name: "Включить ссылку" });
  await expect(page.getByText("Active campaign")).toBeVisible();
  await expect(activeToggle).toHaveClass(/border-accent\/50/);
  await expect(activeToggle).toHaveClass(/bg-accent\/10/);
  await expect(activeToggle).toHaveClass(/text-accent/);
  await expect(inactiveToggle).toHaveClass(/text-subtle/);
});
