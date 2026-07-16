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
  await expect(page.getByText("Сокращайте ссылки быстро и просто")).toBeVisible();
  await page.getByLabel("Switch theme from system").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", /light|dark/);
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
  await expect(page.getByText("Регистрация")).toBeVisible();
});
