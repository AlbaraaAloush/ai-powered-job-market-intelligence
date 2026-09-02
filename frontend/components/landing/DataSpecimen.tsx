'use client';

import { useEffect, useMemo, useRef, useState, memo } from 'react';
import { animate, motion, AnimatePresence, useReducedMotion } from 'motion/react';
import { useLanguage } from '@/lib/i18n';

const SPRING = { type: 'spring' as const, stiffness: 100, damping: 20 };
const ROTATE_MS = 6200;

type Fact = {
  value: number;
  suffix: string;
  prefix?: string;
  decimals?: number;
  region: string;
  body: string;
  source: string;
};

/* Readings calculated from the three English-portal files dated
   12 May 2026 in RAG/data. All four use the same 20,535-row snapshot. */
const FACTS_EN: Fact[] = [
  {
    value: 20535,
    suffix: '',
    region: 'GCC SNAPSHOT',
    body: 'job-posting rows across Qatar, the UAE, and Saudi Arabia.',
    source: 'Bayt.com dataset · 12 May 2026 · n=20,535',
  },
  {
    value: 2413,
    suffix: '',
    region: 'EMPLOYERS',
    body: 'distinct company names represented in the three-country snapshot.',
    source: 'Bayt.com dataset · 12 May 2026 · n=20,535',
  },
  {
    value: 8.7,
    suffix: '%',
    decimals: 1,
    region: 'SALARY DISCLOSURE',
    body: 'of postings disclose a salary range: 1,781 rows in the snapshot.',
    source: 'Bayt.com dataset · 12 May 2026 · n=20,535',
  },
  {
    value: 2644,
    suffix: '',
    region: 'TOP CATEGORY',
    body: 'Engineering postings, the largest category at 12.9% of the snapshot.',
    source: 'Bayt.com dataset · 12 May 2026 · n=20,535',
  },
];

const FACTS_AR: Fact[] = [
  {
    value: 20535,
    suffix: '',
    region: 'لقطة خليجية',
    body: 'صفاً لإعلانات وظائف في قطر والإمارات والسعودية.',
    source: 'العدد ٢٠٬٥٣٥ · ١٢ مايو ٢٠٢٦ · مجموعة بيانات بيت.كوم',
  },
  {
    value: 2413,
    suffix: '',
    region: 'جهات التوظيف',
    body: 'اسماً مميزاً لشركات ممثلة في لقطة الدول الثلاث.',
    source: 'العدد ٢٠٬٥٣٥ · ١٢ مايو ٢٠٢٦ · مجموعة بيانات بيت.كوم',
  },
  {
    value: 8.7,
    suffix: '٪',
    decimals: 1,
    region: 'الإفصاح عن الراتب',
    body: 'من الإعلانات تفصح عن نطاق للراتب، أي ١٬٧٨١ صفاً في اللقطة.',
    source: 'العدد ٢٠٬٥٣٥ · ١٢ مايو ٢٠٢٦ · مجموعة بيانات بيت.كوم',
  },
  {
    value: 2644,
    suffix: '',
    region: 'أكبر فئة',
    body: 'إعلاناً هندسياً، وهي أكبر فئة بنسبة ١٢٫٩٪ من اللقطة.',
    source: 'العدد ٢٠٬٥٣٥ · ١٢ مايو ٢٠٢٦ · مجموعة بيانات بيت.كوم',
  },
];

/* Standalone leaf component, isolated from the parent so the rotation
   never re-renders the hero. */
