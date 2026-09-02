import type {
  DashboardData, DashboardDimension, DashboardScope, DatasetsResponse,
  JobPosting, PostingPage,
} from './types';

const DATA_ROOT = '/data/dashboard';
const SALARY_LABELS = [
  '<$500', '$500-1K', '$1K-1.5K', '$1.5K-2K', '$2K-3K',
  '$3K-5K', '$5K-7.5K', '$7.5K-10K', '$10K-15K', '$15K+',
];
const COMPANY_SIZE_ORDER = [
  '1–50', '51–200', '201–500', '501–1,000', '1,001–5,000',
  '5,001–10,000', '10,001–50,000', '50,000+',
];

interface StaticManifest {
  schema_version: number;
  data_version: string;
  generated_at: string;
  record_count: number;
  analytics_file: string;
  posting_files: Record<string, string>;
  datasets: DatasetsResponse & { sources?: string[] };
}

interface AnalyticsRecord {
  key: string;
  dump: string;
  country: string | null;
  timeline: string | null;
  title: string | null;
  company: string | null;
  sector: string | null;
  category: string | null;
  location: string | null;
  city: string | null;
  salary: string | null;
  salaryMid: number | null;
  salaryBracket: string | null;
  employmentType: string | null;
  careerLevel: string | null;
  experience: string | null;
  companySize: string | null;
  companySizeBucket: string | null;
  skills: string[];
  education: string | null;
  gender: string | null;
  language: string | null;
  remote: boolean;
  nationalization: boolean;
  bilingual: boolean;
  arabicTerms: string[];
}

interface PostingDetail {
  key: string;
  job_id?: string | number | null;
  description?: string | null;
  qualifications?: string | null;
  url?: string | null;
  post_date?: string | null;
}

let manifestPromise: Promise<StaticManifest> | null = null;
let analyticsPromise: Promise<AnalyticsRecord[]> | null = null;
const detailPromises = new Map<string, Promise<Map<string, PostingDetail>>>();
const dashboardCache = new Map<string, DashboardData>();

