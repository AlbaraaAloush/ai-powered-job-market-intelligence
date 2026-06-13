'use client';

import { useEffect, useRef, useState, memo } from 'react';
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

/* Sample readings — illustrative, not authoritative. The component
   self-marks each row with a "Sample" citation so it never poses as
   live ground truth (per the project's data-honesty rule). */
const FACTS_EN: Fact[] = [
  {
    value: 47,
    suffix: '%',
    region: 'QA · DOHA',
    body: 'of senior engineering postings list Arabic proficiency as a hard requirement.',
    source: 'Sample · May 2026 snapshot',
  },
  {
    value: 62,
    suffix: '%',
    region: 'SA · RIYADH',
    body: 'of finance roles in Riyadh require both Arabic and English — the highest mix in the Gulf.',
    source: 'Sample · April 2026 snapshot',
  },
  {
    value: 3.2,
    suffix: '×',
    decimals: 1,
    region: 'QA · DOHA',
    body: 'median salary multiplier between graduate and senior software roles in Doha.',
    source: 'Sample · 2026 cumulative',
  },
  {
    value: 14,
    suffix: 'pp',
    prefix: '+',
    region: 'AE · ABU DHABI',
    body: 'shift toward AI and ML in must-have skills since Q1, the largest jump in the schema.',
    source: 'Sample · Q1 → Q2 2026',
  },
];

const FACTS_AR: Fact[] = [
  {
    value: 47,
    suffix: '٪',
    region: 'الدوحة',
    body: 'من إعلانات الأدوار الهندسية الكبرى تشترط إتقان العربية.',
    source: 'عيّنة · مايو 2026',
  },
  {
    value: 62,
    suffix: '٪',
    region: 'الرياض',
    body: 'من إعلانات التمويل في الرياض تتطلب العربية والإنجليزية معاً — أعلى مزيج في الخليج.',
    source: 'عيّنة · أبريل 2026',
  },
  {
    value: 3.2,
    suffix: '×',
    decimals: 1,
    region: 'الدوحة',
    body: 'مُضاعِف متوسط فئة الراتب من الخريج إلى الكبير في الأدوار البرمجيّة.',
    source: 'عيّنة · 2026 تراكمي',
  },
  {
    value: 14,
    suffix: 'نقطة',
    prefix: '+',
    region: 'أبوظبي',
    body: 'تحوّل نحو الذكاء الاصطناعي ضمن المهارات اللازمة منذ الربع الأول، الأكبر في البنية.',
    source: 'عيّنة · Q1 → Q2 2026',
  },
];

/* Standalone leaf component, isolated from the parent so the rotation
   never re-renders the hero. */
export const DataSpecimen = memo(function DataSpecimen() {
  const { lang, dir } = useLanguage();
  const facts = lang === 'ar' ? FACTS_AR : FACTS_EN;
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
      aria-label="A reading from the data"
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
}: {
  value: number;
  suffix: string;
  prefix?: string;
  decimals?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduce) {
      node.textContent = value.toFixed(decimals);
      return;
    }
    const controls = animate(0, value, {
      duration: 1.6,
      ease: [0.2, 0, 0, 1],
      onUpdate: (v) => {
        node.textContent = v.toFixed(decimals);
      },
    });
    return () => controls.stop();
  }, [value, decimals, reduce]);

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
      <span
        style={{
          fontSize: 'clamp(40px, 5.5vw, 72px)',
          marginLeft: 6,
        }}
      >
        {suffix}
      </span>
    </motion.div>
  );
}
