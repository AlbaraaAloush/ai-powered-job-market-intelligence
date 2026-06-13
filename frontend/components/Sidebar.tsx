'use client';

import { useEffect, useMemo, useRef } from 'react';
import { DumpInfo } from '@/lib/types';
import { ModelOption } from '@/lib/api';

interface Props {
  dumps: DumpInfo[];
  timelines: string[];
  selected: string[];
  model: string;
  models: ModelOption[];
  isOpen: boolean;
  showModel?: boolean;
  onToggle: (id: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  onModelChange: (m: string) => void;
  onCollapse: () => void;
}

export default function Sidebar({
  dumps, timelines, selected, model, models, isOpen,
  showModel = true,
  onToggle, onSelectAll, onClearAll, onModelChange, onCollapse,
}: Props) {
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) closeRef.current?.focus();
  }, [isOpen]);

  // Group dumps by country once; sort countries alphabetically, dumps by timeline.
  const grouped = useMemo(() => {
    const by: Record<string, DumpInfo[]> = {};
    for (const d of dumps) (by[d._country] ??= []).push(d);
    return Object.entries(by)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([country, cDumps]) => ({
        country,
        dumps: cDumps.slice().sort((a, b) => a._timeline.localeCompare(b._timeline)),
      }));
  }, [dumps]);

  const totalJobs = dumps
    .filter(d => selectedSet.has(d._dump_id))
    .reduce((s, d) => s + d.count, 0);

  // Click a country header to toggle the whole group:
  //   none → all selected,  any → all,  all → none.
  function toggleCountry(cDumps: DumpInfo[]) {
    const allSelected = cDumps.every(d => selectedSet.has(d._dump_id));
    if (allSelected) {
      cDumps.forEach(d => onToggle(d._dump_id));
    } else {
      cDumps.filter(d => !selectedSet.has(d._dump_id)).forEach(d => onToggle(d._dump_id));
    }
  }

  // Collapsed state — show only a thin strip with toggle
  if (!isOpen) {
    return null;
  }

  return (
    <aside className="app-sidebar" role="dialog" aria-modal="true" aria-labelledby="data-scope-title">

      {/* Header + collapse button */}
      <div className="app-sidebar__heading">
        <div>
          <div id="data-scope-title" className="app-sidebar__title">Data scope</div>
          <div className="app-sidebar__subtitle">GCC job postings</div>
        </div>
        <button
          ref={closeRef}
          type="button"
          onClick={onCollapse}
          title="Collapse sidebar"
          aria-label="Close data scope"
          className="app-icon-button focus-ring">
          <span aria-hidden className="app-close-glyph" />
        </button>
      </div>

      {/* Dataset selector */}
      <div>
        <div className="app-sidebar__section-title">Datasets</div>
        <div className="flex gap-2 mb-3">
          <button type="button" onClick={onSelectAll}
            className="flex-1 text-xs min-h-8 rounded-md border pill-hover focus-ring"
            style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
            All
          </button>
          <button type="button" onClick={onClearAll}
            className="flex-1 text-xs min-h-8 rounded-md border pill-hover focus-ring"
            style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
            None
          </button>
        </div>

        {grouped.map(({ country, dumps: cDumps }) => {
          const selectedInGroup = cDumps.filter(d => selectedSet.has(d._dump_id)).length;
          const allSelected     = selectedInGroup === cDumps.length;
          const someSelected    = selectedInGroup > 0 && !allSelected;

          return (
            <div key={country} className="mb-3">
              {/* Country header is itself a toggle for the whole group */}
              <button
                type="button"
                onClick={() => toggleCountry(cDumps)}
                title={allSelected ? `Deselect all ${country} datasets` : `Select all ${country} datasets`}
                className="w-full flex items-center justify-between gap-2 px-2 py-1 mb-1 rounded-md pill-hover focus-ring"
                style={{ color: 'var(--text)' }}>
                <span className="text-xs font-semibold">{country}</span>
                <span
                  className="text-[10px] nums px-1.5 py-0.5 rounded-md"
                  style={{
                    background: allSelected ? 'var(--accent)' : someSelected ? 'var(--card-alt)' : 'transparent',
                    color:      allSelected ? '#fff'          : 'var(--muted)',
                    border:     someSelected ? '1px dashed var(--muted)' : '1px solid transparent',
                  }}>
                  {selectedInGroup}/{cDumps.length}
                </span>
              </button>

              {/* Dump rows — full-width buttons with clear selected state */}
              <div className="space-y-0.5">
                {cDumps.map(d => {
                  const isSel = selectedSet.has(d._dump_id);
                  return (
                    <button
                      type="button"
                      key={d._dump_id}
                      onClick={() => onToggle(d._dump_id)}
                      role="checkbox"
                      aria-checked={isSel}
                      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left focus-ring"
                      style={{
                        background: isSel ? 'color-mix(in srgb, var(--accent) 14%, transparent)' : 'transparent',
                        border:     `1px solid ${isSel ? 'color-mix(in srgb, var(--accent) 35%, transparent)' : 'transparent'}`,
                        transitionProperty: 'background-color, border-color, transform',
                        transitionDuration: '120ms',
                        transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
                      }}
                      onMouseEnter={e => {
                        if (!isSel) e.currentTarget.style.background = 'var(--card-alt)';
                      }}
                      onMouseLeave={e => {
                        if (!isSel) e.currentTarget.style.background = 'transparent';
                      }}>
                      {/* Custom check — bigger, snappier feedback than native checkbox */}
                      <span
                        aria-hidden
                        className="shrink-0 inline-flex items-center justify-center h-4 w-4 rounded"
                        style={{
                          background: isSel ? 'var(--accent)' : 'transparent',
                          border:     `1.5px solid ${isSel ? 'var(--accent)' : 'var(--border)'}`,
                          transition: 'background-color 120ms ease, border-color 120ms ease',
                        }}>
                        {isSel && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="m5 12 5 5L20 7" />
                          </svg>
                        )}
                      </span>
                      <span className="text-xs leading-tight flex-1 min-w-0">
                        <span className="block truncate" style={{ color: isSel ? 'var(--text)' : 'var(--muted)' }}>
                          {d._timeline}
                        </span>
                        <span className="block text-[10px] nums" style={{ color: 'var(--muted)' }}>
                          {d.count.toLocaleString()} jobs
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}

        <div className="app-sidebar__summary nums">
          {totalJobs > 0 ? `${totalJobs.toLocaleString()} jobs selected` : 'No datasets selected'}
        </div>
      </div>

      {/* Model selector */}
      {showModel && <div className="app-sidebar__model">
        <div className="app-sidebar__section-title">Model</div>
        {models.length === 0 && (
          <div className="text-xs" style={{ color: 'var(--muted)' }}>Loading models…</div>
        )}
        {models.map(({ label, value }) => (
          <label key={value} className="flex items-start gap-2 mb-2 cursor-pointer">
            <input
              type="radio"
              name="model"
              value={value}
              checked={model === value}
              onChange={() => onModelChange(value)}
              className="mt-0.5"
            />
            <span className="text-xs leading-tight" style={{ color: model === value ? 'var(--text)' : 'var(--muted)' }}>
              {label}
            </span>
          </label>
        ))}
      </div>}

      <div className="app-sidebar__source">
        Source: Bayt.com<br />
        {timelines.join(', ')}
      </div>
    </aside>
  );
}
