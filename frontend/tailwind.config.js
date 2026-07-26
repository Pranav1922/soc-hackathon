/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  // Score-bar fill widths are data-driven (nearest twelfth). Safelisting these
  // standard fractional utilities keeps the width in a class, not an inline style.
  safelist: ["w-0", "w-full", ...Array.from({ length: 11 }, (_, i) => `w-${i + 1}/12`)],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Enterprise dark surface ramp + cyan/blue accent.
        surface: {
          950: "#060a13",
          900: "#0a1120",
          800: "#0f172a",
          700: "#1e293b",
        },
        accent: {
          DEFAULT: "#22d3ee", // cyan-400
          soft: "#38bdf8", // sky-400
          deep: "#2563eb", // blue-600
        },
        risk: {
          high: "#f43f5e",
          medium: "#f59e0b",
          low: "#10b981",
        },
      },
      boxShadow: {
        glass: "0 1px 0 0 rgba(255,255,255,0.04) inset, 0 10px 30px -12px rgba(0,0,0,0.6)",
        glow: "0 0 0 1px rgba(34,211,238,0.25), 0 0 24px -6px rgba(34,211,238,0.35)",
        soft: "0 18px 40px -20px rgba(0,0,0,0.65)",
        "glow-lg": "0 0 40px -8px rgba(34,211,238,0.35)",
      },
      backgroundImage: {
        "grid-faint":
          "linear-gradient(rgba(148,163,184,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.06) 1px, transparent 1px)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};
