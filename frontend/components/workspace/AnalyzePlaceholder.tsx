'use client';

import { useLanguage } from '@/lib/i18n';

export function AnalyzePlaceholder() {
  const { lang } = useLanguage();

  return <p>{lang === 'ar' ? 'قريبًا' : 'Coming soon.'}</p>;
}
