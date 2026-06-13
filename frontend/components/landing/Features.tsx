'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'motion/react';
import { useLanguage } from '@/lib/i18n';
import { Reveal } from './Reveal';
import { ReactNode } from 'react';

const SPRING = { type: 'spring' as const, duration: 0.55, bounce: 0 };

type Feature = {
  key: string;
  href: string | null;
  titleKey: string;
  descKey: string;
  ctaKey?: string;
  glyph: ReactNode;
};

/* Six features. The three navigable ones (live dashboard, chat,
   analyze) come first; the remaining three are info-only. Hover
   reveals an arrow + CTA label *only* on navigable items. */
const FEATURES: Feature[] = [
  {
    key: 'live',
    href: '/app',
    titleKey: 'mihna.featLiveTitle',
    descKey: 'mihna.featLiveDesc',
    ctaKey: 'mihna.featLiveCta',
    glyph: <GlyphLive />,
  },
  {
    key: 'chat',
    href: '/app',
    titleKey: 'mihna.featChatTitle',
    descKey: 'mihna.featChatDesc',
    ctaKey: 'mihna.featChatCta',
    glyph: <GlyphChat />,
  },
  {
    key: 'analyze',
    href: '/app/analyze',
    titleKey: 'mihna.featAnalyzeTitle',
    descKey: 'mihna.featAnalyzeDesc',
    ctaKey: 'mihna.featAnalyzeCta',
    glyph: <GlyphAnalyze />,
  },
  {
    key: 'coverage',
    href: null,
    titleKey: 'mihna.featCoverageTitle',
    descKey: 'mihna.featCoverageDesc',
    glyph: <GlyphCoverage />,
  },
  {
    key: 'bench',
    href: null,
    titleKey: 'mihna.featBenchTitle',
    descKey: 'mihna.featBenchDesc',
    glyph: <GlyphBench />,
  },
  {
    key: 'export',
    href: null,
    titleKey: 'mihna.featExportTitle',
    descKey: 'mihna.featExportDesc',
    glyph: <GlyphExport />,
  },
];

