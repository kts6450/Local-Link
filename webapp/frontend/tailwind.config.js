/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,css}"],
  theme: {
    extend: {
      colors: {
        brand: {
          green: "#1B5E20",
          greenLight: "#2E7D32",
          greenDark: "#14532d",
          blue: "#1976D2",
          orange: "#EA580C",
          cream: "#FAF7F2",
          warm: "#F0EBE3",
          ink: "#1C1917",
          line: "#E8E0D5",
        },
        shop: {
          teal: "#1B5E20",
          tealHover: "#2E7D32",
          tealDark: "#14532d",
          tealLight: "#e8f5e9",
          surface: "#f7faf7",
        },
        hades: {
          bg: "#FAF7F2",
          surface: "#ffffff",
          line: "#E8E0D5",
          gold: "#1B5E20",
          accent: "#2E7D32",
          text: "#1C1917",
          muted: "#6B6560",
          danger: "#dc2626",
          ok: "#15803d",
        },
      },
      fontFamily: {
        sans: ["Pretendard", "system-ui", "sans-serif"],
      },
      fontSize: {
        xs: ["0.8125rem", { lineHeight: "1.5", letterSpacing: "0.005em" }],
        sm: ["0.9375rem", { lineHeight: "1.55", letterSpacing: "0" }],
        base: ["1.0625rem", { lineHeight: "1.7", letterSpacing: "-0.005em" }],
        lg: ["1.1875rem", { lineHeight: "1.6", letterSpacing: "-0.01em" }],
        xl: ["1.4375rem", { lineHeight: "1.45", letterSpacing: "-0.015em" }],
        "2xl": ["1.75rem", { lineHeight: "1.3", letterSpacing: "-0.02em" }],
        "3xl": ["2.25rem", { lineHeight: "1.2", letterSpacing: "-0.025em" }],
        "4xl": ["2.875rem", { lineHeight: "1.1", letterSpacing: "-0.03em" }],
        "5xl": ["3.75rem", { lineHeight: "1.05", letterSpacing: "-0.035em" }],
        "6xl": ["4.75rem", { lineHeight: "1", letterSpacing: "-0.04em" }],
      },
      boxShadow: {
        card: "0 2px 4px rgba(28, 25, 23, 0.04), 0 12px 32px -12px rgba(28, 25, 23, 0.08)",
        "card-hover": "0 6px 16px -4px rgba(28, 25, 23, 0.10), 0 20px 48px -12px rgba(28, 25, 23, 0.18)",
        "header-tight": "0 1px 0 rgba(232, 224, 213, 0.8)",
        soft: "0 1px 3px rgba(28, 25, 23, 0.04)",
      },
      keyframes: {
        pulse_ring: {
          "0%": { transform: "scale(1)", opacity: "0.7" },
          "100%": { transform: "scale(1.6)", opacity: "0" },
        },
        idle_glow: {
          "0%, 100%": { opacity: "0.25" },
          "50%": { opacity: "0.55" },
        },
        wave: {
          "0%, 100%": { transform: "scaleY(0.4)" },
          "50%": { transform: "scaleY(1)" },
        },
      },
      animation: {
        pulse_ring: "pulse_ring 1.5s ease-out infinite",
        idle_glow: "idle_glow 3s ease-in-out infinite",
        wave: "wave 0.9s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
