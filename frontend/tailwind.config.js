/** @type {import('tailwindcss').Config} */

/*
 * One palette, one scale, one set of surfaces.
 *
 * The identity colours are the product brief's tokens: forest #173D32 for
 * identity and primary action, sage #A8B98A for supporting surfaces, ivory
 * #F4F0E5 as the page paper, harvest gold #D49A52 for selective attention, ink
 * #202A25 for primary text and #6B756E for secondary text.
 *
 * Two deviations, both measurable rather than aesthetic:
 *   - ink-500 is #626C65, not #6B756E. On the ivory page the specified tone is
 *     4.20:1, below the 4.5:1 floor for body-size text; this is 4.79:1 and
 *     visually the same colour. The specified tone is kept as ink-400 for
 *     large or decorative use.
 *   - Every forest/sage/gold step is generated around the specified anchor, so
 *     `text-sage-400` on `bg-forest-900` stays legible (7.4:1) instead of
 *     relying on one flat swatch.
 */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        forest: {
          50: '#EFF4F1',
          100: '#DCE7E1',
          200: '#BACFC5',
          300: '#8FB2A2',
          400: '#5E8B77',
          500: '#3A6B56',
          600: '#275243',
          700: '#173D32',
          800: '#12332A',
          900: '#0E2821',
          950: '#081A16',
        },
        sage: {
          50: '#F6F8F0',
          100: '#EEF2E2',
          200: '#DFE7CB',
          300: '#C4D1A8',
          400: '#A8B98A',
          500: '#8B9E6C',
          600: '#6E8053',
        },
        ivory: {
          50: '#FBF8F0',
          100: '#F4F0E5',
          200: '#EAE5D5',
          300: '#DED7C4',
          400: '#C9C0AA',
        },
        gold: {
          50: '#FBF3E8',
          100: '#F6E7D2',
          200: '#EDD2AE',
          300: '#DFB57F',
          400: '#D49A52',
          500: '#C4883F',
          600: '#AC7433',
          700: '#8E5D28',
          800: '#714921',
          900: '#57381A',
        },
        ink: {
          300: '#ADB5AE',
          400: '#6B756E',
          500: '#626C65',
          600: '#4E5A53',
          700: '#3B4741',
          800: '#2B3630',
          900: '#202A25',
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
        /* Editorial hero scale: clamped so a 390px phone and a 1600px desktop
           both get a headline that fits its measure without manual breakpoints. */
        hero: ['clamp(2.25rem, 4.4vw + 1rem, 3.75rem)', { lineHeight: '1.05' }],
        section: ['clamp(1.5rem, 1.1vw + 1.15rem, 2rem)', { lineHeight: '1.15' }],
      },
      boxShadow: {
        card: '0 1px 2px rgba(23, 61, 50, 0.05), 0 1px 3px rgba(23, 61, 50, 0.04)',
        raised: '0 18px 40px -24px rgba(23, 61, 50, 0.3), 0 2px 8px rgba(23, 61, 50, 0.06)',
        lift: '0 26px 52px -28px rgba(23, 61, 50, 0.36), 0 6px 16px -10px rgba(23, 61, 50, 0.14)',
        header: '0 1px 0 rgba(23, 61, 50, 0.07)',
        inset: 'inset 0 1px 0 rgba(255, 255, 255, 0.45)',
      },
      borderRadius: {
        card: '1rem',
        panel: '1.375rem',
        field: '0.75rem',
      },
      maxWidth: {
        shell: '80rem',
        prose: '38rem',
      },
      spacing: {
        safe: 'env(safe-area-inset-bottom, 0px)',
      },
      backgroundImage: {
        /* Only where a gradient does work a flat colour cannot: separating the
           hero from the page paper without a hard edge. */
        'ivory-wash': 'linear-gradient(180deg, #FBF8F0 0%, #F4F0E5 62%, #F1EDE0 100%)',
        'forest-depth': 'linear-gradient(158deg, #173D32 0%, #12332A 55%, #0E2821 100%)',
        'sage-fade': 'linear-gradient(180deg, #F6F8F0 0%, #EEF2E2 100%)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(14px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'grow-line': {
          from: { transform: 'scaleX(0)' },
          to: { transform: 'scaleX(1)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.6s cubic-bezier(0.22, 1, 0.36, 1) both',
        'fade-in': 'fade-in 0.45s ease-out both',
        'grow-line': 'grow-line 0.7s cubic-bezier(0.22, 1, 0.36, 1) both',
      },
    },
  },
  plugins: [],
}
