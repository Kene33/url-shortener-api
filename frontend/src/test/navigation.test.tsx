import { render, screen, waitFor } from "@testing-library/react";
import { App } from "@/app/App";

describe("guest navigation", () => {
  it("shows public home actions and hides protected sidebar for guests", async () => {
    window.history.pushState({}, "", "/");
    global.fetch = vi.fn(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return new Response(JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    render(<App />);

    expect(await screen.findByText("Сокращайте ссылки быстро и просто")).toBeInTheDocument();
    expect(screen.getByText("Войти")).toBeInTheDocument();
    expect(screen.getByText("Регистрация")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Мои ссылки")).not.toBeInTheDocument();
    });
  });
});
