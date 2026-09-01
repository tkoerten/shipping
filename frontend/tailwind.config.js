/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // High-contrast warehouse palette.
        ink: "#0b0f14",
        panel: "#141a22",
        panel2: "#1c242e",
        edge: "#2b3644",
        accent: "#39d98a",
        accent2: "#4aa8ff",
        warn: "#ffb020",
        danger: "#ff5c5c",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
