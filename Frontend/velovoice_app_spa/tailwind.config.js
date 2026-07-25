export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        brand: {
          light: '#F7F9FB',
          primary: '#3b82f6',
          surface: '#FFFFFF',
          border: '#E2E8F0',
          text: '#1E293B',
          muted: '#64748B',
        },
      },
    },
  },
  plugins: [],
}
