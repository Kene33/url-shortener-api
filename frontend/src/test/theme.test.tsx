import { render, screen } from "@testing-library/react";
import { ThemeProvider, useTheme } from "@/features/theme/theme-provider";

function Consumer() {
  const { resolvedTheme, language } = useTheme();
  return (
    <div>
      <span>{resolvedTheme}</span>
      <span>{language}</span>
    </div>
  );
}

describe("theme preferences", () => {
  it("loads persisted light theme and language", () => {
    window.localStorage.setItem(
      "linkcutter.preferences",
      JSON.stringify({ theme: "light", language: "en" }),
    );

    render(
      <ThemeProvider>
        <Consumer />
      </ThemeProvider>,
    );

    expect(screen.getByText("light")).toBeInTheDocument();
    expect(screen.getByText("en")).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
