/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f4f6ff",
          100: "#e6e9ff",
          500: "#5b5bf7",
          600: "#4646d6",
          700: "#3737ab",
        },
      },
    },
  },
  plugins: [],
};
