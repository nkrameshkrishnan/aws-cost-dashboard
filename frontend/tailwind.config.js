/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary Brand Red - Primary brand color
        brandRed: {
          50: '#FFEBEE',
          100: '#FFCDD2',
          200: '#EF9A9A',
          300: '#E57373',
          400: '#EF5350',
          500: '#F44336',
          600: '#E53935',
          700: '#D71920',
          800: '#C62828',
          900: '#B71C1C',
        },
        // Modern Green - Success States
        modernGreen: {
          50: '#E6FAF3',
          100: '#CCF5E7',
          200: '#99EBCF',
          300: '#66E1B7',
          400: '#33D79F',
          500: '#00CD87',
          600: '#1E975F',
          700: '#178F56',
          800: '#10874D',
          900: '#0A6D41',
        },
        // Modern Red - Error/Failed States
        modernRed: {
          50: '#FFE8E8',
          100: '#FFD1D1',
          200: '#FFA3A3',
          300: '#FF7575',
          400: '#FF4747',
          500: '#FF1919',
          600: '#E04949',
          700: '#D13030',
          800: '#C21717',
          900: '#B01616',
        },
        // Modern Yellow - Warning/Pending States
        modernYellow: {
          50: '#FFFAE6',
          100: '#FFF5CC',
          200: '#FFEB99',
          300: '#FFE166',
          400: '#FFD733',
          500: '#FFCD00',
          600: '#E0BB1F',
          700: '#D1AA00',
          800: '#C29900',
          900: '#B08E00',
        },
        // Modern Teal - Running/Active States
        modernTeal: {
          50: '#E6FAF8',
          100: '#CCF5F1',
          200: '#99EBE3',
          300: '#66E1D5',
          400: '#33D7C7',
          500: '#00CDB9',
          600: '#28AC9D',
          700: '#1F9B8E',
          800: '#168A7F',
          900: '#0A6D64',
        },
        // Modern Gray - Neutral/Cancelled States
        modernGray: {
          50: '#F9FAFB',
          100: '#F3F4F6',
          200: '#E5E7EB',
          300: '#D1D5DB',
          400: '#9CA3AF',
          500: '#6B7280',
          600: '#4B5563',
          700: '#374151',
          800: '#1F2937',
          900: '#111827',
        },
      },
      borderRadius: {
        'card': '12px',
        'button': '10px',
      },
      boxShadow: {
        'card': '0 2px 8px rgba(0, 0, 0, 0.1)',
        'card-hover': '0 4px 12px rgba(0, 0, 0, 0.15)',
        'button': '0 2px 8px rgba(215, 25, 32, 0.2)',
        'button-hover': '0 4px 12px rgba(215, 25, 32, 0.3)',
      },
    },
  },
  plugins: [],
}
