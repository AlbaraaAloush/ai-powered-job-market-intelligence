'use client';

import Link from 'next/link';
import { useLanguage } from '@/lib/i18n';
import { Reveal } from './Reveal';

/* Drenched footer with the primary color carried across the
   surface. A compact navigation grid follows the giant wordmark,
   and a hairline-separated lower band for legal + institution copy. */
export function Footer() {
  const { t, dir } = useLanguage();

  return (
    <footer
      className="m-grain relative isolate overflow-hidden"
      style={{
        background: 'var(--m-primary)',
        color: 'var(--m-on-primary)',
        direction: dir,
      }}
    >
      <div className="mx-auto w-full max-w-[1280px] px-5 pt-20 md:px-8 md:pt-32">
        <Reveal>
          <div className="m-footer-brand">
            <div className="m-footer-wordmark-shell">
              <div className="m-display m-footer-wordmark">{t('nav.brand')}</div>
            </div>
            <p className="m-footer-tagline">{t('mihna.footerTagline')}</p>
          </div>
        </Reveal>

        <hr
          className="mt-16 md:mt-24"
          style={{
            border: 0,
            height: 1,
            background: 'color-mix(in oklch, var(--m-on-primary) 18%, transparent)',
          }}
        />

        <div className="grid grid-cols-2 gap-6 py-12 md:gap-10 md:py-16">
          {/* Product links */}
          <Reveal className="col-span-1">
            <FooterTitle>{t('mihna.footerProductTitle')}</FooterTitle>
            <ul className="mt-5 space-y-3 text-[15px]">
              <li>
                <Link href="/app" className="m-link" style={{ color: 'var(--m-on-primary)' }}>
                  {t('mihna.footerLinkDashboard')}
                </Link>
              </li>
              <li>
                <Link href="/app/chat" className="m-link" style={{ color: 'var(--m-on-primary)' }}>
                  {t('mihna.footerLinkChat')}
                </Link>
              </li>
              <li>
                <a href="#features" className="m-link" style={{ color: 'var(--m-on-primary)' }}>
                  {t('mihna.footerLinkFeatures')}
                </a>
              </li>
            </ul>
          </Reveal>

          {/* About */}
          <Reveal delay={0.06} className="col-span-1">
            <FooterTitle>{t('mihna.footerCompanyTitle')}</FooterTitle>
            <ul className="mt-5 space-y-3 text-[15px]">
              <li>
                <a href="#team" className="m-link" style={{ color: 'var(--m-on-primary)' }}>
                  {t('mihna.footerLinkTeam')}
                </a>
              </li>
              <li>
                <a href="#faq" className="m-link" style={{ color: 'var(--m-on-primary)' }}>
                  {t('mihna.footerLinkFaq')}
                </a>
              </li>
            </ul>
          </Reveal>
        </div>

        <hr
          style={{
            border: 0,
            height: 1,
            background: 'color-mix(in oklch, var(--m-on-primary) 18%, transparent)',
          }}
        />

        <div
          className="flex flex-col gap-3 py-8 text-[13px] sm:flex-row sm:items-center sm:justify-between"
          style={{
            color: 'color-mix(in oklch, var(--m-on-primary) 70%, transparent)',
          }}
        >
          <span className="nums">{t('mihna.footerRights')}</span>
          <span>{t('mihna.footerInstitution')}</span>
        </div>
      </div>
    </footer>
  );
}

function FooterTitle({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="m-eyebrow"
      style={{
        color: 'color-mix(in oklch, var(--m-on-primary) 60%, transparent)',
      }}
    >
      {children}
    </div>
  );
}
