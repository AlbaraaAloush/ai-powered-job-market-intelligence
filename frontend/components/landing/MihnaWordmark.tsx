'use client';

import { useLanguage } from '@/lib/i18n';

/* Brand placeholder mark. Until the user supplies their own logo, the
   wordmark renders as a minimal serif/kufi inscription inside a
   hairline circle — a small instrument-shaped placeholder consistent
   with the editorial register, easy to swap for an SVG later.
   Word switches to "مِهنَة" in Arabic; size of the type tightens
   for the kufi face so heights match optically. */
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
      style={{ color: 'var(--m-ink)' }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 32 32"
        aria-hidden="true"
        className="shrink-0"
      >
        <circle
          cx="16"
          cy="16"
          r="14.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1"
          opacity="0.4"
        />
        {/* Concentric mark — a tiny inscribed circle reads "instrument" */}
        <circle
          cx="16"
          cy="16"
          r="3.2"
          fill="currentColor"
          opacity="0.95"
        />
      </svg>
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
