/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: '#F7F5F0', // Màu nền tổng
        primary: '#8B9A84',    // Màu xanh lá trầm (Sidebar active, nút bấm)
        card: '#FFFFFF',       // Nền card trắng
        cardDark: '#D6AFA6',   // Màu hồng/đất cho nút Active
        textMain: '#333333',
        textMuted: '#888888'
      }
    },
  },
  plugins: [],
}