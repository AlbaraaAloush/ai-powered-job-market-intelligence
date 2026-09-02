export interface DumpInfo {
  _dump_id: string;
  _country: string;
  _timeline: string;
  _dump_label: string;
  count: number;
}

export interface DatasetsResponse {
  dumps: DumpInfo[];
  timelines: string[];
}

export interface DashboardData {
  total: number;
  countries: string[];
  timelines: string[];
  kpi_mom: { t1: string; t2: string; c1: number; c2: number; pct: number } | null;
  sectors: { sector: string; count: number; _timeline?: string }[];
  career_levels: { level: string; count: number }[];
  employment_types: { type: string; count: number }[];
  salary: {
    coverage_pct: number;
    n_disclosed: number;
    avg_usd: number | null;
    distribution: { bracket: string; count: number }[];
    by_sector: { sector: string; avg_usd: number; count: number }[];
  };
  skills: { skill: string; count: number; pct: number }[];
  experience: { experience: string; count: number }[];
  company_size: { size: string; count: number }[];
  languages: { language: string; count: number }[];
  locations: { city: string; count: number }[];
  job_titles: { title: string; count: number }[];
  companies: { company: string; count: number }[];
  country_comparison: { country: string; count: number }[];
  trends: {
    t1: string; t2: string; n1: number; n2: number; overall_pct: number;
    growing: { sector: string; count_t1: number; count_t2: number; pct_change: number }[];
    declining: { sector: string; count_t1: number; count_t2: number; pct_change: number }[];
  } | null;

  // ── Bilingual / GCC-specific signals (optional — present when backend supports them).
  //    Cards render only when the array exists and is non-empty, so the dashboard
  //    degrades gracefully if a deployment hasn't shipped these fields yet.
  education?:       { level: string; count: number }[];
  gender?:          { preference: string; count: number }[];
  remote?:          { country: string; pct: number; count: number }[];
  nationalization?: { country: string; pct: number; count: number }[];
  bilingual?:       { country: string; en_only: number; ar_only: number; both: number }[];
  arabic_terms?:    { term: string; count: number }[];
}

export type DashboardDimension =
  | 'sector' | 'skill' | 'company' | 'title' | 'location'
  | 'career_level' | 'employment_type' | 'experience' | 'company_size'
  | 'language' | 'country' | 'salary_bracket' | 'salary_sector'
  | 'education' | 'gender' | 'remote' | 'nationalization' | 'bilingual' | 'arabic_term';

export interface DashboardScope {
  query?: string;
  country?: string;
  timeline?: string;
  sector?: string;
  company?: string;
  title?: string;
  skill?: string;
  location?: string;
  career_level?: string;
  employment_type?: string;
  experience?: string;
  company_size?: string;
  language?: string;
  salary_bracket?: string;
  education?: string;
  gender?: string;
  remote?: string;          // 'remote' | 'hybrid' | 'onsite'
  nationalization?: string; // 'mentioned' | country code
  bilingual?: string;       // 'en_only' | 'ar_only' | 'both'
  arabic_term?: string;
}

export interface JobPosting {
  job_id?: string | number;
  title?: string;
  company?: string;
  sector?: string;
  category?: string;
  location?: string;
  salary?: string;
  employment_type?: string;
  career_level?: string;
  experience?: string;
  company_size?: string;
  description?: string;
  qualifications?: string;
  education?: string;
  language?: string;
  url?: string;
  post_date?: string;
  country?: string;
  timeline?: string;
  skills: string[];
}

export interface PostingPage {
  total: number;
  page: number;
  page_size: number;
  items: JobPosting[];
}

export interface SemanticHit {
  source_id?: string;
  title: string;
  company: string;
  sector: string;
  timeline: string;
  country: string;
  score?: number;
  url?: string;
  scores?: Record<string, number>;
}

export interface RetrievalInfo {
  trace_id?: string;
  mode?: string;
  scope?: string;
  evidence_count?: number;
  rewritten_query?: string;
  versions?: Record<string, string>;
  decomposed: {
    filters: Record<string, string>;
    semantic_query: string;
    needs_aggregation: boolean;
    analysis_types: string[];
    resolved_question: string;
  } | Record<string, never>;
  needs_agg: boolean;
  layers_used: string[];
  sql_snippet: string;
  semantic_hits: SemanticHit[];
}

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;
  retrieval?: RetrievalInfo;
}
