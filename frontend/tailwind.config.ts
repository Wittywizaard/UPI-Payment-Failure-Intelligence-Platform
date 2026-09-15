import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0C0E12",
          surface: "#15181D",
          "surface-hover": "#1B1F26",
          "surface-raised": "#1E222A",
        },
        border: {
          DEFAULT: "#262B33",
          strong: "#333A45",
        },
        text: {
          primary: "#EDEFF2",
          secondary: "#8B93A1",
          tertiary: "#5B6472",
        },
        success: { DEFAULT: "#22C55E", bg: "#122019" },
        warning: { DEFAULT: "#F59E0B", bg: "#241C0E" },
        critical: { DEFAULT: "#EF4444", bg: "#241213" },
        ai: { DEFAULT: "#7C6FF0", bg: "#1A1830" },
        accent: {
          DEFAULT: "#1FCFC0",
          hover: "#3EE0D2",
          bg: "#0F2422",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "SF Mono",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      borderRadius: {
        card: "12px",
        control: "8px",
      },
    },
  },
  plugins: [],
};

export default config;
