/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { navy: { 950: "#050b1a", 900: "#08122a", 800: "#0d1b3a", 700: "#14264d", 600: "#1d3563" } },
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], mono: ["JetBrains Mono", "ui-monospace", "monospace"] },
    },
  },
  plugins: [],
};
