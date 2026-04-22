import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: 'var(--color-primary)',
          light: 'rgba(99,102,241,0.15)',
          dark: 'var(--color-primary-dark)',
        },
        nemo: '#10b981',
        secondary: '#9c27b0',
        dark: {
          DEFAULT: '#121212',
          surface: '#1e1e2e',
        },
        success: '#4caf50',
        warning: '#ff9800',
        danger: {
          DEFAULT: '#f44336',
          text: '#ef5350',
          cost: '#ff7043',
        },
        text: {
          DEFAULT: 'var(--color-text)',
          secondary: 'var(--color-text-secondary)',
          muted: 'var(--color-text-muted)',
          label: 'var(--color-text-secondary)',
        },
        bg: {
          DEFAULT: 'var(--color-bg)',
          surface: 'var(--color-bg-surface)',
          hover: 'var(--color-bg-hover)',
          tag: 'var(--color-bg-hover)',
          input: 'var(--color-bg-input)',
          muted: 'var(--color-bg-hover)',
        },
        border: {
          DEFAULT: 'var(--color-border)',
          input: 'var(--color-border-input)',
          delete: '#5c2020',
        },
      },
      fontFamily: {
        sans: ['Pretendard', 'sans-serif'],
      },
      borderRadius: {
        badge: '10px',
      },
      boxShadow: {
        card: '0 4px 20px rgba(0,0,0,0.4)',
        bubble: '0 1px 4px rgba(0,0,0,0.3)',
        glow: '0 0 15px rgba(249,115,22,0.3)',
      },
      keyframes: {
        'slide-in': {
          '0%': { opacity: '0', transform: 'translateX(100%)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'slide-in-left': {
          '0%': { opacity: '0', transform: 'translateX(-100%)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(-8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateX(-50%) translateY(0)' },
          '15%': { opacity: '1', transform: 'translateX(-50%) translateY(8px)' },
          '70%': { opacity: '1', transform: 'translateX(-50%) translateY(8px)' },
          '100%': { opacity: '0', transform: 'translateX(-50%) translateY(24px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% center' },
          '100%': { backgroundPosition: '200% center' },
        },
      },
      animation: {
        'slide-in': 'slide-in 0.25s ease-out',
        'slide-in-left': 'slide-in-left 0.25s ease-out',
        'fade-in': 'fade-in 0.3s ease-out',
        'slide-up': 'slide-up 3s ease-out forwards',
        shimmer: 'shimmer 2s linear infinite',
      },
    },
  },
  plugins: [],
};

export default config;
