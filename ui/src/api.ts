/** Typed client for the curation API. Vite proxies /api to the FastAPI service. */

import type {
  AnalyzeResponse,
  Concept,
  CurationStatus,
  Reconcile,
  SearchResponse,
  SuggestResponse,
} from "./types";

const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    // A network-level failure is almost always "the API is not running".
    throw new ApiError("No se pudo contactar la API. ¿Está corriendo uvicorn?", 0);
  }

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Response had no JSON body; the status line is the best we have.
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== "") search.set(key, String(value));
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

export const api = {
  search(params: {
    q: string;
    semantic_tag?: string | null;
    curation_status?: string | null;
    limit?: number;
  }): Promise<SearchResponse> {
    return request<SearchResponse>(
      `/search${query({
        q: params.q,
        semantic_tag: params.semantic_tag ?? null,
        curation_status: params.curation_status ?? null,
        limit: params.limit ?? 25,
      })}`,
    );
  },

  suggest(q: string): Promise<SuggestResponse> {
    return request<SuggestResponse>(`/search/suggest${query({ q, limit: 8 })}`);
  },

  analyze(text: string, analyzer: string): Promise<AnalyzeResponse> {
    return request<AnalyzeResponse>(`/search/analyze${query({ text, analyzer })}`);
  },

  getConcept(id: string): Promise<Concept> {
    return request<Concept>(`/concepts/${encodeURIComponent(id)}`);
  },

  updateConcept(
    id: string,
    changes: { curation_status?: CurationStatus; curation_note?: string | null },
  ): Promise<Concept> {
    return request<Concept>(`/concepts/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(changes),
    });
  },

  reconcile(): Promise<Reconcile> {
    return request<Reconcile>("/admin/reconcile");
  },

  reindex(): Promise<{ selected: number; indexed: number; failed: number }> {
    return request("/admin/reindex", { method: "POST" });
  },
};
