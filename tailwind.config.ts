import type { Config } from "tailwindcss";

/**
 * Calm, classic, premium. Warm off-white ground, deep navy ink, muted
 * lavender / dusty blue / soft sage / pale peach for categories, and exactly
 * one strong accent reserved for critical alerts.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#FAF7F2",
        surface: "#FFFFFF",
        ink: { DEFAULT: "#1E2A3A", soft: "#4A5568", faint: "#8A93A0" },
        line: "#E7E1D8",
        lavender: { soft: "#EFECF8", DEFAULT: "#C9C0E4", deep: "#6B5FA0" },
        dusty: { soft: "#E9EFF5", DEFAULT: "#AFC3D6", deep: "#4A6C8C" },
        sage: { soft: "#E9EFE7", DEFAULT: "#B4C7B0", deep: "#4F7050" },
        peach: { soft: "#FBEDE2", DEFAULT: "#EFC9AC", deep: "#A6663A" },
        accent: { DEFAULT: "#B23A2E", soft: "#F7E4E1", deep: "#8B2A20" },
      },
      fontFamily: {
        serif: ["Iowan Old Style", "Palatino Linotype", "Palatino", "Georgia", "serif"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Helvetica", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(30,42,58,0.04), 0 8px 24px -12px rgba(30,42,58,0.12)",
        lift: "0 2px 4px rgba(30,42,58,0.06), 0 18px 40px -20px rgba(30,42,58,0.22)",
      },
      borderRadius: { xl: "14px", "2xl": "18px" },
    },
  },
  plugins: [],
};
export default config;
