'use client';

import { createContext, use, useEffect, useState, ReactNode } from 'react';

type Theme = 'dark' | 'light';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'light',
  toggleTheme: () => {},
});

/* SSR + initial client render both produce theme='light' so hydration
   matches. After mount, the effect synchronizes React state with the
   localStorage value the inline script in layout.tsx already applied
   to html[data-theme]. The setState-in-effect pattern is the canonical
   way to sync with browser-only state (per React docs); the lint rule
   is overly broad here, hence the targeted suppression. */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>('light');

  useEffect(() => {
    const stored = window.localStorage.getItem('theme') as Theme | null;
    const initial: Theme = stored === 'dark' || stored === 'light' ? stored : 'light';
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(initial);
    document.documentElement.setAttribute('data-theme', initial);
  }, []);

  function toggleTheme() {
    setTheme(prev => {
      const next: Theme = prev === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      try {
        window.localStorage.setItem('theme', next);
      } catch {
        /* private browsing / quota — fail silently. */
      }
      return next;
    });
  }

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return use(ThemeContext);
}
