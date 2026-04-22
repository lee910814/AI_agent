import { create } from 'zustand';

type Theme = 'light' | 'dark';

type ThemeState = {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
};

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  const stored = localStorage.getItem('nemo-theme');
  if (stored === 'dark' || stored === 'light') return stored;
  return 'light';
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: 'light',
  toggleTheme: () =>
    set((s) => {
      const next = s.theme === 'light' ? 'dark' : 'light';
      if (typeof document !== 'undefined') {
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('nemo-theme', next);
      }
      return { theme: next };
    }),
  setTheme: (t) => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', t);
      localStorage.setItem('nemo-theme', t);
    }
    set({ theme: t });
  },
}));

// Initialize theme on module load (client only)
if (typeof window !== 'undefined') {
  const initial = getInitialTheme();
  document.documentElement.setAttribute('data-theme', initial);
  useThemeStore.setState({ theme: initial });
}
