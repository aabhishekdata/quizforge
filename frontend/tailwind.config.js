/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: 'rgb(var(--color-ink) / <alpha-value>)',
        board: 'rgb(var(--color-board) / <alpha-value>)',
        card: 'rgb(var(--color-card) / <alpha-value>)',
        rule: 'rgb(var(--color-rule) / <alpha-value>)',
        marker: 'rgb(var(--color-marker) / <alpha-value>)',
        redline: 'rgb(var(--color-redline) / <alpha-value>)',
        mist: 'rgb(var(--color-mist) / <alpha-value>)',
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', 'system-ui', 'sans-serif'],
        body: ['"Inter"', 'system-ui', 'sans-serif'],
        num: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        cardstack: 'var(--shadow-cardstack)',
      },
      keyframes: {
        pop: { '0%': { transform: 'scale(0.6)', opacity: 0 }, '70%': { transform: 'scale(1.08)' }, '100%': { transform: 'scale(1)', opacity: 1 } },
        floatxp: { '0%': { transform: 'translateY(0)', opacity: 1 }, '100%': { transform: 'translateY(-42px)', opacity: 0 } },
      },
      animation: {
        pop: 'pop .25s ease-out',
        floatxp: 'floatxp .9s ease-out forwards',
      },
    },
  },
  plugins: [],
}
