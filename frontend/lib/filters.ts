import type { DashboardScope, DumpInfo } from './types';

export const FILTER_LABELS = {
  sector: 'Sector', employment_type: 'Employment type', career_level: 'Career level',
  company: 'Company', experience: 'Experience', salary_bucket: 'Salary range',
} as const;
export type JobFilters = Partial<Record<keyof typeof FILTER_LABELS, string>>;
export type DatasetScope = { country: string; timeline: string; source: string };
export const ALL_DATASETS: DatasetScope = { country: 'All', timeline: 'All', source: 'All' };

export function selectDatasetIds(dumps: DumpInfo[], scope: DatasetScope): string[] {
  return dumps.filter(dump => (
    (scope.country === 'All' || dump._country === scope.country)
    && (scope.timeline === 'All' || dump._timeline === scope.timeline)
    && (scope.source === 'All' || dump._source === scope.source)
  )).map(dump => dump._dump_id);
}

export function postingScope(filters: JobFilters): DashboardScope {
  const { salary_bucket, ...rest } = filters;
  return { ...rest, ...(salary_bucket ? { salary_bracket: salary_bucket } : {}) };
}
