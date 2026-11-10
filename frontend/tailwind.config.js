/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Product palette. Forest carries identity and primary action, ivory is
        // the page surface (warm paper, not clinical white), sage separates
        // quiet sections, gold marks caution that is not an error.
        forest: {
          50: '#F2F6F3',
          100: '#E4EDE7',
          200: '#C9DBD0',
          300: '#A8B9A1',
          400: '#6E8F7B',
          500: '#3F6B54',
          600: '#2C5A44',
          700: '#214E3D',
          800: '#1B4234',
          900: '#173B2E',
          950: '#0E2620',
        },
        sage: {
          100: '#F1F4EE',
          200: '#E8EEE5',
          300: '#D6E0D0',
          400: '#A8B9A1',
          500: '#8A9C83',
          600: '#6E806A',
        },
        ivory: {
          50: '#FBFAF5',
          100: '#F7F6EF',
          200: '#F0F0E7',
          300: '#E4E4D8',
          400: '#D3D4C6',
        },
        gold: {
          50: '#FBF6E9',
          100: '#F7EFD8',
          200: '#EEDFBB',
          300: '#E3CB8F',
          400: '#D9B866',
          500: '#C09B3F',
          700: '#8A6A1E',
          800: '#6B5216',
          900: '#4E3C10',
        },
        ink: {
          300: '#B4B9B3',
          400: '#9AA09A',
          500: '#737A73',
          600: '#5A615A',
          700: '#3E453F',
          800: '#2E3430',
          900: '#252B27',
        },
        danger: {
          50: '#FCF1EF',
          100: '#F7DFDB',
          200: '#EFC6BF',
          300: '#E6A79E',
          500: '#C4432F',
          600: '#A83725',
          700: '#8A2C1D',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'Noto Sans Devanagari',
          'Segoe UI',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
        display: ['Manrope', 'Inter', 'Noto Sans Devanagari', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        card: '0 1px 2px rgba(37, 43, 39, 0.04), 0 1px 3px rgba(37, 43, 39, 0.05)',
        raised: '0 8px 28px -12px rgba(37, 43, 39, 0.18), 0 2px 6px rgba(37, 43, 39, 0.05)',
        header: '0 1px 0 rgba(37, 43, 39, 0.06)',
      },
      borderRadius: {
        card: '1rem',
        field: '0.75rem',
      },
      maxWidth: {
        shell: '80rem',
        prose: '38rem',
      },
      spacing: {
        safe: 'env(safe-area-inset-bottom, 0px)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
