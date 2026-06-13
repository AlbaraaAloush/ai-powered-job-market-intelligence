'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'motion/react';
import { useLanguage } from '@/lib/i18n';
import { CyclingWord } from './CyclingWord';
import { DataSpecimen } from './DataSpecimen';

const SPRING = { type: 'spring' as const, duration: 0.7, bounce: 0 };

const CYCLING_EN = ['trends', 'skills', 'salaries', 'workforce demand', 'sectors', 'qualifications'];
const CYCLING_AR = ['الاتجاهات', 'المهارات', 'الرواتب', 'الطلب على القوى العاملة', 'القطاعات', 'المؤهّلات'];

export function Hero() {
  const { t, lang } = useLanguage();
  const reduce = useReducedMotion();
  const cycling = lang === 'ar' ? CYCLING_AR : CYCLING_EN;

  return (
    <section
      className="relative overflow-hidden pt-[136px] pb-[clamp(72px,12vw,160px)] sm:pt-[152px]"
      aria-labelledby="hero-title"
    >
      {/* Editorial hairline guides — subtle vertical rules at gutters */}
      <Backdrop />

      <div className="mx-auto grid w-full max-w-[1280px] grid-cols-12 gap-6 px-5 md:gap-10 md:px-8">
        {/* Left column — text */}
        <div className="col-span-12 lg:col-span-7">
          <motion.h1
            id="hero-title"
            initial={reduce ? false : { opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.05 }}
            className="m-display"
            style={{
              fontSize: 'clamp(64px, 13vw, 160px)',
              lineHeight: 0.92,
              letterSpacing: lang === 'ar' ? '0' : '-0.045em',
              color: 'var(--m-ink)',
              fontVariationSettings: lang === 'ar' ? '"wght" 600' : '"opsz" 144, "wght" 400, "SOFT" 50',
              fontWeight: lang === 'ar' ? 600 : 400,
            }}
          >
            {t('nav.brand')}
          </motion.h1>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.22 }}
            className="m-display mt-6 sm:whitespace-nowrap"
            style={{
              fontSize: 'clamp(19px, 2vw, 24px)',
              lineHeight: 1.25,
              color: 'var(--m-ink)',
              fontVariationSettings: lang === 'ar' ? '"wght" 500' : '"opsz" 24, "wght" 400',
              letterSpacing: lang === 'ar' ? '0' : '-0.018em',
            }}
          >
            {t('mihna.heroTagPrefix')}{' '}
            <CyclingWord
              words={cycling}
              color="var(--m-primary)"
            />
            {t('mihna.heroTagSuffix') ? ` ${t('mihna.heroTagSuffix')}` : ''}
          </motion.p>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING, delay: 0.32 }}
            className="mt-9 flex flex-wrap items-center gap-3"
          >
            <Link href="/app" className="m-btn-primary">
              {t('mihna.heroPrimary')}
              <ArrowGlyph />
            </Link>
            <a href="#features" className="m-btn-ghost">
              {t('mihna.heroSecondary')}
            </a>
          </motion.div>
        </div>

        {/* Right column — animated ticker */}
        <motion.div
          initial={reduce ? false : { opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...SPRING, delay: 0.34 }}
          className="col-span-12 lg:col-span-5"
        >
          <DataSpecimen />
        </motion.div>
      </div>
    </section>
  );
}

function Backdrop() {
  return (
    <>
      {/* Atmospheric primary glow — quiet, off-canvas anchor that adds
         depth without competing with the wordmark. */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -left-60 -z-10 h-[560px] w-[760px] rounded-full"
        style={{
          background:
            'radial-gradient(closest-side, var(--m-primary-soft), transparent 65%)',
          filter: 'blur(24px)',
          opacity: 0.7,
        }}
      />
      {/* Warm patina hint — the single point of accent color in the hero */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-24 right-[-180px] -z-10 h-[420px] w-[480px] rounded-full"
        style={{
          background:
            'radial-gradient(closest-side, var(--m-accent-soft), transparent 75%)',
          filter: 'blur(56px)',
          opacity: 0.45,
        }}
      />
    </>
  );
}

function ArrowGlyph() {
  const { dir } = useLanguage();
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden style={{ transform: dir === 'rtl' ? 'scaleX(-1)' : undefined }}>
      <path d="M3 7H11M11 7L7.5 3.5M11 7L7.5 10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
