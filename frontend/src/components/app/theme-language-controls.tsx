import { Languages, Moon, SunMedium } from "lucide-react";
import { useTranslation } from "react-i18next";
import { api } from "@/api/client";
import { useSession } from "@/features/session/session-provider";
import { useTheme } from "@/features/theme/theme-provider";
import type { Language, StoredTheme, ThemePreference } from "@/api/types";

export function ThemeLanguageControls() {
  const { i18n } = useTranslation();
  const { user } = useSession();
  const { language, resolvedTheme, theme, setLanguage, setTheme } = useTheme();

  const sync = (next: { theme?: ThemePreference; language?: Language }) => {
    if (user) {
      const stored: { theme?: StoredTheme; language?: Language } = {
        ...next,
        theme: next.theme === "system" ? resolvedTheme : next.theme,
      };
      void api.updatePreferences(stored).catch(() => undefined);
    }
  };

  const toggleTheme = () => {
    const next = resolvedTheme === "dark" ? "light" : "dark";
    setTheme(next);
    sync({ theme: next });
  };

  const nextLanguage = language === "ru" ? "en" : "ru";

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        className="pill"
        onClick={() => {
          setLanguage(nextLanguage);
          void i18n.changeLanguage(nextLanguage);
          sync({ language: nextLanguage });
        }}
      >
        <Languages className="h-3.5 w-3.5" />
        <span>{language.toUpperCase()}</span>
      </button>
      <button
        type="button"
        className="pill"
        onClick={toggleTheme}
        aria-label={`Switch theme from ${theme}`}
      >
        {resolvedTheme === "dark" ? <SunMedium className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}
