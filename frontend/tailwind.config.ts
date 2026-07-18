import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── SmartCycle Premium Dark Palette ──
        surface: {
          darkest: "#06060c",
          deeper:  "#0a0a14",
          deep:    "#0f0f1e",
          DEFAULT: "#141428",
          raised:  "#1a1a33",
          overlay: "#1e1e3a",
          border:  "#1e2948",
          ring:    "#263355",
        },
        neon: {
          cyan:    "#00d4ff",
          blue:    "#3b82f6",
          purple:  "#8b5cf6",
          green:   "#10b981",
          gold:    "#f59e0b",
          red:     "#ef4444",
          pink:    "#ec4899",
        },
        text: {
          primary:   "#e2e8f0",
          secondary: "#94a3b8",
          tertiary:  "#64748b",
          inverse:   "#0a0a14",
        },
        brand: {
          50:  "#eef2ff",
          100: "#e0e7ff",
          200: "#c7d2fe",
          300: "#a5b4fc",
          400: "#818cf8",
          500: "#6366f1",
          600: "#4f46e5",
          700: "#4338ca",
          800: "#3730a3",
          900: "#312e81",
          950: "#1e1b4b",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "Noto Sans SC",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        display: ["Inter", "Noto Sans SC", "system-ui", "sans-serif"],
      },
      fontSize: {
        "2xs": ["0.625rem", { lineHeight: "0.875rem" }],
      },
      animation: {
        "fade-in":       "fadeIn 0.4s ease-out",
        "slide-up":      "slideUp 0.4s ease-out",
        "slide-right":   "slideRight 0.3s ease-out",
        "pulse-neon":    "pulseNeon 2s ease-in-out infinite",
        "glow":          "glow 2s ease-in-out infinite alternate",
        "spin-slow":     "spin 8s linear infinite",
        "float":         "float 6s ease-in-out infinite",
        "compliance-pass": "compliancePass 0.6s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%":   { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideRight: {
          "0%":   { opacity: "0", transform: "translateX(-8px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        pulseNeon: {
          "0%, 100%": { boxShadow: "0 0 4px rgba(0, 212, 255, 0.3)" },
          "50%":      { boxShadow: "0 0 16px rgba(0, 212, 255, 0.6)" },
        },
        glow: {
          "0%":   { filter: "drop-shadow(0 0 2px rgba(0, 212, 255, 0.4))" },
          "100%": { filter: "drop-shadow(0 0 8px rgba(0, 212, 255, 0.8))" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%":      { transform: "translateY(-8px)" },
        },
        compliancePass: {
          "0%":   { transform: "scale(0.8)", opacity: "0" },
          "60%":  { transform: "scale(1.1)", opacity: "1" },
          "100%": { transform: "scale(1)",   opacity: "1" },
        },
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(30, 41, 72, 0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(30, 41, 72, 0.15) 1px, transparent 1px)",
        "noise-pattern":
          "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.02'/%3E%3C/svg%3E\")",
      },
      backgroundSize: {
        "grid-sm": "20px 20px",
      },
      boxShadow: {
        "neon-cyan":   "0 0 12px rgba(0, 212, 255, 0.3), 0 0 2px rgba(0, 212, 255, 0.15)",
        "neon-green":  "0 0 12px rgba(16, 185, 129, 0.3), 0 0 2px rgba(16, 185, 129, 0.15)",
        "neon-purple": "0 0 12px rgba(139, 92, 246, 0.3), 0 0 2px rgba(139, 92, 246, 0.15)",
        "neon-red":    "0 0 12px rgba(239, 68, 68, 0.3), 0 0 2px rgba(239, 68, 68, 0.15)",
        "inner-glow":  "inset 0 1px 0 0 rgba(255,255,255,0.05)",
        card: "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        elevated:
          "0 4px 16px rgba(0,0,0,0.5), 0 0 0 1px rgba(30, 41, 72, 0.4)",
      },
      borderRadius: {
        "4xl": "2rem",
      },
    },
  },
  plugins: [],
};

export default config;
