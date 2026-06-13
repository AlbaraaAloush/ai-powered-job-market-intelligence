'use client';

import Link from 'next/link';
import { useEffect, useState, useTransition } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { MihnaWordmark } from '@/components/landing/MihnaWordmark';
import { LangToggle } from '@/components/landing/LangToggle';
import { ThemeToggle } from '@/components/landing/ThemeToggle';
import { useLanguage } from '@/lib/i18n';

const routes = [
  { href: '/app', key: 'dashboard' },
  { href: '/app/chat', key: 'chat' },
  { href: '/app/analyze', key: 'analyze' },
] as const;

export function AppHeader({ onOpenScope }: { onOpenScope?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const { t, dir } = useLanguage();

  useEffect(() => {
    routes.forEach((route) => router.prefetch(route.href));
  }, [router]);

  return (
    <header className="app-header" style={{ direction: dir }}>
      <div className="app-header__brand">
        {onOpenScope && (
          <button
            type="button"
            className="app-icon-button app-header__scope-toggle"
            onClick={onOpenScope}
            aria-label="Open data scope"
          >
            <span aria-hidden className="app-menu-glyph" />
          </button>
        )}
        <Link href="/" className="focus-ring rounded-md" aria-label={t('app.home')}>
          <MihnaWordmark size={28} />
        </Link>
      </div>

      <nav className="app-route-nav" aria-label="Workspace">
        {routes.map((route) => {
          const currentHref = isPending && pendingHref ? pendingHref : pathname;
          const active = route.href === '/app'
            ? currentHref === '/app'
            : currentHref.startsWith(route.href);
          return (
            <Link
              key={route.key}
              href={route.href}
              aria-current={active ? 'page' : undefined}
              aria-busy={active && isPending ? true : undefined}
              className="app-route-link focus-ring"
              onPointerEnter={() => router.prefetch(route.href)}
              onFocus={() => router.prefetch(route.href)}
              onClick={(event) => {
                if (
                  event.defaultPrevented ||
                  event.button !== 0 ||
                  event.metaKey ||
                  event.ctrlKey ||
                  event.shiftKey ||
                  event.altKey ||
                  route.href === pathname
                ) return;

                event.preventDefault();
                setPendingHref(route.href);
                startTransition(() => router.push(route.href));
              }}
            >
              {t(`app.${route.key}`)}
            </Link>
          );
        })}
      </nav>

      <div className="app-header__actions">
        <LangToggle />
        <ThemeToggle />
      </div>
    </header>
  );
}
