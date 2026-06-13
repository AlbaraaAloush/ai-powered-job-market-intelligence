'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion, useScroll, useMotionValueEvent } from 'motion/react';
import { useLanguage } from '@/lib/i18n';
import { MihnaWordmark } from './MihnaWordmark';
import { ThemeToggle } from './ThemeToggle';
import { LangToggle } from './LangToggle';

type ModuleItem = {
  key: 'dashboard' | 'chat' | 'analyze';
  href: string | null;
  titleKey: string;
  subKey: string;
  soon?: boolean;
};

const moduleItems: ModuleItem[] = [
  { key: 'dashboard', href: '/app',         titleKey: 'nav.moduleDashboard', subKey: 'nav.moduleDashboardSub' },
  { key: 'chat',      href: '/app/chat',    titleKey: 'nav.moduleChat',      subKey: 'nav.moduleChatSub' },
  { key: 'analyze',   href: '/app/analyze', titleKey: 'nav.moduleAnalyze',   subKey: 'nav.moduleAnalyzeSub' },
];

export function LandingNav() {
  const { t, dir } = useLanguage();
  const reduce = useReducedMotion();
  const [scrolled, setScrolled] = useState(false);
  const [modulesOpen, setModulesOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const modulesRef = useRef<HTMLLIElement>(null);
  const closeTimer = useRef<number | null>(null);

  const { scrollY } = useScroll();
  useMotionValueEvent(scrollY, 'change', (v) => setScrolled(v > 8));

  /* Close dropdown on outside click + ESC */
  useEffect(() => {
    if (!modulesOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!modulesRef.current?.contains(e.target as Node)) setModulesOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setModulesOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [modulesOpen]);

  /* Lock body scroll when mobile menu is open */
  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [mobileOpen]);

  /* Hover-with-delay so the dropdown doesn't flicker between trigger and panel */
  function openModules() {
    if (closeTimer.current) { window.clearTimeout(closeTimer.current); closeTimer.current = null; }
    setModulesOpen(true);
  }
  function scheduleCloseModules() {
    if (closeTimer.current) window.clearTimeout(closeTimer.current);
    closeTimer.current = window.setTimeout(() => setModulesOpen(false), 120);
  }

  return (
    <header
      className="fixed inset-x-0 top-0 z-50"
      dir="ltr"
    >
      {/* Skip link for keyboard users */}
      <a
        href="#main"
        dir={dir}
        className="m-link sr-only focus:not-sr-only focus:absolute focus:start-4 focus:top-3 focus:rounded-full focus:bg-[var(--m-bg)] focus:px-4 focus:py-2 focus:text-sm"
        style={{ color: 'var(--m-ink)' }}
      >
        {t('nav.skipToContent')}
      </a>

      {/* Animated backdrop — subtle frosted band fading in past 8px scroll */}
      <motion.div
        aria-hidden
        className="absolute inset-0 -z-10"
        initial={false}
        animate={{
          opacity: scrolled ? 1 : 0,
          backdropFilter: scrolled ? 'saturate(140%) blur(10px)' : 'saturate(100%) blur(0px)',
        }}
        transition={{ duration: reduce ? 0 : 0.25, ease: [0.2, 0, 0, 1] }}
        style={{
          background: 'color-mix(in oklch, var(--m-bg) 78%, transparent)',
          WebkitBackdropFilter: scrolled ? 'saturate(140%) blur(10px)' : 'saturate(100%) blur(0px)',
          borderBottom: '1px solid color-mix(in oklch, var(--m-line) 100%, transparent 0%)',
          borderColor: scrolled ? 'var(--m-line)' : 'transparent',
        }}
      />

      <nav
        aria-label="Primary"
        className="mx-auto flex h-[72px] w-full max-w-[1280px] items-center justify-between gap-6 px-5 md:px-8"
      >
        {/* Brand — scroll to top on home, navigate home from subpages */}
        <Link
          href="/"
          aria-label="Mihna home"
          className="focus-ring rounded-md outline-none"
          onClick={(e) => {
            if (typeof window !== 'undefined' && window.location.pathname === '/') {
              e.preventDefault();
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }
          }}
        >
          <MihnaWordmark size={28} />
        </Link>

        {/* Desktop center nav */}
        <ul
          className="hidden items-center gap-1 md:flex"
          style={{ color: 'var(--m-ink-2)' }}
        >
          <NavLink href="#features" dir={dir}>{t('nav.features')}</NavLink>

          {/* Modules dropdown */}
          <li
            ref={modulesRef}
            className="relative"
            onMouseEnter={openModules}
            onMouseLeave={scheduleCloseModules}
          >
            <button
              type="button"
              aria-expanded={modulesOpen}
              aria-haspopup="menu"
              onClick={() => setModulesOpen((v) => !v)}
              onFocus={openModules}
              className="focus-ring inline-flex h-10 items-center gap-1 rounded-full px-4 text-[14px] font-medium transition-colors"
              style={{
                color: modulesOpen ? 'var(--m-ink)' : 'var(--m-ink-2)',
              }}
            >
              <span dir={dir}>{t('nav.modules')}</span>
              <motion.svg
                width="10"
                height="10"
                viewBox="0 0 10 10"
                fill="none"
                aria-hidden
                animate={{ rotate: modulesOpen ? 180 : 0 }}
                transition={{ duration: reduce ? 0 : 0.25, ease: [0.2, 0, 0, 1] }}
              >
                <path d="M2 3.5L5 6.5L8 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
              </motion.svg>
            </button>

            <AnimatePresence>
              {modulesOpen && (
                <motion.div
                  role="menu"
                  initial={{ opacity: 0, y: -6, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -6, scale: 0.98 }}
                  transition={{ duration: reduce ? 0 : 0.22, ease: [0.2, 0, 0, 1] }}
                  className="absolute top-[calc(100%+6px)] w-[300px] overflow-hidden rounded-2xl p-1.5"
                  dir={dir}
                  style={{
                    background: 'var(--m-bg)',
                    border: '1px solid var(--m-line)',
                    boxShadow:
                      '0 1px 0 color-mix(in oklch, var(--m-ink) 4%, transparent), 0 24px 56px -24px color-mix(in oklch, var(--m-ink) 30%, transparent)',
                    insetInlineStart: 0,
                  }}
                  onMouseEnter={openModules}
                  onMouseLeave={scheduleCloseModules}
                >
                  {moduleItems.map((m) => (
                    <ModuleRow
                      key={m.key}
                      item={m}
                      title={t(m.titleKey)}
                      sub={t(m.subKey)}
                      soonLabel={t('nav.soon')}
                      onSelect={() => setModulesOpen(false)}
                    />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </li>

          <NavLink href="#team" dir={dir}>{t('nav.team')}</NavLink>
          <NavLink href="#faq" dir={dir}>{t('nav.faq')}</NavLink>
        </ul>

        {/* Right cluster */}
        <div className="hidden items-center gap-1 md:flex">
          <LangToggle />
          <ThemeToggle />
          <Link href="/app" className="m-btn-primary ms-2">
            <span dir={dir}>{t('nav.cta')}</span>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
              <path d="M3 7H11M11 7L7.5 3.5M11 7L7.5 10.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </Link>
        </div>

        {/* Mobile cluster */}
        <div className="flex items-center gap-1 md:hidden">
          <LangToggle />
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            aria-label={t('nav.menu')}
            aria-expanded={mobileOpen}
            className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-full"
            style={{ color: 'var(--m-ink)' }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <path d="M2 5h14M2 9h14M2 13h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      </nav>

      <MobileMenu open={mobileOpen} onClose={() => setMobileOpen(false)} />
    </header>
  );
}

function NavLink({
  href,
  children,
  dir,
}: {
  href: string;
  children: React.ReactNode;
  dir: 'ltr' | 'rtl';
}) {
  return (
    <li>
      <Link
        href={href}
        className="focus-ring inline-flex h-10 items-center rounded-full px-4 text-[14px] font-medium transition-colors hover:text-[color:var(--m-ink)]"
      >
        <span dir={dir}>{children}</span>
      </Link>
    </li>
  );
}

function ModuleRow({
  item,
  title,
  sub,
  soonLabel,
  onSelect,
}: {
  item: ModuleItem;
  title: string;
  sub: string;
  soonLabel: string;
  onSelect: () => void;
}) {
  const inner = (
    <div className="flex items-start gap-3 rounded-xl p-3 transition-colors group-hover:bg-[var(--m-bg-elev)]">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[14px] font-medium" style={{ color: 'var(--m-ink)' }}>
            {title}
          </span>
          {item.soon && (
            <span
              className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase"
              style={{
                background: 'var(--m-accent-soft)',
                color: 'var(--m-on-accent)',
                fontFeatureSettings: '"ss01"',
              }}
            >
              {soonLabel}
            </span>
          )}
        </div>
        <div className="mt-1 text-[12.5px] leading-snug" style={{ color: 'var(--m-ink-2)' }}>
          {sub}
        </div>
      </div>
      {item.href && (
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          aria-hidden
          className="mt-0.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100"
          style={{ color: 'var(--m-ink-2)' }}
        >
          <path d="M5 5h6v6M5 11l6-6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  );

  return item.href ? (
    <Link
      role="menuitem"
      href={item.href}
      onClick={onSelect}
      className="group block focus-ring rounded-xl outline-none"
    >
      {inner}
    </Link>
  ) : (
    <div role="menuitem" aria-disabled="true" className="group block cursor-default opacity-70">
      {inner}
    </div>
  );
}

function MobileMenu({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t, dir } = useLanguage();
  const reduce = useReducedMotion();

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="scrim"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.2 }}
            onClick={onClose}
            className="fixed inset-0 z-40"
            style={{ background: 'color-mix(in oklch, var(--m-ink) 30%, transparent)' }}
          />
          <motion.div
            key="sheet"
            role="dialog"
            aria-modal="true"
            dir="ltr"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: reduce ? 0 : 0.28, ease: [0.2, 0, 0, 1] }}
            className="fixed inset-x-3 top-3 z-50 origin-top overflow-hidden rounded-3xl p-2"
            style={{
              background: 'var(--m-bg)',
              border: '1px solid var(--m-line)',
              boxShadow: '0 24px 60px -20px color-mix(in oklch, var(--m-ink) 30%, transparent)',
            }}
          >
            <div className="flex items-center justify-between p-3">
              <MihnaWordmark size={26} />
              <button
                type="button"
                onClick={onClose}
                aria-label={t('nav.close')}
                className="focus-ring inline-flex h-10 w-10 items-center justify-center rounded-full"
                style={{ color: 'var(--m-ink)' }}
              >
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                  <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            <hr className="m-rule mx-3" />

            <ul className="flex flex-col p-2" dir={dir}>
              <MobileLink href="#features" onClose={onClose}>{t('nav.features')}</MobileLink>
              <li className="px-3 pt-3 pb-2 text-[11px] uppercase tracking-[0.18em]" style={{ color: 'var(--m-ink-3)' }}>
                {t('nav.modules')}
              </li>
              {moduleItems.map((m) => (
                <li key={m.key}>
                  {m.href ? (
                    <Link
                      href={m.href}
                      onClick={onClose}
                      className="focus-ring flex items-center justify-between rounded-xl px-3 py-3 outline-none transition-colors hover:bg-[var(--m-bg-elev)]"
                      style={{ color: 'var(--m-ink)' }}
                    >
                      <span>
                        <span className="block text-[15px] font-medium">{t(m.titleKey)}</span>
                        <span className="block text-[12.5px]" style={{ color: 'var(--m-ink-2)' }}>{t(m.subKey)}</span>
                      </span>
                      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden style={{ transform: dir === 'rtl' ? 'scaleX(-1)' : undefined }}>
                        <path d="M5 5h6v6M5 11l6-6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </Link>
                  ) : (
                    <div className="flex items-center justify-between rounded-xl px-3 py-3 opacity-70" style={{ color: 'var(--m-ink)' }}>
                      <span>
                        <span className="block text-[15px] font-medium">{t(m.titleKey)}</span>
                        <span className="block text-[12.5px]" style={{ color: 'var(--m-ink-2)' }}>{t(m.subKey)}</span>
                      </span>
                      <span
                        className="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                        style={{ background: 'var(--m-accent-soft)', color: 'var(--m-on-accent)' }}
                      >
                        {t('nav.soon')}
                      </span>
                    </div>
                  )}
                </li>
              ))}
              <MobileLink href="#team" onClose={onClose}>{t('nav.team')}</MobileLink>
              <MobileLink href="#faq" onClose={onClose}>{t('nav.faq')}</MobileLink>
            </ul>

            <hr className="m-rule mx-3" />

            <div className="p-3">
              <Link
                href="/app"
                onClick={onClose}
                className="m-btn-primary w-full justify-center"
              >
                <span dir={dir}>{t('nav.cta')}</span>
              </Link>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

function MobileLink({
  href,
  onClose,
  children,
}: {
  href: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <li>
      <Link
        href={href}
        onClick={onClose}
        className="focus-ring block rounded-xl px-3 py-3 text-[15px] font-medium outline-none transition-colors hover:bg-[var(--m-bg-elev)]"
        style={{ color: 'var(--m-ink)' }}
      >
        {children}
      </Link>
    </li>
  );
}
