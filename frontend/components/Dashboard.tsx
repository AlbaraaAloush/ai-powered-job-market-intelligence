'use client';

import { useEffect, useRef, useState } from 'react';
import { fetchDashboard } from '@/lib/api';
import { dashboardExportUrl } from '@/lib/api';
import { DashboardData, DashboardDimension, DashboardScope } from '@/lib/types';
import {
  DashboardSearch, DrilldownRequest, PostingDrawer,
} from '@/components/dashboard/DashboardInteractions';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';

// ── Design tokens ────────────────────────────────────────────────────────────
const TL_PALETTE = ['#6c63ff', '#00c9a7', '#ffd93d', '#ff6b6b', '#a855f7'];
const CAT_PALETTE = ['#6c63ff','#00c9a7','#ffd93d','#ff6b6b','#a855f7','#4ecdc4','#ff8e53','#44b09e','#667eea','#f093fb','#4facfe','#43e97b'];

const TT_STYLE = {
  backgroundColor: 'var(--card-alt)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  color: 'var(--text)',
  fontSize: 12,
  padding: '8px 12px',
};
const TT_LABEL  = { color: 'var(--text)', fontWeight: 600, marginBottom: 4 };
const TT_ITEM   = { color: 'var(--muted)', padding: '2px 0' };
const AX_STYLE  = { fill: 'var(--muted)', fontSize: 11 };
const Y_STYLE   = { fill: 'var(--text)', fontSize: 11 };

const FLAGS: Record<string, string> = {
  All: '🌍', Qatar: '🇶🇦', UAE: '🇦🇪', 'Saudi Arabia': '🇸🇦',
  Bahrain: '🇧🇭', Kuwait: '🇰🇼', Oman: '🇴🇲',
};

// ── Shared chart helpers ──────────────────────────────────────────────────────

function tt(extra?: object) {
  return (
    <Tooltip
      contentStyle={TT_STYLE}
      labelStyle={TT_LABEL}
      itemStyle={TT_ITEM}
      // Recharts' default hover cursor is solid #ccc — reads as near-white on dark themes
      // and gives the bar a harsh flash. A low-opacity card-alt fill is gentle in both themes.
      cursor={{ fill: 'var(--card-alt)', fillOpacity: 0.35 }}
      formatter={(v, n) => [Number(v).toLocaleString(), String(n)]}
      {...extra}
    />
  );
}

