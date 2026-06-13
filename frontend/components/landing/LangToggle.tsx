'use client';

import { useLanguage } from '@/lib/i18n';

/* English ↔ Arabic switch. Renders the *opposite* language label
   so the user reads "what they will get" rather than "what they have". */
export function LangToggle() {
  const { lang, toggleLang, t } = useLanguage();
  const next = lang === 'en' ? t('nav.switchToArabic') : t('nav.switchToEnglish');
  return (
    <button
      type="button"
      onClick={toggleLang}
      aria-label={next}
      className="focus-ring inline-flex h-10 min-w-10 items-center justify-center rounded-full px-3 text-xs font-medium tracking-wide active:scale-[0.96]"
      style={{
        color: 'var(--m-ink-2)',
        transition: 'color 180ms cubic-bezier(0.2, 0, 0, 1), background-color 180ms cubic-bezier(0.2, 0, 0, 1), transform 180ms cubic-bezier(0.2, 0, 0, 1)',
        fontFamily: lang === 'en' ? 'var(--m-font-display)' : 'var(--m-font-body)',
      }}
    >
      <span style={{ fontVariationSettings: '"opsz" 14' }}>{next}</span>
    </button>
  );
}
