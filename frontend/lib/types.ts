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
}

export type DashboardDimension =
  | 'sector' | 'skill' | 'company' | 'title' | 'location'
  | 'career_level' | 'employment_type' | 'experience' | 'company_size'
  | 'language' | 'country' | 'salary_bracket' | 'salary_sector';

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
  title: string;
  company: string;
  sector: string;
  timeline: string;
  country: string;
  score: number;
}

export interface RetrievalInfo {
  decomposed: {
    filters: Record<string, string>;
    semantic_query: string;
    needs_aggregation: boolean;
    analysis_types: string[];
    resolved_question: string;
  };
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
