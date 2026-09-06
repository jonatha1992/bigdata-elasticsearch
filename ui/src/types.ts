/** Wire types. These mirror app/schemas.py; keep them in sync by hand. */

export type CurationStatus = "draft" | "in_review" | "approved" | "rejected";

export const CURATION_STATUSES: CurationStatus[] = [
  "draft",
  "in_review",
  "approved",
  "rejected",
];

export const STATUS_LABELS: Record<CurationStatus, string> = {
  draft: "Borrador",
  in_review: "En revisión",
  approved: "Aprobado",
  rejected: "Rechazado",
};

export interface Description {
  id: number;
  term: string;
  type: "fsn" | "synonym";
  language: string;
  preferred: boolean;
  active: boolean;
}

export interface Concept {
  concept_id: string;
  fsn: string;
  semantic_tag: string;
  module: string;
  active: boolean;
  curation_status: CurationStatus;
  curation_note: string | null;
  effective_time: string | null;
  created_at: string;
  updated_at: string;
  pending_index: boolean;
  indexed_at: string | null;
  descriptions: Description[];
}

export interface SearchHit {
  concept_id: string;
  fsn: string;
  preferred_term: string;
  semantic_tag: string;
  curation_status: CurationStatus;
  active: boolean;
  score: number;
  highlight: Record<string, string[]>;
}

export interface Facet {
  value: string;
  count: number;
}

export interface SearchResponse {
  query: string;
  total: number;
  took_ms: number;
  limit: number;
  offset: number;
  hits: SearchHit[];
  facets: Record<string, Facet[]>;
}

export interface SuggestItem {
  concept_id: string;
  label: string;
  semantic_tag: string;
}

export interface SuggestResponse {
  query: string;
  items: SuggestItem[];
}

export interface AnalyzeToken {
  token: string;
  position: number;
  start_offset: number;
  end_offset: number;
  type: string;
}

export interface AnalyzeResponse {
  text: string;
  analyzer: string;
  tokens: AnalyzeToken[];
}

export interface Reconcile {
  index: string;
  concepts_in_database: number;
  documents_in_index: number;
  pending_index: number;
  in_sync: boolean;
}

export interface Filters {
  semantic_tag: string | null;
  curation_status: CurationStatus | null;
}
