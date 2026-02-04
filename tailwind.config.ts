import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        textPrimary: "#FFFFFF",
        textSecondary: "#B3B3BF",
        accentHover: "#60A5FA",
      },
      fontFamily: {
        sans: ["var(--font-manrope)", "sans-serif"],
        logo: ["var(--font-playfair-display)", "serif"],
      },
    },
  },
  plugins: [],
};

export default config;
