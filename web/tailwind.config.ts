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
          midnight: "#0F0B1A",
          plum: "#1D1630",
          core: "#4C1D95",
          signal: "#6D28D9",
          orchid: "#8B5CF6",
          lilac: "#C4B5FD",
          cloud: "#F3F0FF",
          success: "#10B981",
          warning: "#F59E0B",
          info: "#60A5FA",
          sage: "#8B5CF6",
          sand: "#F3F0FF",
          graphite: "#1D1630",
          canvas: "#F4F1FB",
          mist: "#DED7F6",
          olive: "#6D28D9",
          surface: "#FBFAFF",
          muted: "#6F6682",
        },
      },
      fontFamily: {
        sans: ["Manrope", "Inter", "Geist", "Segoe UI", "Arial", "Helvetica", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(255, 255, 255, 0.04) inset, 0 22px 70px rgba(0, 0, 0, 0.34)",
        panel: "0 1px 0 rgba(255, 255, 255, 0.06) inset, 0 30px 90px rgba(0, 0, 0, 0.46)",
      },
    },
  },
  plugins: [],
};

export default config;
