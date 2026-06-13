'use client';

import { useTheme } from '@/lib/theme';
import { useLanguage } from '@/lib/i18n';

/* Light/dark toggle. Both icons render at all times; visibility is
   driven by the html[data-theme] attribute (set synchronously by the
   inline init script in layout.tsx). This keeps the markup identical
   on server and client during hydration — no flash, no mismatch — and
   the cross-fade is a pure CSS transition.

   Hit area is 40×40 even though the visible target is smaller. */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const { t } = useLanguage();
  const isDark = theme === 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={isDark ? t('nav.light') : t('nav.dark')}
      className="focus-ring m-theme-toggle relative inline-flex h-10 w-10 items-center justify-center rounded-full"
      style={{ color: 'var(--m-ink-2)' }}
      suppressHydrationWarning
    >
      <span className="relative h-4 w-4">
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="m-theme-icon m-theme-icon-sun absolute inset-0"
        >
          <circle cx="8" cy="8" r="3" />
          <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.4 1.4M11.55 11.55l1.4 1.4M3.05 12.95l1.4-1.4M11.55 4.45l1.4-1.4" />
        </svg>
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          width="16"
          height="16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="m-theme-icon m-theme-icon-moon absolute inset-0"
        >
          <path d="M13 9.5A5.5 5.5 0 1 1 6.5 3a4.5 4.5 0 0 0 6.5 6.5z" />
        </svg>
      </span>
    </button>
  );
}
