'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { downloadDashboardExport, fetchDashboardPostings } from '@/lib/api';
import { DashboardScope, JobPosting, PostingPage } from '@/lib/types';
import { useDashboardI18n } from '@/lib/dashboard-i18n';

export interface DrilldownRequest {
  title: string;
  scope: DashboardScope;
}

export function DashboardSearch({ onSearch }: { onSearch: (request: DrilldownRequest) => void }) {
  const i18n = useDashboardI18n();
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut — `/` focuses the search box (when not already typing somewhere)
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (target as HTMLElement | null)?.isContentEditable) return;
      event.preventDefault();
      inputRef.current?.focus();
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (value) onSearch({ title: i18n.t('search.title', { query: value }), scope: { query: value } });
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <label className="sr-only" htmlFor="dashboard-search">{i18n.t('search.label')}</label>
      <div className="relative min-w-0 flex-1">
        {/* Magnifier icon — optically aligned via inset; reads as a search field at a glance */}
        <span className="pointer-events-none absolute inset-y-0 start-3 flex items-center" style={{ color: 'var(--muted)' }} aria-hidden>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
        </span>
        <input
          ref={inputRef}
          id="dashboard-search"
          value={query}
          onChange={event => setQuery(event.target.value)}
          onKeyDown={event => { if (event.key === 'Escape') { setQuery(''); inputRef.current?.blur(); } }}
          placeholder={i18n.t('search.placeholder')}
          autoComplete="off"
          spellCheck={false}
          enterKeyHint="search"
          className="w-full rounded-lg ps-9 pe-20 py-2.5 text-sm focus-ring"
          style={{ background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
        />
        {query ? (
          <button
            type="button"
            onClick={() => { setQuery(''); inputRef.current?.focus(); }}
            aria-label={i18n.t('search.clear')}
            title={i18n.t('search.clearShortcut')}
            className="absolute inset-y-0 end-2 my-auto h-7 w-7 inline-flex items-center justify-center rounded-md pill-hover focus-ring"
            style={{ color: 'var(--muted)' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        ) : (
          <kbd
            aria-hidden
            title={i18n.t('search.focusShortcut')}
            className="absolute inset-y-0 end-2 my-auto h-6 px-1.5 inline-flex items-center justify-center rounded-md text-[10px] font-semibold nums"
            style={{
              color: 'var(--muted)',
              background: 'var(--card-alt)',
              border: '1px solid var(--border)',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
            }}>/</kbd>
        )}
      </div>
      <button
        type="submit"
        className="min-h-10 rounded-lg px-4 text-sm font-semibold pill-hover focus-ring active:scale-[0.96]"
        style={{ background: 'var(--accent)', color: '#fff', transitionProperty: 'transform, background-color, box-shadow' }}>
        {i18n.t('search.browse')}
      </button>
    </form>
  );
}

function PostingCard({ posting }: { posting: JobPosting }) {
  const i18n = useDashboardI18n();
  const meta = [
    posting.company,
    posting.location && i18n.value('location', posting.location),
    posting.sector && i18n.value('sector', posting.sector),
    posting.timeline && i18n.value('timeline', posting.timeline),
    posting.salary,
    posting.career_level && i18n.value('career', posting.career_level),
    posting.experience && i18n.value('experience', posting.experience),
  ].filter(Boolean).join(' · ');
  const title = posting.title ? i18n.value('title', posting.title) : i18n.t('drawer.untitled');

  return (
    <article className="rounded-xl p-4 hover-lift" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 dir="auto" className="font-semibold text-sm text-pretty" style={{ color: 'var(--text)' }}>
            {posting.url
              ? <a href={posting.url} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 hover:text-purple-400 transition-colors focus-ring rounded-sm">
                  {title}
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                    strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden className="opacity-70">
                    <path d="M7 17 17 7" />
                    <path d="M7 7h10v10" />
                  </svg>
                </a>
              : title}
          </h3>
          <p dir="auto" className="mt-1 text-xs text-pretty" style={{ color: 'var(--muted)' }}>{meta}</p>
        </div>
        {posting.country && <span className="shrink-0 text-xs" style={{ color: 'var(--muted)' }}>{i18n.value('country', posting.country)}</span>}
      </div>
      {posting.description && (
        <p dir="ltr" lang="en" className="mt-3 text-xs leading-relaxed text-pretty text-start" style={{ color: 'var(--muted)' }}>
          {posting.description.slice(0, 360)}{posting.description.length > 360 ? '…' : ''}
        </p>
      )}
      {i18n.lang === 'ar' && (posting.description || posting.title) && (
        <p className="mt-2 text-[10px]" style={{ color: 'var(--muted)' }}>{i18n.t('drawer.sourceEnglish')}</p>
      )}
      {posting.skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {/* Some postings list the same skill twice (e.g. "SQL" / "SQL").
              Index participates in the key so duplicates don't collide. */}
          {posting.skills.slice(0, 10).map((skill, i) => (
            <span key={`${skill}-${i}`} dir="auto" className="rounded-full px-2 py-1 text-[11px]"
              style={{ background: 'var(--card-alt)', color: 'var(--text)' }}>{i18n.value('skill', skill)}</span>
          ))}
        </div>
      )}
    </article>
  );
}

export function PostingDrawer({
  request,
  dumps,
  onClose,
}: {
  request: DrilldownRequest;
  dumps: string[];
  onClose: () => void;
}) {
  const i18n = useDashboardI18n();
  const [data, setData] = useState<PostingPage | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const [appliedFilter, setAppliedFilter] = useState('');
  const [error, setError] = useState('');
  const closeRef = useRef<HTMLButtonElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const scope = { ...request.scope, query: [request.scope.query, appliedFilter].filter(Boolean).join(' ') };
    fetchDashboardPostings(dumps, scope, page)
      .then(value => {
        setData(value);
        // Reset scroll on page or filter changes so users see the new top
        if (scrollRef.current) scrollRef.current.scrollTop = 0;
      })
      .catch(errorValue => setError(errorValue.message));
  }, [request, dumps, page, appliedFilter]);

  // Lock body scroll while drawer is open
  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previous; };
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') { onClose(); return; }
      // Arrow-key pagination when focus is not inside an input
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (!data) return;
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      const previousKey = i18n.dir === 'rtl' ? 'ArrowRight' : 'ArrowLeft';
      const nextKey = i18n.dir === 'rtl' ? 'ArrowLeft' : 'ArrowRight';
      if (event.key === previousKey && page > 1) setPage(value => value - 1);
      if (event.key === nextKey && page < pages) setPage(value => value + 1);
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [request, onClose, data, page, i18n.dir]);

  const exportScope = { ...request.scope, query: [request.scope.query, appliedFilter].filter(Boolean).join(' ') };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const loading = !data && !error;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/60 drawer-overlay-enter"
      dir={i18n.dir}
      role="presentation"
      onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="posting-drawer-title"
        className="h-full w-full max-w-3xl overflow-hidden shadow-2xl drawer-enter flex flex-col"
        style={{ background: 'var(--bg)' }}>
        {/* Header */}
        <header className="flex items-start gap-3 p-5 shrink-0" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="min-w-0 flex-1">
            <h2 id="posting-drawer-title" className="font-bold text-balance" style={{ color: 'var(--text)' }}>{request.title}</h2>
            <p className="mt-1 text-xs nums" style={{ color: 'var(--muted)' }}>
              {data
                ? i18n.t('drawer.matchingCount', { count: i18n.number(data.total) })
                : i18n.t('drawer.loading')}
            </p>
          </div>
          <button
            type="button"
            onClick={() => { void downloadDashboardExport('postings', dumps, exportScope, 'csv'); }}
            className="inline-flex items-center justify-center min-h-9 min-w-9 px-2.5 text-[11px] font-semibold rounded-lg pill-hover focus-ring"
            style={{ border: '1px solid var(--border)', color: 'var(--text)' }}
            title={i18n.t('common.downloadCsv')}
            aria-label={i18n.t('common.downloadCsv')}>CSV</button>
          <button
            type="button"
            onClick={() => { void downloadDashboardExport('postings', dumps, exportScope, 'json'); }}
            className="inline-flex items-center justify-center min-h-9 min-w-9 px-2.5 text-[11px] font-semibold rounded-lg pill-hover focus-ring"
            style={{ border: '1px solid var(--border)', color: 'var(--text)' }}
            title={i18n.t('common.downloadJson')}
            aria-label={i18n.t('common.downloadJson')}>JSON</button>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label={i18n.t('drawer.close')}
            title={i18n.t('drawer.closeShort')}
            className="inline-flex items-center justify-center h-10 w-10 rounded-lg pill-hover focus-ring"
            style={{ color: 'var(--muted)', border: '1px solid var(--border)' }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M18 6 6 18" />
              <path d="m6 6 12 12" />
            </svg>
          </button>
        </header>

        {/* Filter bar */}
        <form
          className="flex gap-2 p-4 shrink-0"
          onSubmit={event => {
            event.preventDefault();
            setPage(1);
            setAppliedFilter(filter.trim());
          }}>
          <div className="relative min-w-0 flex-1">
            <span className="pointer-events-none absolute inset-y-0 start-3 flex items-center" style={{ color: 'var(--muted)' }} aria-hidden>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="7" />
                <path d="m20 20-3.5-3.5" />
              </svg>
            </span>
            <input
              value={filter}
              onChange={event => setFilter(event.target.value)}
              aria-label={i18n.t('drawer.filterLabel')}
              placeholder={i18n.t('drawer.filterPlaceholder')}
              autoComplete="off"
              spellCheck={false}
              enterKeyHint="search"
              className="w-full rounded-lg ps-9 pe-9 py-2 text-sm focus-ring"
              style={{ background: 'var(--card)', color: 'var(--text)', border: '1px solid var(--border)' }} />
            {filter && (
              <button
                type="button"
                onClick={() => { setFilter(''); if (appliedFilter) { setAppliedFilter(''); setPage(1); } }}
                aria-label={i18n.t('drawer.clearFilter')}
                className="absolute inset-y-0 end-2 my-auto h-7 w-7 inline-flex items-center justify-center rounded-md pill-hover focus-ring"
                style={{ color: 'var(--muted)' }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                  <path d="M18 6 6 18" />
                  <path d="m6 6 12 12" />
                </svg>
              </button>
            )}
          </div>
          <button
            type="submit"
            className="min-h-10 rounded-lg px-4 text-sm font-semibold pill-hover focus-ring active:scale-[0.96]"
            style={{ background: 'var(--accent)', color: '#fff', transitionProperty: 'transform, background-color, box-shadow' }}>
            {i18n.t('drawer.filter')}
          </button>
        </form>

        {/* Scrollable results */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 pb-5">
          {error && (
            <div className="rounded-lg p-4 text-sm text-red-400" role="alert" title={error}>{i18n.t('drawer.error')}</div>
          )}
          {loading && (
            <div className="space-y-3" aria-busy="true">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="skeleton h-28" style={{ animationDelay: `${i * 80}ms` }} />
              ))}
            </div>
          )}
          {data?.items.length === 0 && (
            <div className="p-10 text-center" style={{ color: 'var(--muted)' }}>
              <div className="text-3xl mb-2" aria-hidden>🔍</div>
              <div className="text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>{i18n.t('drawer.noMatches')}</div>
              <div className="text-xs">{i18n.t('drawer.noMatchesHint')}</div>
            </div>
          )}
          <div className="space-y-3">
            {data?.items.map((item, index) => (
              <PostingCard key={`${item.job_id ?? 'idx'}-${index}`} posting={item} />
            ))}
          </div>
        </div>

        {/* Sticky pagination footer */}
        {data && pages > 1 && (
          <div
            className="flex items-center justify-between gap-3 p-3 shrink-0"
            style={{ borderTop: '1px solid var(--border)', background: 'var(--bg)' }}>
            <button
              disabled={page === 1}
              onClick={() => setPage(value => value - 1)}
              aria-label={i18n.t('drawer.previousPage')}
              className="inline-flex items-center gap-1.5 min-h-10 rounded-lg px-3 text-sm pill-hover focus-ring disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ border: '1px solid var(--border)' }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="m15 18-6-6 6-6" transform={i18n.dir === 'rtl' ? 'translate(24 0) scale(-1 1)' : undefined} />
              </svg>
              {i18n.t('drawer.previous')}
            </button>
            <span className="text-xs nums" style={{ color: 'var(--muted)' }}>
              {i18n.t('drawer.pageOf', { page: i18n.number(page), pages: i18n.number(pages) })}
              <span className="hidden sm:inline"> · {i18n.t('drawer.keyboardHint')}</span>
            </span>
            <button
              disabled={page === pages}
              onClick={() => setPage(value => value + 1)}
              aria-label={i18n.t('drawer.nextPage')}
              className="inline-flex items-center gap-1.5 min-h-10 rounded-lg px-3 text-sm pill-hover focus-ring disabled:opacity-40 disabled:cursor-not-allowed"
              style={{ border: '1px solid var(--border)' }}>
              {i18n.t('drawer.next')}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="m9 18 6-6-6-6" transform={i18n.dir === 'rtl' ? 'translate(24 0) scale(-1 1)' : undefined} />
              </svg>
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
