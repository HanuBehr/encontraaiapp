import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          sage: "#8FAF9A",
          sand: "#E8E1D8",
          graphite: "#2F3333",
          canvas: "#F7F6F2",
          mist: "#D9DDD6",
          olive: "#B7C3B3",
          surface: "#FFFDF8",
          muted: "#6F7772",
        },
      },
      fontFamily: {
        sans: ["Manrope", "Inter", "Geist", "Segoe UI", "Arial", "Helvetica", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(47, 51, 51, 0.04), 0 18px 44px rgba(47, 51, 51, 0.07)",
        panel: "0 24px 70px rgba(47, 51, 51, 0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
