/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        desk: {
          950: '#12181B',
          900: '#1A2226',
          800: '#222C31',
        },
        paper: {
          50: '#EFEAE0',
          100: '#E5DFD3',
          200: '#D6CDBA',
          800: '#3D3428',
          900: '#261F16',
        },
        ink: {
          800: '#1F2A2E',
          700: '#2D3D43',
          600: '#435860',
          300: '#94A8B0',
          100: '#D8E2E6',
        },
        verdigris: {
          500: '#4F7C71',
          400: '#64978B',
          600: '#3C6158',
        },
        stamp: {
          red: '#A63D2F',     // HIGH - oxblood
          amber: '#B08A3E',   // MEDIUM - muted brass
          slate: '#6B7280',   // LOW - quiet slate
          ghost: '#8A8378',   // INSUFFICIENT EVIDENCE - smudged ghost
        }
      },
      fontFamily: {
        serif: ['"IBM Plex Serif"', 'Georgia', 'serif'],
        sans: ['"IBM Plex Sans"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}
