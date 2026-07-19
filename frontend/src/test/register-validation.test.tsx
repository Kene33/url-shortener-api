import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { App } from "@/app/App";

function mockGuestSession() {
  global.fetch = vi.fn(async (input) => {
    if (String(input).endsWith("/api/v1/auth/refresh")) {
      return new Response(JSON.stringify({ code: "invalid_refresh_token", detail: "No session" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });
    }
    throw new Error(`Unexpected request: ${String(input)}`);
  }) as typeof fetch;
}

describe("registration password validation", () => {
  it("shows the Russian minimum-length message before sending the form", async () => {
    window.history.pushState({}, "", "/register");
    mockGuestSession();
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByPlaceholderText("Пароль"), "123");
    await user.type(screen.getByPlaceholderText("Повторите пароль"), "123");
    await user.click(screen.getByRole("button", { name: "Создать аккаунт" }));

    expect(await screen.findAllByText("Пароль должен содержать минимум 8 символов.")).toHaveLength(2);
  });

  it("shows the English minimum-length message after language switching", async () => {
    window.history.pushState({}, "", "/register");
    mockGuestSession();
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "Сменить язык" }));
    await user.type(screen.getByPlaceholderText("Password"), "123");
    await user.type(screen.getByPlaceholderText("Confirm password"), "123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findAllByText("Password must contain at least 8 characters.")).toHaveLength(2);
  });
});