export const DataSpecimen = memo(function DataSpecimen() {
  const { lang, dir } = useLanguage();
  const facts = lang === 'ar' ? FACTS_AR : FACTS_EN;
  const locale = lang === 'ar' ? 'ar-QA' : 'en-US';
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);

  useEffect(() => {
    if (reduce) return;
    const id = window.setInterval(() => {
      setI((prev) => (prev + 1) % facts.length);
    }, ROTATE_MS);
    return () => window.clearInterval(id);
  }, [reduce, facts.length]);

  const fact = facts[i];

  return (
    <figure
      aria-label={lang === 'ar' ? 'قراءة من البيانات' : 'A reading from the data'}
      className="relative flex h-full min-h-[440px] flex-col justify-between"
    >
      {/* Top meta — index marker stays put; region cycles inside the
         shared specimen block so all changing copy moves as one unit. */}
      <div className="flex items-baseline justify-between">
        <span
          className="m-eyebrow nums"
          dir="ltr"
          style={{ color: 'var(--m-ink-2)' }}
        >
          {String(i + 1).padStart(2, '0')}
          <span style={{ color: 'var(--m-ink-3)' }}>
            {' / '}
            {String(facts.length).padStart(2, '0')}
          </span>
        </span>
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={`region-${i}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={SPRING}
            className="m-eyebrow"
            style={{ color: 'var(--m-ink-2)' }}
          >
            {fact.region}
          </motion.span>
        </AnimatePresence>
      </div>

      {/* The whole specimen (number + sentence + citation) swaps as a
         single keyed motion block so the figure and its caption never
         desync mid-transition. */}
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={`fact-${i}`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={SPRING}
          className="flex flex-1 flex-col"
        >
          <div className="flex flex-1 items-end pt-10">
            <CountedNumber
              value={fact.value}
              suffix={fact.suffix}
              prefix={fact.prefix}
              decimals={fact.decimals}
              locale={locale}
            />
          </div>

          <div className="mt-7 max-w-[420px]">
            <p
              className="m-display"
              style={{
                fontSize: 'clamp(17px, 1.6vw, 19px)',
                lineHeight: 1.4,
                color: 'var(--m-ink)',
                fontVariationSettings: '"opsz" 24, "wght" 400',
                letterSpacing: '-0.01em',
                textWrap: 'pretty',
              }}
            >
              {fact.body}
            </p>
            <p
              className="mt-4 text-[12px] leading-snug"
              style={{ color: 'var(--m-ink-3)' }}
            >
              {fact.source}
            </p>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Hairline progress rule — fills over the rotation interval,
         resets on each new fact via the keyed motion element. */}
      <div className="mt-10 h-px w-full" style={{ background: 'var(--m-line)' }}>
        <motion.div
          key={`progress-${i}`}
          className="h-full"
          style={{
            background: 'var(--m-primary)',
            transformOrigin: dir === 'rtl' ? 'right' : 'left',
          }}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: reduce ? 0 : ROTATE_MS / 1000, ease: 'linear' }}
        />
      </div>
    </figure>
  );
});

/* Number count-up. Mutates DOM via ref instead of React state so the
   parent never re-renders during the animation (per perf guidance). */
function CountedNumber({
  value,
  suffix,
  prefix,
  decimals = 0,
  locale,
}: {
  value: number;
  suffix: string;
  prefix?: string;
  decimals?: number;
  locale: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  const formatter = useMemo(
    () => new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }),
    [decimals, locale],
  );

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduce) {
      node.textContent = formatter.format(value);
      return;
    }
    const controls = animate(0, value, {
      duration: 1.6,
      ease: [0.2, 0, 0, 1],
      onUpdate: (v) => {
        node.textContent = formatter.format(v);
      },
    });
    return () => controls.stop();
  }, [value, reduce, formatter]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={SPRING}
      className="m-display flex items-baseline"
      /* Numeric figure stays LTR even in Arabic context: "62%" not "%62". */
      dir="ltr"
      style={{
        color: 'var(--m-ink)',
        letterSpacing: '-0.045em',
        lineHeight: 0.92,
        fontVariationSettings: '"opsz" 144, "wght" 400, "SOFT" 50',
      }}
    >
      {prefix && (
        <span style={{ fontSize: 'clamp(56px, 8vw, 88px)' }}>{prefix}</span>
      )}
      <span
        ref={ref}
        className="nums"
        style={{ fontSize: 'clamp(96px, 13vw, 168px)' }}
      >
        0
      </span>
      {suffix ? (
        <span
          style={{
            fontSize: 'clamp(40px, 5.5vw, 72px)',
            marginLeft: 6,
          }}
        >
          {suffix}
        </span>
      ) : null}
    </motion.div>
  );
}
