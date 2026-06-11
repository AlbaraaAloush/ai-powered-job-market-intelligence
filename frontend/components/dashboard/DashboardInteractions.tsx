'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { dashboardExportUrl, fetchDashboardPostings } from '@/lib/api';
import { DashboardScope, JobPosting, PostingPage } from '@/lib/types';

export interface DrilldownRequest {
  title: string;
  scope: DashboardScope;
}

export function DashboardSearch({ onSearch }: { onSearch: (request: DrilldownRequest) => void }) {
  const [query, setQuery] = useState('');

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = query.trim();
    if (value) onSearch({ title: `Search: ${value}`, scope: { query: value } });
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <label className="sr-only" htmlFor="dashboard-search">Search job postings</label>
      <input
        id="dashboard-search"
        value={query}
        onChange={event => setQuery(event.target.value)}
        placeholder="Search titles, companies, skills, locations, and descriptions"
        className="min-w-0 flex-1 rounded-lg px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-purple-500"
        style={{ background: 'var(--bg)', color: 'var(--text)', border: '1px solid var(--border)' }}
      />
      <button
        type="submit"
        className="min-h-10 rounded-lg px-4 text-sm font-semibold active:scale-[0.96] transition-transform"
        style={{ background: 'var(--accent)', color: '#fff' }}>
        Browse results
      </button>
    </form>
  );
}

function PostingCard({ posting }: { posting: JobPosting }) {
  const meta = [
    posting.company, posting.location, posting.sector, posting.timeline,
    posting.salary, posting.career_level, posting.experience,
  ].filter(Boolean).join(' · ');

  return (
    <article className="rounded-xl p-4" style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="font-semibold text-sm text-pretty" style={{ color: 'var(--text)' }}>
            {posting.url
              ? <a href={posting.url} target="_blank" rel="noreferrer" className="hover:text-purple-400">{posting.title || 'Untitled posting'}</a>
              : posting.title || 'Untitled posting'}
          </h3>
          <p className="mt-1 text-xs text-pretty" style={{ color: 'var(--muted)' }}>{meta}</p>
        </div>
        {posting.country && <span className="shrink-0 text-xs" style={{ color: 'var(--muted)' }}>{posting.country}</span>}
      </div>
      {posting.description && (
        <p className="mt-3 text-xs leading-relaxed text-pretty" style={{ color: 'var(--muted)' }}>
          {posting.description.slice(0, 360)}{posting.description.length > 360 ? '…' : ''}
        </p>
      )}
      {posting.skills.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {posting.skills.slice(0, 10).map(skill => (
            <span key={skill} className="rounded-full px-2 py-1 text-[11px]"
              style={{ background: 'var(--card-alt)', color: 'var(--text)' }}>{skill}</span>
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
  const [data, setData] = useState<PostingPage | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState('');
  const [appliedFilter, setAppliedFilter] = useState('');
  const [error, setError] = useState('');
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const scope = { ...request.scope, query: [request.scope.query, appliedFilter].filter(Boolean).join(' ') };
    fetchDashboardPostings(dumps, scope, page)
      .then(setData)
      .catch(errorValue => setError(errorValue.message));
  }, [request, dumps, page, appliedFilter]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [request, onClose]);

  const exportScope = { ...request.scope, query: [request.scope.query, appliedFilter].filter(Boolean).join(' ') };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60" role="presentation" onMouseDown={event => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section role="dialog" aria-modal="true" aria-labelledby="posting-drawer-title"
        className="h-full w-full max-w-3xl overflow-hidden shadow-2xl"
        style={{ background: 'var(--bg)' }}>
        <header className="flex items-start gap-3 p-5" style={{ borderBottom: '1px solid var(--border)' }}>
          <div className="min-w-0 flex-1">
            <h2 id="posting-drawer-title" className="font-bold text-balance" style={{ color: 'var(--text)' }}>{request.title}</h2>
            <p className="mt-1 text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
              {data ? `${data.total.toLocaleString()} matching postings` : 'Loading matching postings…'}
            </p>
          </div>
          <a className="min-h-10 px-3 py-2 text-xs font-semibold rounded-lg active:scale-[0.96] transition-transform"
            style={{ border: '1px solid var(--border)', color: 'var(--text)' }}
            href={dashboardExportUrl('postings', dumps, exportScope, 'csv')}>CSV</a>
          <a className="min-h-10 px-3 py-2 text-xs font-semibold rounded-lg active:scale-[0.96] transition-transform"
            style={{ border: '1px solid var(--border)', color: 'var(--text)' }}
            href={dashboardExportUrl('postings', dumps, exportScope, 'json')}>JSON</a>
          <button ref={closeRef} onClick={onClose} aria-label="Close detailed results"
            className="min-h-10 min-w-10 rounded-lg text-lg active:scale-[0.96] transition-transform"
            style={{ color: 'var(--muted)', border: '1px solid var(--border)' }}>×</button>
        </header>

        <form className="flex gap-2 p-4" onSubmit={event => {
          event.preventDefault();
          setPage(1);
          setAppliedFilter(filter.trim());
        }}>
          <input value={filter} onChange={event => setFilter(event.target.value)}
            aria-label="Filter current result set" placeholder="Filter these postings"
            className="min-w-0 flex-1 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-purple-500"
            style={{ background: 'var(--card)', color: 'var(--text)', border: '1px solid var(--border)' }} />
          <button className="min-h-10 rounded-lg px-4 text-sm font-semibold active:scale-[0.96] transition-transform"
            style={{ background: 'var(--accent)', color: '#fff' }}>Filter</button>
        </form>

        <div className="h-[calc(100%-145px)] overflow-y-auto px-4 pb-5">
          {error && <div className="rounded-lg p-4 text-sm text-red-400">{error}</div>}
          {!data && !error && <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>Loading…</div>}
          {data?.items.length === 0 && <div className="p-8 text-center text-sm" style={{ color: 'var(--muted)' }}>No postings match this scope.</div>}
          <div className="space-y-3">{data?.items.map((item, index) => <PostingCard key={`${item.job_id ?? index}`} posting={item} />)}</div>
          {data && pages > 1 && (
            <div className="mt-4 flex items-center justify-between">
              <button disabled={page === 1} onClick={() => setPage(value => value - 1)}
                className="min-h-10 rounded-lg px-4 text-sm disabled:opacity-40"
                style={{ border: '1px solid var(--border)' }}>Previous</button>
              <span className="text-xs tabular-nums" style={{ color: 'var(--muted)' }}>Page {page} of {pages}</span>
              <button disabled={page === pages} onClick={() => setPage(value => value + 1)}
                className="min-h-10 rounded-lg px-4 text-sm disabled:opacity-40"
                style={{ border: '1px solid var(--border)' }}>Next</button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
