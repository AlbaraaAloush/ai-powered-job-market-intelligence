'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'motion/react';
import { useLanguage } from '@/lib/i18n';

const SPRING = { type: 'spring' as const, duration: 0.7, bounce: 0 };

const STAGES = [
  { num: '01', titleKey: 'mihna.analyzeStage1Title', noteKey: 'mihna.analyzeStage1Note' },
  { num: '02', titleKey: 'mihna.analyzeStage2Title', noteKey: 'mihna.analyzeStage2Note' },
  { num: '03', titleKey: 'mihna.analyzeStage3Title', noteKey: 'mihna.analyzeStage3Note' },
];

/* Editorial placeholder for the Analyze workspace. The route exists and
   the chrome matches Mihna so the navigation never feels broken; the
   copy is honest about being in development without aping a fake
   loading-state SaaS skeleton. */
export function AnalyzeContent() {
  const { t, lang, dir } = useLanguage();
  const reduce = useReducedMotion();

  return (
    <section
      className="relative overflow-hidden pt-[136px] pb-[clamp(96px,14vw,200px)] sm:pt-[160px]"
      aria-labelledby="analyze-title"
    >
      {/* Subtle backdrop — primary glow, just enough to anchor the page */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-[-220px] -z-10 h-[520px] w-[700px] rounded-full"
        style={{
          background: 'radial-gradient(closest-side, var(--m-primary-soft), transparent 65%)',
          filter: 'blur(28px)',
          opacity: 0.6,
        }}
      />

      <div className="mx-auto w-full max-w-[1280px] px-5 md:px-8">
        <div className="grid grid-cols-12 gap-8 md:gap-12">
          {/* Left — display copy */}
          <div className="col-span-12 lg:col-span-7">
            <motion.p
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...SPRING, delay: 0.05 }}
              className="m-eyebrow"
            >
              {t('mihna.analyzeEyebrow')}
            </motion.p>

            <motion.h1
              id="analyze-title"
              initial={reduce ? false : { opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...SPRING, delay: 0.12 }}
              className="m-display mt-5"
              style={{
                fontSize: 'clamp(40px, 7vw, 84px)',
                lineHeight: 1.02,
                color: 'var(--m-ink)',
                fontVariationSettings:
                  lang === 'ar'
                    ? '"wght" 600'
                    : '"opsz" 96, "wght" 400, "SOFT" 50',
                letterSpacing: lang === 'ar' ? '0' : '-0.04em',
                fontWeight: lang === 'ar' ? 600 : 400,
                textWrap: 'balance',
              }}
            >
              {t('mihna.analyzeTitle')}
            </motion.h1>

            <motion.p
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...SPRING, delay: 0.22 }}
              className="mt-7 max-w-[560px] text-[16px] leading-relaxed"
              style={{ color: 'var(--m-ink-2)', textWrap: 'pretty' }}
            >
              {t('mihna.analyzeBody')}
            </motion.p>

            <motion.div
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...SPRING, delay: 0.32 }}
              className="mt-9 flex flex-wrap items-center gap-3"
            >
              <Link href="/app" className="m-btn-primary">
                {t('nav.cta')}
                <ArrowGlyph dir={dir} />
              </Link>
              <Link href="/" className="m-btn-ghost">
                {t('mihna.analyzeBackHome')}
              </Link>
            </motion.div>
          </div>

          {/* Right — staged roadmap, hairline-divided */}
          <motion.ul
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ ...SPRING, delay: 0.4 }}
            className="col-span-12 self-end lg:col-span-5 lg:pt-16"
            style={{
              borderTop: '1px solid var(--m-line)',
              borderBottom: '1px solid var(--m-line)',
            }}
          >
            {STAGES.map((stage, i) => (
              <motion.li
                key={stage.num}
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ ...SPRING, delay: 0.42 + i * 0.08 }}
                className="flex items-baseline gap-6 py-6"
                style={{
                  borderTop: i === 0 ? undefined : '1px solid var(--m-line)',
                }}
              >
                <span
                  className="m-eyebrow nums"
                  dir="ltr"
                  style={{ color: 'var(--m-ink-3)', minWidth: 32 }}
                >
                  {stage.num}
                </span>
                <div className="flex-1">
                  <div
                    className="m-display"
                    style={{
                      fontSize: '18px',
                      lineHeight: 1.3,
                      color: 'var(--m-ink)',
                      fontVariationSettings: '"opsz" 24, "wght" 500',
                      letterSpacing: '-0.008em',
                    }}
                  >
                    {t(stage.titleKey)}
                  </div>
                  <div
                    className="mt-1.5 text-[13px] leading-snug"
                    style={{ color: 'var(--m-ink-2)' }}
                  >
                    {t(stage.noteKey)}
                  </div>
                </div>
              </motion.li>
            ))}
          </motion.ul>
        </div>
      </div>
    </section>
  );
}

function ArrowGlyph({ dir }: { dir: 'ltr' | 'rtl' }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden
      style={{ transform: dir === 'rtl' ? 'scaleX(-1)' : undefined }}
    >
      <path
        d="M3 7H11M11 7L7.5 3.5M11 7L7.5 10.5"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