/** Single-series horizontal bar (sorted descending = top item largest) */
function HBar({ data, x, y, color = '#6c63ff', height, onSelect }: {
  data: Record<string, unknown>[]; x: string; y: string; color?: string; height: number;
  onSelect?: (row: Record<string, unknown>) => void;
}) {
  // Wrapping div sets cursor for the entire chart area — including the Tooltip's
  // hover rectangle that recharts draws on top of bars (SVG inherits CSS cursor).
  return (
    <div style={{ cursor: onSelect ? 'pointer' : 'default' }}>
      <ResponsiveContainer width="100%" height={height} minWidth={0} minHeight={0}>
        <BarChart data={[...data].reverse()} layout="vertical"
          margin={{ left: 8, right: 60, top: 4, bottom: 4 }}>
          <XAxis type="number" tick={AX_STYLE} axisLine={false} tickLine={false}
            tickFormatter={(v) => Number(v) >= 1000 ? `${(Number(v)/1000).toFixed(1)}k` : String(v)} />
          <YAxis type="category" dataKey={y} width={175}
            tick={Y_STYLE} axisLine={false} tickLine={false} />
          {tt()}
          <Bar dataKey={x} fill={color} radius={[0, 4, 4, 0]}
            cursor={onSelect ? 'pointer' : undefined}
            onClick={entry => onSelect?.(entry.payload as Record<string, unknown>)}
            label={{ position: 'right', fill: 'var(--muted)', fontSize: 10,
              formatter: (v: unknown) => Number(v) >= 1000 ? `${(Number(v)/1000).toFixed(1)}k` : String(v) }} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Stacked horizontal bar — one segment per timeline */
function HBarStacked({ rows, timelines, tlColors, height }: {
  rows: Record<string, unknown>[]; timelines: string[]; tlColors: Record<string, string>; height: number;
}) {
  const sorted = [...rows].sort((a, b) => {
    const ta = timelines.reduce((s, t) => s + ((a[t] as number) ?? 0), 0);
    const tb = timelines.reduce((s, t) => s + ((b[t] as number) ?? 0), 0);
    return ta - tb; // asc = top is largest in horizontal chart
  });

  return (
    <ResponsiveContainer width="100%" height={height} minWidth={0} minHeight={0}>
      <BarChart data={sorted} layout="vertical"
        margin={{ left: 8, right: 60, top: 4, bottom: 4 }}>
        <XAxis type="number" tick={AX_STYLE} axisLine={false} tickLine={false}
          tickFormatter={(v) => Number(v) >= 1000 ? `${(Number(v)/1000).toFixed(1)}k` : String(v)} />
        <YAxis type="category" dataKey="sector" width={175}
          tick={Y_STYLE} axisLine={false} tickLine={false} />
        {tt()}
        <Legend wrapperStyle={{ fontSize: 11, color: 'var(--muted)', paddingTop: 8 }} />
        {timelines.map((tl, i) => (
          <Bar key={tl} dataKey={tl} stackId="s" fill={tlColors[tl] ?? TL_PALETTE[i % TL_PALETTE.length]}
            radius={i === timelines.length - 1 ? [0, 4, 4, 0] : [0, 0, 0, 0]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}


/** Donut — Top-N + "Other" + ranked legend list.
 *  Recharts side-labels collide for slices < ~5% and a flat legend with
 *  20+ categories becomes unreadable. We keep the pie clean and put the
 *  detail in a sortable, scrollable, clickable list. */
function Donut({ data, name, value, onSelect }: {
  data: Record<string, unknown>[]; name: string; value: string;
  onSelect?: (row: Record<string, unknown>) => void;
}) {
  const TOP_N = 6;
  const sorted = [...data].sort((a, b) => Number(b[value] ?? 0) - Number(a[value] ?? 0));
  const total  = sorted.reduce((s, d) => s + Number(d[value] ?? 0), 0);

  type Slice = {
    label:    string;
    count:    number;
    color:    string;
    original: Record<string, unknown> | null;
    isOther:  boolean;
  };

  const top:  Slice[] = sorted.slice(0, TOP_N).map((d, i) => ({
    label:    String(d[name]),
    count:    Number(d[value] ?? 0),
    color:    CAT_PALETTE[i % CAT_PALETTE.length],
    original: d,
    isOther:  false,
  }));
  const rest = sorted.slice(TOP_N);
  const slices: Slice[] = rest.length > 0
    ? [...top, {
        label:    `Other (${rest.length})`,
        count:    rest.reduce((s, d) => s + Number(d[value] ?? 0), 0),
        color:    'var(--muted)',
        original: null,
        isOther:  true,
      }]
    : top;

  function handlePick(slice: Slice) {
    if (slice.isOther || !slice.original || !onSelect) return;
    onSelect(slice.original);
  }

  return (
    // Container queries: switch from stacked → side-by-side based on the CARD'S
    // own width, not the viewport. So a donut card sitting in a 3-col grid (~340px)
    // stacks vertically; the same component in a half-width card (~520px) goes
    // side-by-side. No more legend labels truncating to "F.." or "Sau...".
    <div className="@container max-w-xl mx-auto">
      <div className="grid grid-cols-1 @md:grid-cols-[160px_minmax(0,1fr)] gap-3 @md:gap-4 items-center">
        {/* Donut + centered total — slightly smaller when stacked */}
        <div className="relative h-[170px] @md:h-[200px] mx-auto w-full max-w-[170px] @md:max-w-[200px]">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
            <PieChart>
              <Pie
                data={slices}
                dataKey="count"
                nameKey="label"
                cx="50%" cy="50%"
                innerRadius={46} outerRadius={76}
                paddingAngle={slices.length > 1 ? 1.5 : 0}
                stroke="var(--card)" strokeWidth={2}
                isAnimationActive={false}
                cursor={onSelect ? 'pointer' : undefined}
                onClick={(_, idx) => handlePick(slices[idx])}>
                {slices.map((s, i) => <Cell key={i} fill={s.color} />)}
              </Pie>
              <Tooltip
                contentStyle={TT_STYLE}
                labelStyle={TT_LABEL}
                itemStyle={TT_ITEM}
                formatter={(v) => [
                  `${Number(v).toLocaleString()} (${total ? ((Number(v) / total) * 100).toFixed(1) : '0'}%)`,
                  'Postings',
                ]}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--muted)' }}>Total</div>
            <div className="text-base @md:text-lg font-bold leading-tight nums" style={{ color: 'var(--text)' }}>
              {total.toLocaleString()}
            </div>
          </div>
        </div>

        {/* Ranked legend list — full width when stacked, narrower side panel when wide */}
        <ul className="w-full max-h-[170px] @md:max-h-[220px] overflow-y-auto pr-1 space-y-0.5">
          {slices.map((s, i) => {
            const pct       = total > 0 ? (s.count / total) * 100 : 0;
            const clickable = !s.isOther && !!onSelect;
            return (
              <li key={`${s.label}-${i}`}>
                <button
                  type="button"
                  disabled={!clickable}
                  onClick={() => handlePick(s)}
                  title={clickable ? `${s.label} — ${s.count.toLocaleString()} (${pct.toFixed(1)}%)` : s.isOther ? `${rest.length} smaller categories` : undefined}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-left pill-hover focus-ring cursor-pointer disabled:cursor-not-allowed"
                  style={{ background: 'transparent' }}>
                  <span aria-hidden className="h-2.5 w-2.5 rounded-sm shrink-0" style={{ background: s.color }} />
                  <span
                    className={`text-xs truncate flex-1 min-w-0 ${s.isOther ? 'italic' : ''}`}
                    style={{ color: s.isOther ? 'var(--muted)' : 'var(--text)' }}>
                    {s.label}
                  </span>
                  {/* Count column is hidden in extra-narrow legend (very tight cards) — % alone tells the story, full count is in the tooltip */}
                  <span className="hidden @xs:inline text-xs nums shrink-0" style={{ color: 'var(--muted)' }}>
                    {s.count >= 1000 ? `${(s.count / 1000).toFixed(1)}k` : s.count.toLocaleString()}
                  </span>
                  <span className="text-[10px] nums w-10 text-right shrink-0" style={{ color: 'var(--muted)' }}>
                    {pct.toFixed(pct < 10 ? 1 : 0)}%
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

// ── Salary-specific visualizations ────────────────────────────────────────────
//
// The generic HBar/VBar don't serve Salary Intelligence well:
//   • A single outlier (e.g. "Technical $43.1k") compresses every other bar
//     into identical stubs, hiding all sector-to-sector variation.
//   • Averages without sample size are misleading — a 12-posting sector reads
//     identical to a 1,200-posting sector.
//   • Categorical rainbow colours on an ordinal bracket axis suggests the
//     brackets are unrelated when they're a continuous distribution.
//
// These two components fix all three.

function fmtUsd(n: number) {
  return n >= 1000 ? `$${(n / 1000).toFixed(1)}k` : `$${Math.round(n)}`;
}

function SectorSalaryBars({ data, onSelect }: {
  data:      { sector: string; avg_usd: number; count: number }[];
  onSelect?: (row: { sector: string; avg_usd: number; count: number }) => void;
}) {
  const sorted = [...data].sort((a, b) => b.avg_usd - a.avg_usd);
  const max    = Math.max(...sorted.map(d => d.avg_usd), 1);

  // Robust median (avg salaries) — used to flag obvious outliers.
  const vals = sorted.map(d => d.avg_usd).sort((a, b) => a - b);
  const mid  = Math.floor(vals.length / 2);
  const median = vals.length === 0
    ? 0
    : (vals.length % 2 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2);

  return (
    <div
      className="space-y-0.5 max-h-[420px] overflow-y-auto pr-1"
      style={{ cursor: onSelect ? 'pointer' : 'default' }}>
      {sorted.map(row => {
        const pct       = (row.avg_usd / max) * 100;
        const lowSample = row.count < 5;
        const outlier   = median > 0 && row.avg_usd > median * 3;
        const dim       = lowSample || outlier;
        return (
          <button
            key={row.sector}
            type="button"
            onClick={() => onSelect?.(row)}
            disabled={!onSelect}
            title={[
              row.sector,
              `Average: ${fmtUsd(row.avg_usd)}/mo`,
              `Sample size: ${row.count.toLocaleString()} postings`,
              lowSample ? '⚠ Low sample — interpret with caution' : '',
              outlier   ? '⚠ Potential outlier (more than 3× median)' : '',
            ].filter(Boolean).join('\n')}
            className="w-full grid grid-cols-[150px_1fr_64px_64px] gap-3 items-center px-2 py-1.5 rounded-md pill-hover focus-ring text-left cursor-pointer disabled:cursor-not-allowed">
            <span className="text-xs truncate" style={{ color: 'var(--text)' }}>
              {row.sector}
            </span>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--card-alt)' }}>
              <div
                className="h-full rounded-full"
                style={{
                  width: `${pct}%`,
                  background: '#00c9a7',
                  opacity:    dim ? 0.4 : 1,
                  transition: 'width 320ms cubic-bezier(0.2, 0, 0, 1), opacity 200ms ease',
                }} />
            </div>
            <span className="text-xs nums text-right" style={{ color: 'var(--text)' }}>
              {fmtUsd(row.avg_usd)}
            </span>
            <span
              className="text-[10px] nums text-right inline-flex items-center justify-end gap-0.5"
              style={{ color: 'var(--muted)' }}>
              n={row.count.toLocaleString()}
              {dim && <span aria-hidden style={{ color: '#ffd93d' }}>⚠</span>}
            </span>
          </button>
        );
      })}
      {sorted.some(r => r.count < 5 || (median > 0 && r.avg_usd > median * 3)) && (
        <p className="text-[10px] pt-2 mt-1 border-t" style={{ color: 'var(--muted)', borderColor: 'var(--border)' }}>
          <span style={{ color: '#ffd93d' }}>⚠</span> Low sample size or 3× median outlier — average may be unreliable.
        </p>
      )}
    </div>
  );
}

function SalaryBracketBars({ data, onSelect }: {
  data:      { bracket: string; count: number }[];
  onSelect?: (row: { bracket: string; count: number }) => void;
}) {
  const max     = Math.max(...data.map(d => d.count), 1);
  const total   = data.reduce((s, d) => s + d.count, 0);
  const peakIdx = data.reduce((mi, d, i, arr) => d.count > arr[mi].count ? i : mi, 0);

  return (
    <div
      className="h-[300px] flex flex-col"
      style={{ cursor: onSelect ? 'pointer' : 'default' }}>
      {/* Chart row — items-stretch + min-h-0 gives each button a real pixel height,
          so the bar's `height: X%` actually resolves to something visible. */}
      <div className="flex-1 flex items-stretch gap-1.5 px-1 min-h-0">
        {data.map((row, i) => {
          const pct    = total ? (row.count / total) * 100 : 0;
          const isPeak = i === peakIdx;
          // Cap the tallest bar at 92% of column height so the value label
          // (which sits above the bar's top edge) always has room.
          const barH   = Math.max(1.5, (row.count / max) * 92);
          return (
            <button
              key={row.bracket}
              type="button"
              onClick={() => onSelect?.(row)}
              disabled={!onSelect}
              aria-label={`${row.bracket}: ${row.count.toLocaleString()} postings (${pct.toFixed(1)}%)`}
              title={`${row.bracket}\n${row.count.toLocaleString()} postings (${pct.toFixed(1)}%)`}
              className="flex-1 group relative focus-ring rounded-md cursor-pointer disabled:cursor-not-allowed">
              {/* Bar — anchored to the bottom of the column */}
              <div
                className="absolute left-0 right-0 bottom-0 rounded-t-md group-hover:brightness-110"
                style={{
                  height:     `${barH}%`,
                  background: isPeak ? 'var(--accent)' : '#00c9a7',
                  opacity:    isPeak ? 1 : 0.85,
                  transitionProperty:       'height, opacity, filter',
                  transitionDuration:       '320ms',
                  transitionTimingFunction: 'cubic-bezier(0.2, 0, 0, 1)',
                }} />
              {/* Value label — sits 4px above the bar's top edge */}
              <span
                className={`absolute left-0 right-0 text-center text-[10px] nums leading-none transition-opacity duration-150 ${isPeak ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                style={{ bottom: `calc(${barH}% + 4px)`, color: 'var(--text)' }}>
                {row.count.toLocaleString()}
              </span>
            </button>
          );
        })}
      </div>
      <div className="flex gap-1.5 px-1 pt-2 mt-1 border-t" style={{ borderColor: 'var(--border)' }}>
        {data.map(row => (
          <span
            key={row.bracket}
            className="flex-1 text-[10px] text-center truncate"
            style={{ color: 'var(--muted)' }}
            title={row.bracket}>
            {row.bracket}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── GCC signal components (Remote / Nationalization / Bilingual / Arabic terms) ──
//
// Clean list-row look (same affordances as SectorSalaryBars):
// label · inline bar · numeric value. Avoids recharts for tiny country lists
// where the bar count is small but visual hierarchy matters most.

function CountryPctBars({ data, accent = '#00c9a7', onSelect }: {
  data:      { country: string; pct: number; count: number }[];
  accent?:   string;
  onSelect?: (row: { country: string; pct: number; count: number }) => void;
}) {
  const sorted = [...data].sort((a, b) => b.pct - a.pct);
  const max    = Math.max(...sorted.map(d => d.pct), 1);
  return (
    <div className="space-y-0.5" style={{ cursor: onSelect ? 'pointer' : 'default' }}>
      {sorted.map(row => {
        const w = (row.pct / max) * 100;
        return (
          <button
            key={row.country}
            type="button"
            onClick={() => onSelect?.(row)}
            disabled={!onSelect}
            title={`${row.country} — ${row.count.toLocaleString()} matching postings (${row.pct.toFixed(1)}%)`}
            className="w-full grid grid-cols-[120px_1fr_64px] gap-3 items-center px-2 py-1.5 rounded-md pill-hover focus-ring text-left cursor-pointer disabled:cursor-not-allowed">
            <span className="text-xs inline-flex items-center gap-1.5" style={{ color: 'var(--text)' }}>
              <span aria-hidden>{FLAGS[row.country] ?? '🌍'}</span>
              <span className="truncate">{row.country}</span>
            </span>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--card-alt)' }}>
              <div className="h-full rounded-full"
                style={{
                  width:      `${w}%`,
                  background: accent,
                  transition: 'width 320ms cubic-bezier(0.2, 0, 0, 1)',
                }} />
            </div>
            <span className="text-xs nums text-right" style={{ color: 'var(--text)' }}>
              {row.pct.toFixed(1)}%
            </span>
          </button>
        );
      })}
    </div>
  );
}

function BilingualBars({ data, onSelect }: {
  data:      { country: string; en_only: number; ar_only: number; both: number }[];
  onSelect?: (row: { country: string; segment: 'en_only' | 'ar_only' | 'both' }) => void;
}) {
  const SEG = [
    { key: 'both',    label: 'Bilingual (EN + AR)', color: 'var(--accent)' },
    { key: 'en_only', label: 'English only',        color: '#00c9a7'       },
    { key: 'ar_only', label: 'Arabic only',         color: '#ffd93d'       },
  ] as const;

  return (
    <div className="space-y-3" style={{ cursor: onSelect ? 'pointer' : 'default' }}>
      {data.map(row => {
        const total = row.en_only + row.ar_only + row.both || 1;
        const segs  = SEG.map(s => ({ ...s, n: row[s.key], pct: (row[s.key] / total) * 100 }));
        return (
          <div key={row.country}>
            <div className="flex items-baseline justify-between mb-1.5 px-1">
              <span className="text-xs font-semibold inline-flex items-center gap-1.5" style={{ color: 'var(--text)' }}>
                <span aria-hidden>{FLAGS[row.country] ?? '🌍'}</span>
                <span>{row.country}</span>
              </span>
              <span className="text-[10px] nums" style={{ color: 'var(--muted)' }}>
                {total.toLocaleString()} postings
              </span>
            </div>
            <div className="flex h-3 rounded-full overflow-hidden" style={{ background: 'var(--card-alt)' }}>
              {segs.map(s => s.pct > 0 && (
                <button
                  key={s.key}
                  type="button"
                  onClick={() => onSelect?.({ country: row.country, segment: s.key })}
                  disabled={!onSelect}
                  title={`${s.label} — ${s.n.toLocaleString()} (${s.pct.toFixed(1)}%)`}
                  className="cursor-pointer disabled:cursor-not-allowed"
                  style={{
                    width:      `${s.pct}%`,
                    background: s.color,
                    border:     'none',
                    transition: 'filter 150ms ease',
                  }}
                  onMouseEnter={e => (e.currentTarget.style.filter = 'brightness(1.15)')}
                  onMouseLeave={e => (e.currentTarget.style.filter = 'brightness(1)')} />
              ))}
            </div>
            <div className="flex gap-3 mt-1 px-1 text-[10px] nums flex-wrap" style={{ color: 'var(--muted)' }}>
              {segs.map(s => (
                <span key={s.key} className="inline-flex items-center gap-1">
                  <span aria-hidden className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
                  {s.label.replace(' (EN + AR)', '').replace(' only', '')} · {s.pct.toFixed(0)}%
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ArabicTermsBars({ data, onSelect }: {
  data:      { term: string; count: number }[];
  onSelect?: (row: { term: string; count: number }) => void;
}) {
  const sorted = [...data].sort((a, b) => b.count - a.count).slice(0, 20);
  const max    = Math.max(...sorted.map(d => d.count), 1);
  return (
    <div className="space-y-0.5 max-h-[480px] overflow-y-auto pr-1"
         style={{ cursor: onSelect ? 'pointer' : 'default' }}>
      {sorted.map((row, i) => {
        const w = (row.count / max) * 100;
        return (
          <button
            key={`${row.term}-${i}`}
            type="button"
            onClick={() => onSelect?.(row)}
            disabled={!onSelect}
            title={`${row.term} — ${row.count.toLocaleString()} postings`}
            className="w-full grid grid-cols-[180px_1fr_72px] gap-3 items-center px-2 py-1.5 rounded-md pill-hover focus-ring text-left cursor-pointer disabled:cursor-not-allowed">
            {/* RTL container so Arabic text aligns naturally and punctuation sits on the right edge */}
            <span dir="rtl" lang="ar" className="text-sm truncate" style={{ color: 'var(--text)', fontFamily: '"Noto Naskh Arabic", "Segoe UI", sans-serif' }}>
              {row.term}
            </span>
            <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--card-alt)' }}>
              <div className="h-full rounded-full"
                style={{
                  width:      `${w}%`,
                  background: '#a855f7',
                  transition: 'width 320ms cubic-bezier(0.2, 0, 0, 1)',
                }} />
            </div>
            <span className="text-xs nums text-right" style={{ color: 'var(--text)' }}>
              {row.count.toLocaleString()}
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────────────

function Card({ title, subtitle, children, exportUrls, index = 0 }: {
  title: string; subtitle?: string; children: React.ReactNode;
  exportUrls?: { csv: string; json: string };
  index?: number;
}) {
  return (
    <div
      className="rounded-xl mb-5 overflow-hidden hover-lift card-in"
      style={{
        background: 'var(--card)',
        border: '1px solid var(--border)',
        animationDelay: `${Math.min(index, 6) * 40}ms`,
      }}>
      <div className="flex items-start gap-3 px-5 pt-4 pb-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="min-w-0 flex-1">
          <div className="font-bold text-sm text-balance" style={{ color: 'var(--text)' }}>{title}</div>
          {subtitle && <div className="text-xs mt-0.5 text-pretty" style={{ color: 'var(--muted)' }}>{subtitle}</div>}
        </div>
        {exportUrls && (
          <div className="flex gap-1.5">
            <a
              href={exportUrls.csv}
              title="Download as CSV"
              aria-label="Download as CSV"
              className="inline-flex items-center justify-center min-h-9 min-w-9 px-2.5 text-[11px] font-semibold tracking-wide rounded-lg pill-hover focus-ring"
              style={{ color: 'var(--muted)', border: '1px solid var(--border)' }}>CSV</a>
            <a
              href={exportUrls.json}
              title="Download as JSON"
              aria-label="Download as JSON"
              className="inline-flex items-center justify-center min-h-9 min-w-9 px-2.5 text-[11px] font-semibold tracking-wide rounded-lg pill-hover focus-ring"
              style={{ color: 'var(--muted)', border: '1px solid var(--border)' }}>JSON</a>
          </div>
        )}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// ── Navigation components ─────────────────────────────────────────────────────

function CountryTabs({ countries, counts, active, onChange }: {
  countries: string[]; counts: Record<string, number>; active: string; onChange: (c: string) => void;
}) {
  const all = ['All', ...countries];
  return (
    <div className="flex gap-2 flex-wrap" role="tablist" aria-label="Country filter">
      {all.map(c => {
        const isActive = active === c;
        return (
          <button
            key={c}
            onClick={() => onChange(c)}
            role="tab"
            aria-selected={isActive}
            className={`flex items-center gap-1.5 px-3.5 min-h-9 rounded-lg text-xs font-semibold pill-hover focus-ring ${isActive ? '' : 'hover:border-[var(--muted)]'}`}
            style={isActive
              ? { background: 'var(--accent)', color: '#fff', border: '1px solid var(--accent)', boxShadow: '0 1px 2px rgba(108,99,255,0.25), 0 4px 12px rgba(108,99,255,0.18)' }
              : { background: 'var(--card)', color: 'var(--muted)', border: '1px solid var(--border)' }}>
            <span aria-hidden>{FLAGS[c] ?? '🌍'}</span>
            <span>{c}</span>
            {c !== 'All' && counts[c] !== undefined && (
              <span className="ml-1 px-1.5 py-0.5 rounded-md text-[10px] nums"
                style={{
                  background: isActive ? 'rgba(255,255,255,0.22)' : 'var(--card-alt)',
                  color: isActive ? '#fff' : 'var(--muted)',
                }}>
                {counts[c].toLocaleString()}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function TimelinePills({ timelines, tlColors, active, onChange }: {
  timelines: string[]; tlColors: Record<string, string>; active: string; onChange: (t: string) => void;
}) {
  const all = ['All', ...timelines];
  return (
    <div className="flex gap-2 flex-wrap items-center" role="tablist" aria-label="Timeline filter">
      <span className="text-xs font-semibold mr-1" style={{ color: 'var(--muted)' }}>Timeline:</span>
      {all.map((t, i) => {
        const isActive = active === t;
        const bgColor  = t === 'All' ? 'var(--accent)' : (tlColors[t] ?? TL_PALETTE[(i - 1) % TL_PALETTE.length]);
        return (
          <button
            key={t}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(t)}
            className="px-3 min-h-8 rounded-full text-xs font-semibold pill-hover focus-ring"
            style={isActive
              ? { background: bgColor, color: '#fff', border: `1px solid ${bgColor}`, boxShadow: `0 1px 2px ${bgColor}33, 0 4px 10px ${bgColor}22` }
              : { background: 'transparent', color: 'var(--muted)', border: '1px solid var(--border)' }}>
            {t}
          </button>
        );
      })}
    </div>
  );
}

// ── Pivot helper ──────────────────────────────────────────────────────────────

function pivotSectors(raw: { sector: string; count: number; _timeline?: string }[]) {
  const timelines = [...new Set(raw.map(d => d._timeline).filter(Boolean))] as string[];
  if (!timelines.length) {
    return { rows: raw.map(d => ({ sector: d.sector, count: d.count })), timelines: [] };
  }
  const byKey: Record<string, Record<string, number>> = {};
  for (const d of raw) {
    if (!byKey[d.sector]) byKey[d.sector] = {};
    if (d._timeline) byKey[d.sector][d._timeline] = d.count;
  }
  const rows = Object.entries(byKey).map(([sector, vals]) => ({ sector, ...vals }));
  return { rows, timelines };
}

// ── Main component ────────────────────────────────────────────────────────────

interface Props {
  selectedDumps: string[];
  allTimelines: string[];
  activeTimeline: string;
  onTimelineSelect: (tl: string) => void;
  allCountries: string[];
  allCountryCounts: Record<string, number>;
  activeCountry: string;
  onCountrySelect: (c: string) => void;
}

export default function Dashboard({ selectedDumps, allTimelines, activeTimeline, onTimelineSelect, allCountries, allCountryCounts, activeCountry, onCountrySelect }: Props) {
  const [data,     setData]     = useState<DashboardData | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const dashboardCache = useRef(new Map<string, DashboardData>());

  const [activeSector, setActiveSector] = useState('All');
  const [allSectors,     setAllSectors]     = useState<string[]>([]);
  const [drilldown, setDrilldown] = useState<DrilldownRequest | null>(null);

  // Sticky-bar shadow + scroll-to-top affordance.
  // The dashboard scrolls inside an ancestor (<main>), not the window — so we observe
  // a top sentinel: when it leaves the viewport, we know the user has scrolled past it.
  const [scrolled, setScrolled] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const node = sentinelRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      entries => setScrolled(!(entries[0]?.isIntersecting ?? true)),
      { threshold: 0, rootMargin: '0px 0px -100% 0px' },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // Find the nearest scrolling ancestor (the <main> the page renders us into)
  // and scroll it back to the top smoothly.
  function scrollToTop() {
    let node: HTMLElement | null = rootRef.current;
    while (node && node !== document.body) {
      const style = window.getComputedStyle(node);
      if (/(auto|scroll|overlay)/.test(style.overflowY) && node.scrollHeight > node.clientHeight) {
        node.scrollTo({ top: 0, behavior: 'smooth' });
        return;
      }
      node = node.parentElement;
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  // No datasets selected → zero everything out without round-tripping the API.
  // The backend treats an empty `dumps` param as "no filter" (returns the full dataset),
  // which would show the user the same stats as "All" and contradict their intent.
  const noDatasets = selectedDumps.length === 0;
  const dumpsKey = selectedDumps.join(',');
  const dashboardKey = `${dumpsKey}::${activeSector}`;

  // Fetch whenever dumps/country/timeline/sector change.
  //
  // Three layered defenses against laggy filter interactions:
  //   1. Debounce — coalesce rapid changes into a single fetch (180ms after the
  //      last change). Clicking five sidebar dumps in a row → one request.
  //   2. Abort — any pending or in-flight request is cancelled when a new
  //      selection arrives, so the user is never waiting on stale work.
  //   3. Delay the loading indicator — only show the dim + progress bar if the
  //      fetch is still pending after 250ms, so quick refetches never flash.
  useEffect(() => {
    if (noDatasets) {
      // Resetting the dashboard state when the dataset selection empties out.
      /* eslint-disable react-hooks/set-state-in-effect */
      setData(null);
      setError('');
      setLoading(false);
      /* eslint-enable react-hooks/set-state-in-effect */
      return;
    }

    const cached = dashboardCache.current.get(dashboardKey);
    if (cached) {
      setData(cached);
      setError('');
      setLoading(false);
      return;
    }

    let loadingTimer:  ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const debounce = setTimeout(() => {
      loadingTimer = setTimeout(() => { if (!cancelled) setLoading(true); }, 250);
      fetchDashboard(
        { dumps: dumpsKey.split(','), sector: activeSector !== 'All' ? activeSector : undefined },
      )
        .then(d => {
          if (cancelled) return;
          dashboardCache.current.set(dashboardKey, d);
          setData(d);
          setError('');
          if (activeSector === 'All') {
            const secs = [...new Set(d.sectors.map(s => s.sector))].sort();
            setAllSectors(secs);
          }
        })
        .catch(e => {
          if (cancelled || e.name === 'AbortError') return;
          setError(e.message);
        })
        .finally(() => {
          if (loadingTimer) clearTimeout(loadingTimer);
          if (!cancelled) setLoading(false);
        });
    }, 180);

    return () => {
      cancelled = true;
      clearTimeout(debounce);
      if (loadingTimer) clearTimeout(loadingTimer);
    };
  }, [dumpsKey, dashboardKey, activeSector, noDatasets]);

  // Reset sector when selection, country, or timeline changes.
  useEffect(() => {
    // The available sector scope changes when dataset navigation changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActiveSector('All');
  }, [selectedDumps, activeCountry, activeTimeline]);

  // Colors keyed on allTimelines so they stay consistent regardless of active filters
  const tlColors: Record<string, string> = {};
  allTimelines.forEach((t, i) => { tlColors[t] = TL_PALETTE[i % TL_PALETTE.length]; });

  // (country counts come from allCountryCounts prop — stable totals from dump metadata)

  const { rows: sectorRows, timelines: sectorTL } = pivotSectors(data?.sectors ?? []);
  const sectorHeight = Math.max(300, sectorRows.length * 36);

  // First-paint loader: skeleton tiles matching the actual layout
  if (loading && !data) return (
    <div className="p-5 max-w-7xl mx-auto" aria-busy="true" aria-live="polite">
      <div className="skeleton h-28 mb-5" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="skeleton h-24" style={{ animationDelay: `${i * 60}ms` }} />
        ))}
      </div>
      <div className="skeleton h-72 mb-5" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="skeleton h-64" />
        <div className="skeleton h-64" />
      </div>
      <span className="sr-only">Loading dashboard…</span>
    </div>
  );

  if (error) return (
    <div className="p-8 text-center">
      <div className="text-red-400 text-sm">{error}</div>
    </div>
  );

  // "None" clicked in the sidebar — render the filter bar so the user can recover
  // (clicking a country tab re-selects all its dumps), with every stat explicitly zeroed.
  if (noDatasets) return (
    <div ref={rootRef} className="max-w-7xl mx-auto">
      <div className="px-5 pt-5 pb-4">
        <div className="rounded-xl p-4 space-y-3"
             style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <CountryTabs
            countries={allCountries}
            counts={allCountryCounts}
            active={activeCountry}
            onChange={onCountrySelect}
          />
          {allTimelines.length > 1 && (
            <TimelinePills
              timelines={allTimelines}
              tlColors={tlColors}
              active={activeTimeline}
              onChange={onTimelineSelect}
            />
          )}
        </div>
      </div>

      <div className="px-5 pb-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          {[
            { icon: '📋', label: 'Total Postings',   value: '0' },
            { icon: '💰', label: 'Salary Coverage',  value: '0%' },
            { icon: '🗓', label: 'Timeline',         value: '—' },
            { icon: '🏢', label: 'Top Sector',       value: '—' },
          ].map((k, i) => (
            <div key={i} className="rounded-xl p-4 hover-lift"
                 style={{ background: 'var(--card)', border: '1px solid var(--border)', opacity: 0.65 }}>
              <div className="text-xl mb-1" aria-hidden>{k.icon}</div>
              <div className="text-xl font-bold leading-tight nums" style={{ color: 'var(--text)' }}>{k.value}</div>
              <div className="text-xs mt-1 font-semibold" style={{ color: 'var(--muted)' }}>{k.label}</div>
              <div className="text-xs" style={{ color: 'var(--muted)' }}>no datasets selected</div>
            </div>
          ))}
        </div>

        <div className="rounded-xl p-10 text-center"
             style={{ background: 'var(--card)', border: '1px dashed var(--border)' }}>
          <div className="text-4xl mb-3" aria-hidden>📭</div>
          <div className="text-sm font-bold mb-1" style={{ color: 'var(--text)' }}>
            No datasets selected
          </div>
          <p className="text-xs max-w-md mx-auto text-pretty" style={{ color: 'var(--muted)' }}>
            Every statistic is zero because nothing is in scope. Pick datasets in the sidebar,
            or click a country above to select all of its dumps at once.
          </p>
        </div>
      </div>
    </div>
  );

  if (!data) return null;

  // Subsequent loads (filter change) — keep dashboard visible, dim & disable interactions
  const refetching = loading;

  const baseScope: DashboardScope = activeSector !== 'All' ? { sector: activeSector } : {};
  const openDrilldown = (title: string, scope: DashboardScope) => {
    setDrilldown({ title, scope: { ...baseScope, ...scope } });
  };
  const exportUrls = (dimension: DashboardDimension) => ({
    csv: dashboardExportUrl('aggregation', selectedDumps, baseScope, 'csv', dimension),
    json: dashboardExportUrl('aggregation', selectedDumps, baseScope, 'json', dimension),
  });

  return (
    <div ref={rootRef} className="max-w-7xl mx-auto">

      {/* Top sentinel — used only to decide when the floating "back to filters" FAB appears */}
      <div ref={sentinelRef} aria-hidden style={{ height: 1 }} />

      {/* ── Filter bar (in flow — no longer sticky) ───────────────────────── */}
      <div className="px-5 pt-5 pb-4">
        <div className="rounded-xl p-4 space-y-3"
             style={{ background: 'var(--card)', border: '1px solid var(--border)' }}>
          <CountryTabs
            countries={allCountries}
            counts={allCountryCounts}
            active={activeCountry}
            onChange={onCountrySelect}
          />
          {allTimelines.length > 1 && (
            <TimelinePills
              timelines={allTimelines}
              tlColors={tlColors}
              active={activeTimeline}
              onChange={onTimelineSelect}
            />
          )}

          {/* Sector filter */}
          {allSectors.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
              <span className="text-xs font-semibold" style={{ color: 'var(--muted)' }}>Sector:</span>
              <div className="flex gap-2 flex-wrap flex-1">
                <button
                  onClick={() => setActiveSector('All')}
                  className="px-3 min-h-8 rounded-full text-xs font-semibold pill-hover focus-ring"
                  style={activeSector === 'All'
                    ? { background: 'var(--card-alt)', color: 'var(--text)', border: '1px solid var(--muted)' }
                    : { background: 'transparent', color: 'var(--muted)', border: '1px solid var(--border)' }}>
                  All Sectors
                </button>
                {allSectors.map(s => (
                  <button key={s} onClick={() => setActiveSector(s)}
                    className="px-3 min-h-8 rounded-full text-xs font-semibold pill-hover focus-ring"
                    style={activeSector === s
                      ? { background: 'var(--accent)', color: '#fff', border: '1px solid var(--accent)', boxShadow: '0 1px 2px rgba(108,99,255,0.25), 0 4px 10px rgba(108,99,255,0.18)' }
                      : { background: 'transparent', color: 'var(--muted)', border: '1px solid var(--border)' }}>
                    {s}
                  </button>
                ))}
              </div>
              {activeSector !== 'All' && (
                <button
                  onClick={() => setActiveSector('All')}
                  className="inline-flex items-center gap-1 text-xs px-2 min-h-8 rounded-lg pill-hover focus-ring"
                  style={{ color: 'var(--muted)', border: '1px solid var(--border)' }}>
                  <span aria-hidden>✕</span> Clear
                </button>
              )}
            </div>
          )}
          <div className="pt-2 border-t" style={{ borderColor: 'var(--border)' }}>
            <DashboardSearch onSearch={request => setDrilldown({
              ...request,
              scope: { ...baseScope, ...request.scope },
            })} />
          </div>
        </div>
      </div>

      <div
        className="px-5 pb-5 transition-opacity duration-150"
        style={{ opacity: refetching ? 0.78 : 1 }}
        aria-busy={refetching}>
        {refetching && (
          <div className="h-0.5 -mt-px mb-3 overflow-hidden rounded-full" style={{ background: 'var(--card-alt)' }}>
            <div className="h-full w-1/3 rounded-full skeleton" />
          </div>
        )}

      {/* ── KPI row ────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        {[
          {
            icon: '📋', label: 'Total Postings',
            value: data.total.toLocaleString(),
            sub: activeCountry !== 'All' ? `in ${activeCountry}` : `${allCountries.length} countries`,
          },
          {
            icon: '💰', label: 'Salary Coverage',
            value: `${data.salary.coverage_pct}%`,
            sub: data.salary.avg_usd ? `avg $${Number(data.salary.avg_usd).toLocaleString()}/mo` : 'of postings disclose',
          },
          data.kpi_mom
            ? {
                icon: '📈', label: `${data.kpi_mom.t1} → ${data.kpi_mom.t2}`,
                value: data.kpi_mom.c2.toLocaleString(),
                delta: `${data.kpi_mom.pct > 0 ? '+' : ''}${data.kpi_mom.pct}%`,
                sub: `from ${data.kpi_mom.c1.toLocaleString()}`,
              }
            : {
                icon: '🗓', label: 'Timeline',
                value: activeTimeline !== 'All' ? activeTimeline : 'All periods',
                sub: `${data.timelines.length} snapshots`,
              },
          activeSector !== 'All'
            ? { icon: '🏭', label: 'Sector Filter', value: activeSector, sub: `${data.total.toLocaleString()} postings` }
            : { icon: '🏢', label: 'Top Sector', value: sectorRows.length > 0 ? String(sectorRows[sectorRows.length - 1]?.sector ?? '—') : '—', sub: 'by posting volume' },
        ].map((k, i) => (
          <div key={i} className="rounded-xl p-4 hover-lift card-in"
               style={{
                 background: 'var(--card)',
                 border: '1px solid var(--border)',
                 animationDelay: `${i * 40}ms`,
               }}>
            <div className="text-xl mb-1" aria-hidden>{k.icon}</div>
            <div className="text-xl font-bold leading-tight nums text-balance" style={{ color: 'var(--text)' }}>{k.value}</div>
            {'delta' in k && k.delta && (
              <div className={`text-xs font-bold mt-0.5 nums ${parseFloat(k.delta as string) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {k.delta}
              </div>
            )}
            <div className="text-xs mt-1 font-semibold" style={{ color: 'var(--muted)' }}>{k.label}</div>
            <div className="text-xs nums" style={{ color: 'var(--muted)' }}>{k.sub}</div>
          </div>
        ))}
      </div>

      {/* ── Sectors ────────────────────────────────────────────────────────── */}
      {sectorRows.length > 0 && (
        <Card
          title="📊 Postings by Sector"
          subtitle={sectorTL.length > 1 ? `Stacked by timeline — ${sectorTL.join(', ')}. Export includes the full ranking.` : 'Click a sector to browse matching postings. Export includes the full ranking.'}
          exportUrls={exportUrls('sector')}>
          {sectorTL.length > 1
            ? <HBarStacked rows={sectorRows} timelines={sectorTL} tlColors={tlColors} height={sectorHeight} />
            : <HBar data={sectorRows} x="count" y="sector" color="#6c63ff" height={sectorHeight}
                onSelect={row => openDrilldown(String(row.sector), { sector: String(row.sector) })} />
          }
        </Card>
      )}

      {/* ── Career level + Employment type + Education ─────────────────────── */}
      {(() => {
        const hasEdu = data.education && data.education.length > 0;
        const cols   = hasEdu ? 'md:grid-cols-3' : 'md:grid-cols-2';
        return (
          <div className={`grid grid-cols-1 ${cols} gap-5`}>
            {data.career_levels.length > 0 && (
              <Card title="🎯 Career Level" subtitle="Click a segment to browse matching postings." exportUrls={exportUrls('career_level')}>
                <Donut data={data.career_levels} name="level" value="count"
                  onSelect={row => openDrilldown(String(row.level), { career_level: String(row.level) })} />
              </Card>
            )}
            {data.employment_types.length > 0 && (
              <Card title="💼 Employment Type" exportUrls={exportUrls('employment_type')}>
                <Donut data={data.employment_types} name="type" value="count"
                  onSelect={row => openDrilldown(String(row.type), { employment_type: String(row.type) })} />
              </Card>
            )}
            {hasEdu && (
              <Card title="🎓 Education Requirements" subtitle="Highest credential mentioned in the posting." exportUrls={exportUrls('education')}>
                <Donut data={data.education!} name="level" value="count"
                  onSelect={row => openDrilldown(String(row.level), { education: String(row.level) })} />
              </Card>
            )}
          </div>
        );
      })()}

      {/* ── Salary ─────────────────────────────────────────────────────────── */}
      {data.salary.n_disclosed > 0 && (
        <Card
          title="💰 Salary Intelligence"
          subtitle={`${data.salary.coverage_pct}% of postings disclose salary — ${data.salary.n_disclosed.toLocaleString()} postings`}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {data.salary.by_sector.length > 0 && (
              <div>
                <div className="flex items-baseline justify-between mb-3">
                  <div className="text-xs font-semibold" style={{ color: 'var(--muted)' }}>
                    Average Monthly Salary by Sector
                  </div>
                  <div className="text-[10px] nums" style={{ color: 'var(--muted)' }}>
                    sorted by avg · USD
                  </div>
                </div>
                <SectorSalaryBars
                  data={data.salary.by_sector}
                  onSelect={row => openDrilldown(`Salary disclosures · ${row.sector}`, { sector: row.sector })}
                />
              </div>
            )}
            {data.salary.distribution.length > 0 && (
              <div>
                <div className="flex items-baseline justify-between mb-3">
                  <div className="text-xs font-semibold" style={{ color: 'var(--muted)' }}>
                    Salary Brackets (USD / month)
                  </div>
                  <div className="text-[10px] nums" style={{ color: 'var(--muted)' }}>
                    peak highlighted
                  </div>
                </div>
                <SalaryBracketBars
                  data={data.salary.distribution}
                  onSelect={row => openDrilldown(`Salary ${row.bracket}`, { salary_bracket: row.bracket })}
                />
              </div>
            )}
          </div>
        </Card>
      )}

      {/* ── Skills ─────────────────────────────────────────────────────────── */}
      {data.skills.length > 0 && (
        <Card title="🛠 Top In-Demand Skills" subtitle="The chart shows top results; export includes every extracted skill."
          exportUrls={exportUrls('skill')}>
          <HBar data={data.skills} x="count" y="skill" color="#a855f7"
            height={Math.max(280, data.skills.length * 30)}
            onSelect={row => openDrilldown(String(row.skill), { skill: String(row.skill) })} />
        </Card>
      )}

      {/* ── Job titles ─────────────────────────────────────────────────────── */}
      {data.job_titles.length > 0 && (
        <Card title="📋 Most Advertised Positions" exportUrls={exportUrls('title')}>
          <HBar data={data.job_titles} x="count" y="title" color="#ffd93d"
            height={Math.max(280, data.job_titles.length * 30)}
            onSelect={row => openDrilldown(String(row.title), { title: String(row.title) })} />
        </Card>
      )}

      {/* ── Companies ──────────────────────────────────────────────────────── */}
      {data.companies.length > 0 && (
        <Card title="🏢 Top Hiring Companies" exportUrls={exportUrls('company')}>
          <HBar data={data.companies} x="count" y="company" color="#4ecdc4"
            height={Math.max(240, data.companies.length * 32)}
            onSelect={row => openDrilldown(String(row.company), { company: String(row.company) })} />
        </Card>
      )}

      {/* ── Experience + Company size + Gender ──────────────────────────────── */}
      {(() => {
        const hasGender = data.gender && data.gender.length > 0;
        const cols      = hasGender ? 'md:grid-cols-3' : 'md:grid-cols-2';
        return (
          <div className={`grid grid-cols-1 ${cols} gap-5`}>
            {data.experience.length > 0 && (
              <Card title="📅 Experience Required" exportUrls={exportUrls('experience')}>
                {/* HBar gives long labels like "Minimum 10 years" their own row instead of
                    pile-up-and-rotate on the X-axis the way VBar did. Sort + display
                    happens inside HBar (it reverses for top-largest-at-top). */}
                <HBar
                  data={[...data.experience].sort((a, b) => b.count - a.count)}
                  x="count" y="experience" color="#ff8e53"
                  height={Math.max(240, data.experience.length * 28)}
                  onSelect={row => openDrilldown(String(row.experience), { experience: String(row.experience) })} />
              </Card>
            )}
            {data.company_size.length > 0 && (
              <Card title="🏭 Company Size" exportUrls={exportUrls('company_size')}>
                <Donut data={data.company_size} name="size" value="count"
                  onSelect={row => openDrilldown(String(row.size), { company_size: String(row.size) })} />
              </Card>
            )}
            {hasGender && (
              <Card title="⚧ Gender Preference" subtitle="Most postings do not specify; this is the split among those that do." exportUrls={exportUrls('gender')}>
                <Donut data={data.gender!} name="preference" value="count"
                  onSelect={row => openDrilldown(String(row.preference), { gender: String(row.preference) })} />
              </Card>
            )}
          </div>
        );
      })()}

      {/* ── Language + Location ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {data.languages.length > 0 && (
          <Card title="🗣 Language Requirements" exportUrls={exportUrls('language')}>
            <HBar data={data.languages} x="count" y="language"
              height={Math.max(260, data.languages.length * 42)}
              onSelect={row => openDrilldown(String(row.language), { language: String(row.language) })} />
          </Card>
        )}
        {data.locations.length > 0 && (
          <Card title="📍 Top Locations" exportUrls={exportUrls('location')}>
            <Donut data={data.locations} name="city" value="count"
              onSelect={row => openDrilldown(String(row.city), { location: String(row.city) })} />
          </Card>
        )}
      </div>

      {/* ── GCC Bilingual & Workplace Signals ──────────────────────────────────
          Bilingual portal coverage, remote/hybrid mention rate, and
          nationalization signals (Saudization / Emiratization / Qatarization)
          are GCC-specific patterns surfaced from Arabic-page content. Each
          card renders only when its data is present, so this block becomes
          invisible on deployments whose backend hasn't shipped them yet. */}
      {(() => {
        const hasBilingual = data.bilingual       && data.bilingual.length       > 0;
        const hasRemote    = data.remote          && data.remote.length          > 0;
        const hasNat       = data.nationalization && data.nationalization.length > 0;
        if (!hasBilingual && !hasRemote && !hasNat) return null;
        return (
          <>
            {hasBilingual && (
              <Card
                title="🌐 Bilingual Posting Coverage"
                subtitle="Share of postings present on the English portal, Arabic portal, or both."
                exportUrls={exportUrls('bilingual')}>
                <BilingualBars
                  data={data.bilingual!}
                  onSelect={row => openDrilldown(
                    `${row.country} · ${row.segment === 'both' ? 'Bilingual' : row.segment === 'en_only' ? 'English only' : 'Arabic only'}`,
                    { country: row.country, bilingual: row.segment },
                  )}
                />
              </Card>
            )}

            <div className={`grid grid-cols-1 ${hasRemote && hasNat ? 'md:grid-cols-2' : ''} gap-5`}>
              {hasRemote && (
                <Card
                  title="🏠 Remote / Hybrid Work"
                  subtitle="% of postings mentioning remote, hybrid, or work-from-home."
                  exportUrls={exportUrls('remote')}>
                  <CountryPctBars
                    data={data.remote!}
                    accent="#00c9a7"
                    onSelect={row => openDrilldown(
                      `Remote postings · ${row.country}`,
                      { country: row.country, remote: 'remote' },
                    )}
                  />
                </Card>
              )}
              {hasNat && (
                <Card
                  title="🪪 Nationalization Signals"
                  subtitle="% of postings mentioning Saudization / Emiratization / Qatarization."
                  exportUrls={exportUrls('nationalization')}>
                  <CountryPctBars
                    data={data.nationalization!}
                    accent="#ffd93d"
                    onSelect={row => openDrilldown(
                      `Nationalization · ${row.country}`,
                      { country: row.country, nationalization: 'mentioned' },
                    )}
                  />
                </Card>
              )}
            </div>
          </>
        );
      })()}

      {/* ── Most-frequent Arabic terms (from Original_Page_Content) ──────── */}
      {data.arabic_terms && data.arabic_terms.length > 0 && (
        <Card
          title="🔤 Most Frequent Arabic Terms"
          subtitle="Top terms extracted from Arabic posting content. Click a term to browse matching postings."
          exportUrls={exportUrls('arabic_term')}>
          <ArabicTermsBars
            data={data.arabic_terms}
            onSelect={row => openDrilldown(row.term, { arabic_term: row.term })}
          />
        </Card>
      )}

      {/* ── Country comparison (only visible on "All" tab) ─────────────────── */}
      {activeCountry === 'All' && data.country_comparison.length > 1 && (
        <Card title="🌍 Volume by Country" subtitle="Share of total postings across selected datasets" exportUrls={exportUrls('country')}>
          <Donut data={data.country_comparison} name="country" value="count"
            onSelect={row => openDrilldown(String(row.country), { country: String(row.country) })} />
        </Card>
      )}

      {/* ── Trends ─────────────────────────────────────────────────────────── */}
      {data.trends && (
        <Card
          title="📈 Market Trends"
          subtitle={`${data.trends.t1} → ${data.trends.t2} · ${data.trends.n1.toLocaleString()} → ${data.trends.n2.toLocaleString()} postings`}>
          <div className="flex items-center gap-3 mb-4">
            <span className={`text-2xl font-bold nums ${data.trends.overall_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {data.trends.overall_pct > 0 ? '+' : ''}{data.trends.overall_pct}%
            </span>
            <span className="text-sm" style={{ color: 'var(--muted)' }}>overall change</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="text-xs font-bold text-green-400 mb-3 flex items-center gap-2">
                ▲ Growing Sectors
              </div>
              {data.trends.growing.length === 0
                ? <div className="text-xs" style={{ color: 'var(--muted)' }}>None in current selection</div>
                : data.trends.growing.map(r => (
                <div key={r.sector} className="flex items-center gap-3 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold truncate" style={{ color: 'var(--text)' }}>{r.sector}</div>
                    <div className="text-xs nums" style={{ color: 'var(--muted)' }}>
                      {r.count_t1.toLocaleString()} → {r.count_t2.toLocaleString()}
                    </div>
                  </div>
                  <span className="text-xs font-bold nums text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full shrink-0">
                    +{r.pct_change}%
                  </span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-xs font-bold text-red-400 mb-3">▼ Declining Sectors</div>
              {data.trends.declining.length === 0
                ? <div className="text-xs" style={{ color: 'var(--muted)' }}>None in current selection</div>
                : data.trends.declining.map(r => (
                <div key={r.sector} className="flex items-center gap-3 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold truncate" style={{ color: 'var(--text)' }}>{r.sector}</div>
                    <div className="text-xs nums" style={{ color: 'var(--muted)' }}>
                      {r.count_t1.toLocaleString()} → {r.count_t2.toLocaleString()}
                    </div>
                  </div>
                  <span className="text-xs font-bold nums text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full shrink-0">
                    {r.pct_change}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}

      </div>

      {/* Floating "back to filters" — surfaces only after you've scrolled past the bar.
          Shows a badge with the active-filter count so you know the current scope at a glance. */}
      {(() => {
        const activeFilters = [
          activeCountry  !== 'All' ? activeCountry  : null,
          activeTimeline !== 'All' ? activeTimeline : null,
          activeSector   !== 'All' ? activeSector   : null,
        ].filter(Boolean) as string[];
        const count = activeFilters.length;
        const label = count > 0
          ? `Back to filters — ${count} active: ${activeFilters.join(', ')}`
          : 'Back to filters';
        return (
          <button
            onClick={scrollToTop}
            aria-label={label}
            title={label}
            className={`fab-top ${scrolled ? 'is-visible' : ''} relative inline-flex items-center justify-center h-11 w-11 rounded-full focus-ring active:scale-[0.96]`}
            style={{
              background: 'var(--card)',
              color: 'var(--text)',
              border: '1px solid var(--border)',
              boxShadow: '0 4px 14px rgba(0,0,0,0.18), 0 1px 2px rgba(0,0,0,0.08)',
            }}>
            {/* Filter funnel — signals the destination, not just "up" */}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M3 5h18l-7 9v6l-4-2v-4L3 5z" />
            </svg>
            {count > 0 && <span className="fab-badge" aria-hidden>{count}</span>}
          </button>
        );
      })()}

      {drilldown && (
        <PostingDrawer
          key={`${drilldown.title}:${JSON.stringify(drilldown.scope)}`}
          request={drilldown}
          dumps={selectedDumps}
          onClose={() => setDrilldown(null)}
        />
      )}
    </div>
  );
}
