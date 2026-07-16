import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/app/App";

describe("public shortener", () => {
  it("creates a guest short link and renders the result", async () => {
    window.history.pushState({}, "", "/");
    global.fetch = vi.fn(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/api/v1/auth/refresh")) {
        return new Response(JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (url.endsWith("/api/v1/links") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            shortcode: "abc123",
            short_url: "http://127.0.0.1:8000/abc123",
            created: true,
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      }
      throw new Error(`Unexpected request: ${url}`);
    }) as typeof fetch;

    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByLabelText("URL input"), "example.com");
    await user.click(screen.getByRole("button", { name: "Сократить" }));

    expect(await screen.findByText("http://127.0.0.1:8000/abc123")).toBeInTheDocument();
  });
});
