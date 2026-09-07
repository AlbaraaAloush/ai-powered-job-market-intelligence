import {
  DashboardData, DashboardDimension, DashboardScope, DatasetsResponse,
  PostingPage, RetrievalInfo,
} from './types';
import {
  downloadStaticExport, fetchStaticDashboard, fetchStaticDatasets,
  fetchStaticPostings, preloadStaticDashboard,
} from './static-dashboard';
import type { JobFilters } from './filters';

// An explicitly empty value means same-origin (the nginx production stack).
// Only an undefined value falls back to the local development backend.
const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
export async function fetchDatasets(): Promise<DatasetsResponse> {
  const datasets = await fetchStaticDatasets();
  preloadStaticDashboard();
  return datasets;
}

export interface DashboardParams extends JobFilters {
  dumps: string[];
  country?: string;
  sector?: string;
  timeline?: string;
}

export async function fetchDashboard(params: DashboardParams, signal?: AbortSignal): Promise<DashboardData> {
  return fetchStaticDashboard(params, signal);
}

export async function fetchDashboardPostings(
  dumps: string[],
  scope: DashboardScope,
  page: number,
  pageSize = 20,
): Promise<PostingPage> {
  return fetchStaticPostings(dumps, scope, page, pageSize);
}

export function downloadDashboardExport(
  kind: 'postings' | 'aggregation',
  dumps: string[],
  scope: DashboardScope,
  format: 'csv' | 'json',
  dimension?: DashboardDimension,
) {
  return downloadStaticExport(kind, dumps, scope, format, dimension);
}

export interface ModelOption {
  label: string;
  value: string;
}

export async function fetchModels(): Promise<{ models: ModelOption[]; default: string }> {
  const r = await fetch(`${API}/api/models`);
  if (!r.ok) throw new Error('Failed to fetch models');
  return r.json();
}

export async function createSession(): Promise<string> {
  const r = await fetch(`${API}/api/session`, { method: 'POST' });
  const data = await r.json();
  return data.session_id;
}

export async function clearSession(sessionId: string): Promise<void> {
  await fetch(`${API}/api/session/${sessionId}`, { method: 'DELETE' });
}

export async function submitFeedback(payload: {
  trace_id: string; session_id: string; helpful: boolean; reason?: string;
  comment?: string; question?: string; answer?: string;
}): Promise<void> {
  const r = await fetch(`${API}/api/feedback`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!r.ok) throw new Error(`Feedback error: ${r.status}`);
}

// Typed stream events from the server
export type StreamEvent =
  | { type: 'retrieval'; info: RetrievalInfo }
  | { type: 'token'; token: string }
  | { type: 'done' };

export async function* streamChat(
  question: string,
  sessionId: string,
  model: string,
  dumpIds: string[],
  signal?: AbortSignal,
  filters: JobFilters = {},
): AsyncGenerator<StreamEvent> {
  const r = await fetch(`${API}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId, model, dump_ids: dumpIds, filters }),
    signal,
  });

  if (!r.ok) throw new Error(`Chat error: ${r.status}`);
  if (!r.body) return;

  const reader  = r.body.getReader();
  const decoder = new TextDecoder();
  let   buf     = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const raw = line.slice(6).trim();
      if (raw === '[DONE]') { yield { type: 'done' }; return; }
      try {
        const parsed = JSON.parse(raw);
        if (parsed.type === 'retrieval') yield { type: 'retrieval', info: parsed.info };
        else if (parsed.type === 'token' && parsed.token) yield { type: 'token', token: parsed.token };
      } catch { /* skip partial */ }
    }
  }
}
