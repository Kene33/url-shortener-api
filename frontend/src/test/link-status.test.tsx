import { render, screen } from "@testing-library/react";
import { App } from "@/app/App";

function sessionResponse() {
  return new Response(
    JSON.stringify({
      access_token: "token-1",
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: 1,
        email: "user@example.com",
        role: "user",
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

function userResponse() {
  return new Response(
    JSON.stringify({
      id: 1,
      email: "user@example.com",
      role: "user",
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

function preferencesResponse() {
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

describe("link status styling", () => {
  it("renders distinct active and inactive status controls", async () => {
    window.history.pushState({}, "", "/links");
    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return sessionResponse();
      }
      if (url.endsWith("/api/v1/me") && !url.endsWith("/api/v1/me/preferences")) {
        return userResponse();
      }
      if (url.endsWith("/api/v1/me/preferences")) {
        return preferencesResponse();
      }
      if (url.includes("/api/v1/me/links?")) {
        return new Response(
          JSON.stringify({
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
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        );
      }
      if (url.endsWith("/api/v1/me/folders")) {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    render(<App />);

    expect(await screen.findByText("Active campaign")).toBeInTheDocument();
    const activeToggle = screen.getByRole("button", { name: "Отключить ссылку" });
    const inactiveToggle = screen.getByRole("button", { name: "Включить ссылку" });

    expect(activeToggle.className).toContain("border-accent/50");
    expect(activeToggle.className).toContain("bg-accent/10");
    expect(activeToggle.className).toContain("text-accent");
    expect(inactiveToggle.className).not.toContain("border-accent/50");
    expect(inactiveToggle.className).toContain("text-subtle");
  });
});
