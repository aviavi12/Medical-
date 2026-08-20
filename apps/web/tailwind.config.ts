import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f14",
        panel: "#121821",
        panel2: "#0f141b",
        border: "#1f2a37",
        accent: "#4f9cf9",
        good: "#2fbf71",
        warn: "#e0a458",
        bad: "#e05a5a",
        muted: "#8b98a5",
      },
    },
  },
  plugins: [],
};

export default config;