export function Features() {
  const { t } = useLanguage();

  return (
    <section id="features" className="m-section relative">
      {/* Header */}
      <div className="mx-auto w-full max-w-[1280px] px-5 md:px-8">
        <div className="grid grid-cols-12 gap-6 md:gap-10">
          <Reveal className="col-span-12">
            <h2
              className="m-display"
              style={{
                fontSize: 'clamp(36px, 5.2vw, 64px)',
                lineHeight: 1.02,
                color: 'var(--m-ink)',
                fontVariationSettings: '"opsz" 60, "wght" 400',
              }}
            >
              {t('mihna.featuresTitle')}
            </h2>
          </Reveal>
        </div>

        {/* Grid */}
        <div
          className="mt-14 grid grid-cols-1 gap-px overflow-hidden rounded-3xl border md:mt-20 md:grid-cols-3"
          style={{
            background: 'var(--m-line)',
            borderColor: 'var(--m-line)',
          }}
        >
          {FEATURES.map((f, i) => (
            <FeatureCell
              key={f.key}
              feature={f}
              title={t(f.titleKey)}
              desc={t(f.descKey)}
              cta={f.ctaKey ? t(f.ctaKey) : undefined}
              index={i}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

function FeatureCell({
  feature,
  title,
  desc,
  cta,
  index,
}: {
  feature: Feature;
  title: string;
  desc: string;
  cta?: string;
  index: number;
}) {
  const reduce = useReducedMotion();
  const { dir } = useLanguage();
  const navigable = feature.href !== null;

  const inner = (
    <motion.article
      initial={reduce ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ ...SPRING, delay: 0.04 * (index % 3) }}
      className="group relative flex h-full min-h-[260px] flex-col justify-between gap-8 p-7 md:p-9"
      style={{ background: 'var(--m-bg)' }}
    >
      {/* Glyph + index marker */}
      <div className="flex items-start justify-between gap-3">
        <div
          aria-hidden
          className="flex h-9 w-9 items-center justify-center rounded-md transition-colors"
          style={{
            background: 'var(--m-primary-soft)',
            color: 'var(--m-primary)',
          }}
        >
          {feature.glyph}
        </div>
        <span
          aria-hidden
          className="m-display nums select-none text-[12px] tracking-wider"
          style={{
            color: 'var(--m-ink-3)',
            fontVariationSettings: '"opsz" 14',
          }}
        >
          {String(index + 1).padStart(2, '0')}
        </span>
      </div>

      <div>
        <h3
          className="m-display"
          style={{
            fontSize: 'clamp(22px, 2.4vw, 28px)',
            lineHeight: 1.18,
            color: 'var(--m-ink)',
            fontVariationSettings: '"opsz" 36, "wght" 500',
          }}
        >
          {title}
        </h3>
        <p
          className="mt-3 text-[14.5px] leading-relaxed"
          style={{ color: 'var(--m-ink-2)', textWrap: 'pretty' }}
        >
          {desc}
        </p>

        {/* Hover-reveal CTA — only on navigable items */}
        {navigable && cta && (
          <div
            className="relative mt-5 inline-flex h-5 items-center text-[13px] font-medium"
            style={{ color: 'var(--m-primary)' }}
            aria-hidden
          >
            <span
              className="opacity-0 transition-all duration-300 group-hover:opacity-100"
              style={{
                transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
                transform: 'translateX(0)',
              }}
            >
              {cta}
            </span>
            <span
              className="ms-1 inline-flex items-center opacity-0 transition-all duration-300 group-hover:translate-x-0 group-hover:opacity-100"
              style={{
                transform: dir === 'rtl' ? 'translateX(8px)' : 'translateX(-8px)',
                transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
              }}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                fill="none"
                style={{ transform: dir === 'rtl' ? 'scaleX(-1)' : undefined }}
              >
                <path d="M3 7H11M11 7L7.5 3.5M11 7L7.5 10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </div>
        )}
      </div>

      {/* Hairline accent rule on the leading edge — appears on hover for navigable */}
      {navigable && (
        <span
          aria-hidden
          className="absolute inset-y-7 start-0 w-px origin-top scale-y-0 transition-transform duration-500 group-hover:scale-y-100"
          style={{
            background: 'var(--m-primary)',
            transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
          }}
        />
      )}
    </motion.article>
  );

  if (navigable && feature.href) {
    return (
      <Link
        href={feature.href}
        aria-label={`${title} — open`}
        className="focus-ring outline-none"
      >
        {inner}
      </Link>
    );
  }
  return inner;
}

/* ── Glyphs — minimal line marks, all on the same 16-grid ──────────────── */
function GlyphLive() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 14V8M7 14V5M11 14V10M15 14V3" />
    </svg>
  );
}
function GlyphChat() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 4h12v8H8l-3 3v-3H3V4z" />
    </svg>
  );
}
function GlyphCoverage() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="9" cy="9" r="6" />
      <path d="M3 9h12M9 3a8 8 0 0 1 0 12M9 3a8 8 0 0 0 0 12" />
    </svg>
  );
}
function GlyphAnalyze() {
  /* Three connected nodes — reads as a graph / dependency map. */
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="4" cy="5" r="1.6" />
      <circle cx="14" cy="6" r="1.6" />
      <circle cx="9" cy="13" r="1.6" />
      <path d="M5.3 5.8l7.4 0.4M5 6.5l3 5M13.3 7.3L10 11.5" />
    </svg>
  );
}
function GlyphBench() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M3 10h5v5H3zM10 5h5v10h-5z" />
    </svg>
  );
}
function GlyphExport() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 3v8M9 3L6 6M9 3l3 3M3 11v3a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-3" />
    </svg>
  );
}
