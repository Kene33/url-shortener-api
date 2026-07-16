import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { App } from "@/app/App";

function guestRefreshResponse() {
  return new Response(
    JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }),
    {
      status: 401,
      headers: { "Content-Type": "application/json" },
    },
  );
}

function authenticatedSessionResponse() {
  return new Response(
    JSON.stringify({
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
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
}

function authenticatedUserResponse() {
  return new Response(
    JSON.stringify({
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
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
}

function authenticatedPreferencesResponse() {
  return new Response(
    JSON.stringify({
      theme: "dark",
      language: "ru",
      email_notifications: true,
      system_notifications: true,
      created_at: "2026-07-16T10:00:00Z",
      updated_at: "2026-07-16T10:00:00Z",
    }),
    {
      status: 200,
      headers: { "Content-Type": "application/json" },
    },
  );
}

describe("home page behavior", () => {
  it("switches guest language to English and persists the selection", async () => {
    window.history.pushState({}, "", "/");
    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return guestRefreshResponse();
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("Сокращайте ссылки без лишних шагов")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Сменить язык" }));

    expect(await screen.findByText("Shorten links without extra steps")).toBeInTheDocument();
    expect(screen.getByText("Create account")).toBeInTheDocument();
    expect(window.localStorage.getItem("linkcutter.preferences")).toContain('"language":"en"');
  });

  it("shows the guest account prompt only for anonymous visitors", async () => {
    window.history.pushState({}, "", "/");
    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return guestRefreshResponse();
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    render(<App />);

    expect(await screen.findByText("Сохраняйте ссылки в кабинете")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Создать аккаунт" })).toBeInTheDocument();
  });

  it("hides the guest account prompt for authenticated users", async () => {
    window.history.pushState({}, "", "/");
    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return authenticatedSessionResponse();
      }
      if (url.endsWith("/api/v1/me") && !url.endsWith("/api/v1/me/preferences")) {
        return authenticatedUserResponse();
      }
      if (url.endsWith("/api/v1/me/preferences")) {
        return authenticatedPreferencesResponse();
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    render(<App />);

    expect(await screen.findByText("Test User")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Сохраняйте ссылки в кабинете")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Ссылки, папки, отчеты и настройки в одном месте.")).toBeInTheDocument();
  });

  it("redirects guests away from protected pages to login", async () => {
    window.history.pushState({}, "", "/links");
    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return guestRefreshResponse();
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    render(<App />);

    expect(await screen.findByText("Вход")).toBeInTheDocument();
    expect(screen.getByText("Введите email и пароль.")).toBeInTheDocument();
  });
});
