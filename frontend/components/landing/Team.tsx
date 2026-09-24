'use client';

import { motion, useReducedMotion } from 'motion/react';
import { useLanguage } from '@/lib/i18n';
import { Reveal } from './Reveal';

const SPRING = { type: 'spring' as const, duration: 0.55, bounce: 0 };

const MEMBERS = [
  { id: 'm1', nameKey: 'mihna.teamMember1Name', roleKey: 'mihna.teamMember1Role' },
  { id: 'ummar', nameKey: 'mihna.teamUmmarName' },
  { id: 'm2', nameKey: 'mihna.teamMember2Name' },
  { id: 'm3', nameKey: 'mihna.teamMember3Name' },
  { id: 'm4', nameKey: 'mihna.teamMember4Name' },
  { id: 'm5', nameKey: 'mihna.teamMember5Name' },
];

/* Stripped-down team band: portraits and concise identity copy. The
   composition is the content; spacing and the surface tint mark the section. */
export function Team() {
  const { t, lang } = useLanguage();

  return (
    <section
      id="team"
      className="m-section-tight relative"
      style={{ background: 'var(--m-surface)' }}
    >
      <div className="mx-auto w-full max-w-[1280px] px-5 md:px-8">
        <Reveal>
          <h2
            className="m-display mb-14 md:mb-20"
            style={{
              fontSize: 'clamp(36px, 5.2vw, 64px)',
              lineHeight: 1.02,
              color: 'var(--m-ink)',
              fontVariationSettings: '"opsz" 60, "wght" 400',
            }}
          >
            {t('mihna.teamTitle')}
          </h2>
        </Reveal>
        <div className="grid grid-cols-2 gap-x-4 gap-y-12 sm:grid-cols-3 lg:grid-cols-6 md:gap-x-6">
          {MEMBERS.map((m, i) => {
            const name = t(m.nameKey);
            const role = lang === 'en' && m.roleKey ? t(m.roleKey) : undefined;
            return <PortraitCard key={m.id} name={name} role={role} index={i} />;
          })}
        </div>
      </div>
    </section>
  );
}

function PortraitCard({ name, role, index }: { name: string; role?: string; index: number }) {
  const reduce = useReducedMotion();
  const initial = getInitial(name);

  return (
    <motion.figure
      initial={reduce ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ ...SPRING, delay: 0.06 * index }}
      className="group flex flex-col items-center text-center"
    >
      <div
        className="relative inline-flex h-[88px] w-[88px] items-center justify-center rounded-full transition-transform duration-500 group-hover:scale-[1.03] md:h-[112px] md:w-[112px]"
        style={{
          background: 'var(--m-bg)',
          border: '1px solid var(--m-line-strong)',
          transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
          boxShadow:
            '0 1px 0 color-mix(in oklch, var(--m-ink) 4%, transparent), 0 14px 30px -18px color-mix(in oklch, var(--m-ink) 25%, transparent)',
        }}
      >
        {/* Concentric inner ring — appears on hover */}
        <span
          aria-hidden
          className="pointer-events-none absolute inset-1.5 rounded-full opacity-0 transition-opacity duration-500 group-hover:opacity-100"
          style={{
            border: '1px solid var(--m-line)',
            transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
          }}
        />
        <span
          aria-hidden
          className="m-display select-none"
          style={{
            fontSize: 38,
            color: 'var(--m-ink)',
            fontVariationSettings: '"opsz" 60, "wght" 500, "SOFT" 50',
            letterSpacing: '-0.02em',
          }}
        >
          {initial}
        </span>
      </div>

      <figcaption
        className="m-display mt-5 text-[15.5px] leading-tight"
        style={{
          color: 'var(--m-ink)',
          fontVariationSettings: '"opsz" 18, "wght" 500',
        }}
      >
        <span className="block">{name}</span>
        {role ? (
          <span
            className="mt-2 block text-[12px] leading-snug"
            style={{ color: 'var(--m-ink-2)' }}
          >
            {role}
          </span>
        ) : null}
      </figcaption>
    </motion.figure>
  );
}

/* First letter of the first non-honorific word. Handles "Dr." prefix
   gracefully and works for both EN and AR. */
function getInitial(name: string): string {
  const parts = name
    .replace(/^د\.|^Dr\.|^الأستاذ\b/u, '')
    .trim()
    .split(/\s+/);
  const first = parts[0] || name;
  return Array.from(first)[0] ?? '·';
}
