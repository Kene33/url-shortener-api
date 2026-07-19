import { render, screen } from "@testing-library/react";
import { App } from "@/app/App";

describe("protected refresh flow", () => {
  it("refreshes once after a 401 and retries the protected request", async () => {
    window.history.pushState({}, "", "/links");
    let refreshCalls = 0;
    let linksCalls = 0;

    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        refreshCalls += 1;
        return new Response(
          JSON.stringify({
            access_token: `token-${refreshCalls}`,
            token_type: "bearer",
            expires_in: 3600,
            user: {
              id: 1,
              email: "user@example.com",
              role: "user",
              is_admin: false,
              is_active: true,
              email_verified: true,
              created_at: "2026-07-16T10:00:00Z",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.endsWith("/api/v1/me/profile")) {
        return new Response(
          JSON.stringify({
            user: {
              id: 1,
              email: "user@example.com",
              role: "user",
              is_admin: false,
              is_active: true,
              email_verified: true,
              created_at: "2026-07-16T10:00:00Z",
            },
            preferences: {
              theme: "dark",
              language: "ru",
              email_notifications: true,
              system_notifications: true,
            },
            two_factor_enabled: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/api/v1/me/links?")) {
        linksCalls += 1;
        if (linksCalls === 1) {
          return new Response(JSON.stringify({ code: "invalid_access_token", detail: "expired" }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({
            items: [
              {
                shortcode: "x1y2z3",
                url: "https://example.com",
                short_url: "http://127.0.0.1:8000/x1y2z3",
                label: "Campaign",
                is_active: true,
                access_count: 12,
                created_at: "2026-07-16T10:00:00Z",
                updated_at: "2026-07-16T10:00:00Z",
                last_accessed_at: null,
              },
            ],
            total: 1,
            limit: 8,
            offset: 0,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
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

    expect(await screen.findByText("Campaign")).toBeInTheDocument();
    expect(refreshCalls).toBe(2);
    expect(linksCalls).toBe(2);
  });
});
