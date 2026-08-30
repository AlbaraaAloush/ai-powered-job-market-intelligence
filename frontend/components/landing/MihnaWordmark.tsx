'use client';

import Image from 'next/image';
import { useLanguage } from '@/lib/i18n';

/* The symbol is rendered in both theme variants so the server and the
   first client render stay identical. CSS selects the visible asset
   from html[data-theme], matching the pre-paint theme initializer. */
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
      >
        <Image
          src="/brand/mihna-mark-light.png"
          alt=""
          width={size}
          height={size}
          loading="eager"
          className="m-brand-mark__image m-brand-mark__image--light"
        />
        <Image
          src="/brand/mihna-mark-dark.png"
          alt=""
          width={size}
          height={size}
          loading="eager"
          className="m-brand-mark__image m-brand-mark__image--dark"
        />
      </span>
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
