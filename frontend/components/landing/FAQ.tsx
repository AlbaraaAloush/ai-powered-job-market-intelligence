'use client';

import { createContext, ReactNode, use, useId, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useLanguage } from '@/lib/i18n';
import { Reveal } from './Reveal';

const SPRING = { type: 'spring' as const, duration: 0.45, bounce: 0 };

/* ── Compound component context (state lifted to provider) ─────────────── */

type FaqState = { openId: string | null };
type FaqActions = { setOpen: (id: string | null) => void; toggle: (id: string) => void };
type FaqValue = { state: FaqState; actions: FaqActions };

const FaqContext = createContext<FaqValue | null>(null);

function useFaq() {
  const v = use(FaqContext);
  if (!v) throw new Error('FAQ.* must be used inside FAQ.Provider');
  return v;
}

function FaqProvider({ children }: { children: ReactNode }) {
  const [openId, setOpenId] = useState<string | null>(null);
  const value: FaqValue = {
    state: { openId },
    actions: {
      setOpen: setOpenId,
      toggle: (id) => setOpenId((prev) => (prev === id ? null : id)),
    },
  };
  return <FaqContext.Provider value={value}>{children}</FaqContext.Provider>;
}

/* ── Public surface ────────────────────────────────────────────────────── */

const ITEMS: { id: string; qKey: string; aKey: string }[] = [
  { id: 'data',     qKey: 'mihna.faq1Q', aKey: 'mihna.faq1A' },
  { id: 'fanar',    qKey: 'mihna.faq2Q', aKey: 'mihna.faq2A' },
  { id: 'arabic',   qKey: 'mihna.faq3Q', aKey: 'mihna.faq3A' },
  { id: 'coverage', qKey: 'mihna.faq4Q', aKey: 'mihna.faq4A' },
  { id: 'fresh',    qKey: 'mihna.faq5Q', aKey: 'mihna.faq5A' },
  { id: 'salary',   qKey: 'mihna.faq6Q', aKey: 'mihna.faq6A' },
];

export function FAQ() {
  const { t } = useLanguage();

  return (
    <section id="faq" className="m-section relative">
      <div className="mx-auto w-full max-w-[1280px] px-5 md:px-8">
        <div className="grid grid-cols-12 gap-6 md:gap-10">
          <Reveal className="col-span-12 md:col-span-5">
            <h2
              className="m-display"
              style={{
                fontSize: 'clamp(36px, 5.2vw, 64px)',
                lineHeight: 1.02,
                color: 'var(--m-ink)',
                fontVariationSettings: '"opsz" 60, "wght" 400',
              }}
            >
              {t('mihna.faqTitle')}
            </h2>
          </Reveal>

          <div className="col-span-12 md:col-span-7">
            <FaqProvider>
              <ul role="list">
                {ITEMS.map((item, i) => (
                  <FaqItem
                    key={item.id}
                    id={item.id}
                    question={t(item.qKey)}
                    answer={t(item.aKey)}
                    index={i}
                    last={i === ITEMS.length - 1}
                  />
                ))}
              </ul>
            </FaqProvider>
          </div>
        </div>
      </div>
    </section>
  );
}

function FaqItem({
  id,
  question,
  answer,
  index,
  last,
}: {
  id: string;
  question: string;
  answer: string;
  index: number;
  last: boolean;
}) {
  const { state, actions } = useFaq();
  const reduce = useReducedMotion();
  const isOpen = state.openId === id;
  const buttonId = useId();
  const panelId = useId();

  return (
    <motion.li
      initial={reduce ? false : { opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ ...SPRING, delay: 0.04 * index }}
      style={{
        borderTop: '1px solid var(--m-line)',
        borderBottom: last ? '1px solid var(--m-line)' : undefined,
      }}
    >
      <h3>
        <button
          type="button"
          id={buttonId}
          aria-controls={panelId}
          aria-expanded={isOpen}
          onClick={() => actions.toggle(id)}
          className="focus-ring flex w-full items-start justify-between gap-6 py-6 text-start outline-none transition-colors md:py-8"
          style={{ color: 'var(--m-ink)' }}
        >
          <span
            className="m-display flex-1"
            style={{
              fontSize: 'clamp(20px, 2.4vw, 26px)',
              lineHeight: 1.25,
              fontVariationSettings: '"opsz" 30, "wght" 500',
              letterSpacing: '-0.012em',
            }}
          >
            {question}
          </span>
          <PlusGlyph open={isOpen} />
        </button>
      </h3>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            id={panelId}
            role="region"
            aria-labelledby={buttonId}
            initial={reduce ? { height: 'auto', opacity: 1 } : { height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={reduce ? { height: 'auto', opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.4, ease: [0.2, 0, 0, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <div
              className="pb-8 pe-12 text-[15.5px] leading-relaxed md:pe-16"
              style={{ color: 'var(--m-ink-2)', textWrap: 'pretty' }}
            >
              {answer}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

function PlusGlyph({ open }: { open: boolean }) {
  const reduce = useReducedMotion();
  return (
    <span
      aria-hidden
      className="relative mt-2 inline-flex h-6 w-6 shrink-0 items-center justify-center"
      style={{ color: 'var(--m-ink)' }}
    >
      <motion.span
        className="absolute h-px w-3.5"
        style={{ background: 'currentColor' }}
        animate={{ rotate: 0 }}
        transition={{ duration: reduce ? 0 : 0.32, ease: [0.2, 0, 0, 1] }}
      />
      <motion.span
        className="absolute h-px w-3.5"
        style={{ background: 'currentColor' }}
        animate={{ rotate: open ? 0 : 90 }}
        transition={{ duration: reduce ? 0 : 0.32, ease: [0.2, 0, 0, 1] }}
      />
    </span>
  );
}
