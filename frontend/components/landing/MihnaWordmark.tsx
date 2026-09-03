'use client';

import { useLanguage } from '@/lib/i18n';

/* The mark uses the supplied vector as a CSS mask. This keeps its geometry
   crisp at every size while the surface color follows the active theme. */
export function MihnaWordmark({
  size = 32,
  showWord = true,
}: {
  size?: number;
  showWord?: boolean;
}) {
  const { t, lang } = useLanguage();
  const word = t('nav.brand');
  const isAr = lang === 'ar';
  return (
    <span
      className="inline-flex items-center gap-2 select-none"
      dir={isAr ? 'rtl' : 'ltr'}
      style={{ color: 'var(--m-ink)' }}
    >
      <span
        aria-hidden="true"
        className="m-brand-mark"
        style={{ width: size, height: size }}
      />
      {showWord && (
        <span
          className="m-display"
          style={{
            fontSize: size * (isAr ? 0.7 : 0.62),
            lineHeight: 1,
            fontWeight: isAr ? 600 : 500,
            letterSpacing: isAr ? '0' : '-0.025em',
            fontVariationSettings: isAr ? '"wght" 600' : '"opsz" 24',
          }}
        >
          {word}
        </span>
      )}
    </span>
  );
}
