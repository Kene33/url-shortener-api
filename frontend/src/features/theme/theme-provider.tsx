import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import type { Language, ThemePreference } from "@/api/types";

const STORAGE_KEY = "linkcutter.preferences";

interface ThemeContextValue {
  theme: ThemePreference;
  language: Language;
  resolvedTheme: "light" | "dark";
  setTheme: (theme: ThemePreference) => void;
  setLanguage: (language: Language) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getStoredPreferences() {
  if (typeof window === "undefined") {
    return { theme: "system" as ThemePreference, language: "ru" as Language };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { theme: "system" as ThemePreference, language: "ru" as Language };
    return JSON.parse(raw) as { theme: ThemePreference; language: Language };
  } catch {
    return { theme: "system" as ThemePreference, language: "ru" as Language };
  }
}

function resolveTheme(theme: ThemePreference) {
  if (theme !== "system") return theme;
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const initial = getStoredPreferences();
  const [theme, setTheme] = useState<ThemePreference>(initial.theme);
  const [language, setLanguage] = useState<Language>(initial.language);
  const resolvedTheme = resolveTheme(theme);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    document.documentElement.classList.toggle("dark", resolvedTheme === "dark");
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme, language }));
  }, [theme, language, resolvedTheme]);

  const value = useMemo(
    () => ({ theme, language, resolvedTheme, setTheme, setLanguage }),
    [theme, language, resolvedTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) throw new Error("useTheme must be used within ThemeProvider");
  return value;
}
