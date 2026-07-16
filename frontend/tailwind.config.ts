import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        surface: "rgb(var(--surface) / <alpha-value>)",
        panel: "rgb(var(--panel) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        border: "rgb(var(--border) / <alpha-value>)",
        text: "rgb(var(--text) / <alpha-value>)",
        subtle: "rgb(var(--subtle) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        success: "rgb(var(--success) / <alpha-value>)",
        danger: "rgb(var(--danger) / <alpha-value>)",
        warning: "rgb(var(--warning) / <alpha-value>)",
      },
      borderRadius: {
        panel: "8px",
      },
      boxShadow: {
        panel: "0 18px 48px rgba(18, 24, 38, 0.08)",
        dark: "0 18px 48px rgba(0, 0, 0, 0.36)",
      },
      backgroundImage: {
        "grid-light":
          "radial-gradient(circle at top left, rgba(98,72,255,0.08), transparent 24%), linear-gradient(180deg, rgba(255,255,255,0.96), rgba(243,246,255,0.9))",
        "grid-dark":
          "radial-gradient(circle at top left, rgba(114,87,255,0.24), transparent 24%), linear-gradient(180deg, rgba(10,14,24,0.98), rgba(12,17,29,0.96))",
      },
    },
  },
  plugins: [],
};

export default config;
