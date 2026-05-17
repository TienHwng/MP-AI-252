/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: '#F8F5E9', // Beige nhạt - Màu nền tổng
        primary: '#3A7D44',    // Green đậm - Màu chính (Sidebar active, nút bấm)
        primaryLight: '#9DC08B', // Light Green - Màu phụ
        accent: '#DF6D14',     // Orange - Màu nhấn
        card: '#FFFFFF',       // Nền card trắng
        cardDark: '#3A7D44',   // Green đậm cho nút Active
        textMain: '#333333',
        textMuted: '#888888'
      }
    },
  },
  plugins: [],
}