async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Static dashboard data is unavailable (${response.status})`);
  return response.json() as Promise<T>;
}

async function getManifest(): Promise<StaticManifest> {
  manifestPromise ??= fetchJson<StaticManifest>(`${DATA_ROOT}/manifest.json`);
  return manifestPromise;
}

async function getAnalytics(signal?: AbortSignal): Promise<AnalyticsRecord[]> {
  if (!analyticsPromise) {
    analyticsPromise = getManifest().then(manifest => (
      fetchJson<AnalyticsRecord[]>(`${DATA_ROOT}/${manifest.analytics_file}`, signal)
    ));
  }
  return analyticsPromise;
}

async function getDetails(dumpIds: string[]): Promise<Map<string, PostingDetail>> {
  const manifest = await getManifest();
  const maps = await Promise.all(dumpIds.map(async dumpId => {
    const filename = manifest.posting_files[dumpId];
    if (!filename) return new Map<string, PostingDetail>();
    if (!detailPromises.has(dumpId)) {
      detailPromises.set(dumpId, fetchJson<PostingDetail[]>(`${DATA_ROOT}/${filename}`)
        .then(rows => new Map(rows.map(row => [row.key, row]))));
    }
    return detailPromises.get(dumpId)!;
  }));
  return new Map(maps.flatMap(map => [...map.entries()]));
}

export async function fetchStaticDatasets(): Promise<DatasetsResponse> {
  return (await getManifest()).datasets;
}

export function preloadStaticDashboard(): void {
  void getAnalytics().catch(() => {});
}

function caseEqual(left: string | null | undefined, right: string | null | undefined) {
  return (left ?? '').localeCompare(right ?? '', undefined, { sensitivity: 'accent' }) === 0
    || (left ?? '').toLocaleLowerCase() === (right ?? '').toLocaleLowerCase();
}

function isPresent(value: string | null | undefined): value is string {
  return Boolean(value?.trim());
}

function sortTimelines(values: string[]) {
  const monthOrder: Record<string, number> = {
    Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5,
    Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11,
  };
  return [...new Set(values)].sort((a, b) => {
    const [am, ay] = a.split(' ');
    const [bm, by] = b.split(' ');
    return (Number(ay) - Number(by)) || ((monthOrder[am] ?? 99) - (monthOrder[bm] ?? 99));
  });
}

function counts(values: Array<string | null | undefined>, limit?: number) {
  const result = new Map<string, number>();
  values.filter(isPresent).forEach(value => result.set(value, (result.get(value) ?? 0) + 1));
  return [...result.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, limit)
    .map(([label, count]) => ({ label, count }));
}

function filterDashboardRecords(records: AnalyticsRecord[], dumps: string[], sector?: string) {
  const selected = new Set(dumps);
  return records.filter(record => selected.has(record.dump) && (!sector || caseEqual(record.sector, sector)));
}

function countrySignalRows(records: AnalyticsRecord[], field: 'remote' | 'nationalization') {
  const groups = new Map<string, AnalyticsRecord[]>();
  records.forEach(record => {
    if (!record.country) return;
    const group = groups.get(record.country) ?? [];
    group.push(record);
    groups.set(record.country, group);
  });
  return [...groups.entries()].flatMap(([country, group]) => {
    const count = group.filter(record => record[field]).length;
    return count ? [{ country, count, pct: Math.round(count / group.length * 1000) / 10 }] : [];
  });
}

function buildDashboard(records: AnalyticsRecord[]): DashboardData {
  const total = records.length;
  const timelines = sortTimelines(records.map(record => record.timeline).filter(isPresent));
  const countries = [...new Set(records.map(record => record.country).filter(isPresent))].sort();

  const sectorCounts = counts(records.map(record => record.sector));
  const topSectors = new Set(sectorCounts.slice(0, 15).map(row => row.label));
  const sectors: DashboardData['sectors'] = timelines.length > 1
    ? [...new Map(records
        .filter(record => record.sector && record.timeline && topSectors.has(record.sector))
        .map(record => [`${record.sector}\u0000${record.timeline}`, { sector: record.sector!, _timeline: record.timeline!, count: 0 }]))
        .values()]
    : sectorCounts.slice(0, 15).map(row => ({ sector: row.label, count: row.count }));
  if (timelines.length > 1) {
    const keyed = new Map(sectors.map(row => [`${row.sector}\u0000${row._timeline}`, row]));
    records.forEach(record => {
      const row = keyed.get(`${record.sector}\u0000${record.timeline}`);
      if (row) row.count += 1;
    });
  }

  const salaryRecords = records.filter(record => record.salaryMid !== null);
  const salaryDistribution = SALARY_LABELS.map(bracket => ({
    bracket,
    count: salaryRecords.filter(record => record.salaryBracket === bracket).length,
  }));
  const sectorSalary = new Map<string, number[]>();
  salaryRecords.forEach(record => {
    if (!record.sector || record.salaryMid === null) return;
    const values = sectorSalary.get(record.sector) ?? [];
    values.push(record.salaryMid);
    sectorSalary.set(record.sector, values);
  });
  const salaryBySector = [...sectorSalary.entries()]
    .filter(([, values]) => values.length >= 3)
    .map(([sector, values]) => ({
      sector,
      avg_usd: Math.round(values.reduce((sum, value) => sum + value, 0) / values.length),
      count: values.length,
    }))
    .sort((a, b) => b.avg_usd - a.avg_usd)
    .slice(0, 15);

  const skillCounts = counts(records.flatMap(record => record.skills.map(skill => skill.toLocaleLowerCase())), 20)
    .map(row => ({ skill: row.label, count: row.count, pct: Math.round(row.count / Math.max(total, 1) * 1000) / 10 }));

  let trends: DashboardData['trends'] = null;
  if (timelines.length >= 2) {
    const t1 = timelines[0];
    const t2 = timelines[timelines.length - 1];
    const first = records.filter(record => record.timeline === t1);
    const last = records.filter(record => record.timeline === t2);
    const c1 = new Map(counts(first.map(record => record.sector)).map(row => [row.label, row.count]));
    const c2 = new Map(counts(last.map(record => record.sector)).map(row => [row.label, row.count]));
    const n1 = Math.max(first.length, 1);
    const n2 = Math.max(last.length, 1);
    const rows = [...new Set([...c1.keys(), ...c2.keys()])].flatMap(sector => {
      const firstShare = (c1.get(sector) ?? 0) / n1;
      const lastShare = (c2.get(sector) ?? 0) / n2;
      return firstShare > 0.005 ? [{
        sector,
        count_t1: c1.get(sector) ?? 0,
        count_t2: c2.get(sector) ?? 0,
        pct_change: Math.round((lastShare - firstShare) / firstShare * 1000) / 10,
      }] : [];
    }).sort((a, b) => b.pct_change - a.pct_change);
    trends = {
      t1, t2, n1, n2,
      overall_pct: Math.round((n2 - n1) / n1 * 1000) / 10,
      growing: rows.filter(row => row.pct_change > 0).slice(0, 5),
      declining: rows.filter(row => row.pct_change < 0).slice(-5).reverse(),
    };
  }

  const timelineCounts = new Map(counts(records.map(record => record.timeline)).map(row => [row.label, row.count]));
  const kpi_mom = timelines.length >= 2 ? (() => {
    const t1 = timelines[0];
    const t2 = timelines[timelines.length - 1];
    const c1 = timelineCounts.get(t1) ?? 0;
    const c2 = timelineCounts.get(t2) ?? 0;
    return { t1, t2, c1, c2, pct: c1 ? Math.round((c2 - c1) / c1 * 1000) / 10 : 0 };
  })() : null;

  const bilingualGroups = new Map<string, { country: string; en_only: number; ar_only: number; both: number }>();
  records.forEach(record => {
    if (!record.country) return;
    const row = bilingualGroups.get(record.country) ?? { country: record.country, en_only: 0, ar_only: 0, both: 0 };
    if (record.bilingual) row.both += 1;
    else row.en_only += 1;
    bilingualGroups.set(record.country, row);
  });

  const arabicTerms = counts(records.flatMap(record => record.arabicTerms), 30)
    .map(row => ({ term: row.label, count: row.count }));

  return {
    total,
    countries,
    timelines,
    kpi_mom,
    sectors,
    career_levels: counts(records.map(record => record.careerLevel)).map(row => ({ level: row.label, count: row.count })),
    employment_types: counts(records.map(record => record.employmentType)).map(row => ({ type: row.label, count: row.count })),
    salary: {
      coverage_pct: Math.round(salaryRecords.length / Math.max(total, 1) * 1000) / 10,
      n_disclosed: salaryRecords.length,
      avg_usd: salaryRecords.length
        ? Math.round(salaryRecords.reduce((sum, record) => sum + (record.salaryMid ?? 0), 0) / salaryRecords.length)
        : null,
      distribution: salaryDistribution,
      by_sector: salaryBySector,
    },
    skills: skillCounts,
    experience: counts(records.map(record => record.experience), 15).map(row => ({ experience: row.label, count: row.count })),
    company_size: counts(records.map(record => record.companySizeBucket))
      .sort((a, b) => COMPANY_SIZE_ORDER.indexOf(a.label) - COMPANY_SIZE_ORDER.indexOf(b.label))
      .map(row => ({ size: row.label, count: row.count })),
    languages: counts(records.map(record => record.language), 8).map(row => ({ language: row.label, count: row.count })),
    locations: counts(records.map(record => record.city), 10).map(row => ({ city: row.label, count: row.count })),
    job_titles: counts(records.map(record => record.title), 20).map(row => ({ title: row.label, count: row.count })),
    companies: counts(records.map(record => record.company), 15).map(row => ({ company: row.label, count: row.count })),
    country_comparison: counts(records.map(record => record.country)).map(row => ({ country: row.label, count: row.count })),
    trends,
    education: counts(records.map(record => record.education)).map(row => ({ level: row.label, count: row.count })),
    gender: counts(records.map(record => record.gender)).map(row => ({ preference: row.label, count: row.count })),
    remote: countrySignalRows(records, 'remote'),
    nationalization: countrySignalRows(records, 'nationalization'),
    bilingual: [...bilingualGroups.values()].filter(row => row.both > 0),
    arabic_terms: arabicTerms,
  };
}

export async function fetchStaticDashboard(
  params: { dumps: string[]; sector?: string },
  signal?: AbortSignal,
): Promise<DashboardData> {
  const key = `${[...params.dumps].sort().join(',')}::${params.sector ?? ''}`;
  const cached = dashboardCache.get(key);
  if (cached) return cached;
  const records = filterDashboardRecords(await getAnalytics(signal), params.dumps, params.sector);
  if (!records.length) throw new Error('No data for selected filters');
  const result = buildDashboard(records);
  dashboardCache.set(key, result);
  return result;
}

function filterByScope(records: AnalyticsRecord[], dumps: string[], scope: DashboardScope) {
  const selected = new Set(dumps);
  return records.filter(record => {
    if (!selected.has(record.dump)) return false;
    if (scope.country && !caseEqual(record.country, scope.country)) return false;
    if (scope.timeline && !caseEqual(record.timeline, scope.timeline)) return false;
    if (scope.sector && !caseEqual(record.sector, scope.sector)) return false;
    if (scope.company && !caseEqual(record.company, scope.company)) return false;
    if (scope.title && !caseEqual(record.title, scope.title)) return false;
    if (scope.skill && !record.skills.some(skill => caseEqual(skill, scope.skill))) return false;
    if (scope.location && !caseEqual(record.city, scope.location)) return false;
    if (scope.career_level && !caseEqual(record.careerLevel, scope.career_level)) return false;
    if (scope.employment_type && !caseEqual(record.employmentType, scope.employment_type)) return false;
    if (scope.experience && !caseEqual(record.experience, scope.experience)) return false;
    if (scope.company_size && !caseEqual(record.companySizeBucket, scope.company_size)) return false;
    if (scope.language && !caseEqual(record.language, scope.language)) return false;
    if (scope.salary_bracket && !caseEqual(record.salaryBracket, scope.salary_bracket)) return false;
    if (scope.education && !caseEqual(record.education, scope.education)) return false;
    if (scope.gender && !caseEqual(record.gender, scope.gender)) return false;
    if (scope.remote && !record.remote) return false;
    if (scope.nationalization && !record.nationalization) return false;
    if (scope.bilingual === 'both' && !record.bilingual) return false;
    if (scope.bilingual === 'en_only' && record.bilingual) return false;
    if (scope.arabic_term && !record.arabicTerms.some(term => caseEqual(term, scope.arabic_term))) return false;
    return true;
  });
}

function posting(record: AnalyticsRecord, detail?: PostingDetail): JobPosting {
  return {
    job_id: detail?.job_id ?? record.key,
    title: record.title ?? undefined,
    company: record.company ?? undefined,
    sector: record.sector ?? record.category ?? undefined,
    category: record.category ?? undefined,
    location: record.location ?? undefined,
    salary: record.salary ?? undefined,
    employment_type: record.employmentType ?? undefined,
    career_level: record.careerLevel ?? undefined,
    experience: record.experience ?? undefined,
    company_size: record.companySize ?? undefined,
    description: detail?.description ?? undefined,
    qualifications: detail?.qualifications ?? undefined,
    education: record.education ?? undefined,
    language: record.language ?? undefined,
    url: detail?.url ?? undefined,
    post_date: detail?.post_date ?? undefined,
    country: record.country ?? undefined,
    timeline: record.timeline ?? undefined,
    skills: record.skills,
  };
}

export async function fetchStaticPostings(
  dumps: string[],
  scope: DashboardScope,
  page: number,
  pageSize = 20,
): Promise<PostingPage> {
  let records = filterByScope(await getAnalytics(), dumps, scope);
  const query = scope.query?.trim().toLocaleLowerCase();
  let details: Map<string, PostingDetail> | null = null;
  if (query) {
    details = await getDetails([...new Set(records.map(record => record.dump))]);
    records = records.filter(record => {
      const detail = details!.get(record.key);
      return [record.title, record.company, record.sector, record.category, record.location,
        record.skills.join(' '), detail?.description, detail?.qualifications]
        .filter(Boolean).join(' ').toLocaleLowerCase().includes(query);
    });
  }
  const total = records.length;
  const pageRecords = records.slice((page - 1) * pageSize, page * pageSize);
  details ??= await getDetails([...new Set(pageRecords.map(record => record.dump))]);
  return {
    total, page, page_size: pageSize,
    items: pageRecords.map(record => posting(record, details!.get(record.key))),
  };
}

function aggregate(records: AnalyticsRecord[], dimension: DashboardDimension): Record<string, unknown>[] {
  if (dimension === 'skill') return counts(records.flatMap(record => record.skills)).map(row => ({ label: row.label, count: row.count }));
  if (dimension === 'remote') return countrySignalRows(records, 'remote').map(row => ({ label: row.country, pct: row.pct, count: row.count }));
  if (dimension === 'nationalization') return countrySignalRows(records, 'nationalization').map(row => ({ label: row.country, pct: row.pct, count: row.count }));
  if (dimension === 'bilingual') {
    const groups = new Map<string, { label: string; en_only: number; ar_only: number; both: number }>();
    records.forEach(record => {
      if (!record.country) return;
      const row = groups.get(record.country) ?? { label: record.country, en_only: 0, ar_only: 0, both: 0 };
      if (record.bilingual) row.both += 1; else row.en_only += 1;
      groups.set(record.country, row);
    });
    return [...groups.values()];
  }
  if (dimension === 'arabic_term') return counts(records.flatMap(record => record.arabicTerms)).map(row => ({ label: row.label, count: row.count }));
  if (dimension === 'salary_sector') {
    return buildDashboard(records).salary.by_sector.map(row => ({ label: row.sector, avg_usd: row.avg_usd, count: row.count }));
  }
  const values: Record<DashboardDimension, Array<string | null | undefined>> = {
    sector: records.map(record => record.sector),
    company: records.map(record => record.company),
    title: records.map(record => record.title),
    location: records.map(record => record.city),
    career_level: records.map(record => record.careerLevel),
    employment_type: records.map(record => record.employmentType),
    experience: records.map(record => record.experience),
    company_size: records.map(record => record.companySizeBucket),
    language: records.map(record => record.language),
    country: records.map(record => record.country),
    salary_bracket: records.map(record => record.salaryBracket),
    education: records.map(record => record.education),
    gender: records.map(record => record.gender),
    skill: [], remote: [], nationalization: [], bilingual: [], arabic_term: [], salary_sector: [],
  };
  return counts(values[dimension]).map(row => ({ label: row.label, count: row.count }));
}

function serializeCsv(rows: Record<string, unknown>[]) {
  const fields = [...new Set(rows.flatMap(row => Object.keys(row)))];
  const escape = (value: unknown) => {
    const text = Array.isArray(value) ? value.join(' | ') : String(value ?? '');
    return `"${text.replaceAll('"', '""')}"`;
  };
  return `\uFEFF${fields.join(',')}\n${rows.map(row => fields.map(field => escape(row[field])).join(',')).join('\n')}`;
}

function download(content: string, contentType: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: contentType }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function downloadStaticExport(
  kind: 'postings' | 'aggregation',
  dumps: string[],
  scope: DashboardScope,
  format: 'csv' | 'json',
  dimension?: DashboardDimension,
) {
  let rows: Record<string, unknown>[];
  if (kind === 'postings') {
    const records = filterByScope(await getAnalytics(), dumps, scope);
    const details = await getDetails([...new Set(records.map(record => record.dump))]);
    rows = records.map(record => posting(record, details.get(record.key)) as unknown as Record<string, unknown>);
  } else {
    if (!dimension) throw new Error('An aggregation dimension is required');
    rows = aggregate(filterByScope(await getAnalytics(), dumps, scope), dimension);
  }
  const content = format === 'json'
    ? JSON.stringify(rows, null, 2)
    : serializeCsv(rows);
  download(content, format === 'json' ? 'application/json' : 'text/csv;charset=utf-8', `mihna-${kind}.${format}`);
}
