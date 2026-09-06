import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "./api";
import { AnalyzerPeek } from "./components/AnalyzerPeek";
import { ConceptPanel } from "./components/ConceptPanel";
import { Facets } from "./components/Facets";
import { ResultList } from "./components/ResultList";
import { SearchBar } from "./components/SearchBar";
import { StatusStrip } from "./components/StatusStrip";
import { useDebounced } from "./useDebounced";
import type { Facet, Filters, SearchHit } from "./types";

const NO_FILTERS: Filters = { semantic_tag: null, curation_status: null };

export default function App() {
  const [queryText, setQueryText] = useState("");
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [facets, setFacets] = useState<Record<string, Facet[]>>({});
  const [total, setTotal] = useState(0);
  const [tookMs, setTookMs] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  const debouncedQuery = useDebounced(queryText, 250);

  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .search({
        q: debouncedQuery.trim(),
        semantic_tag: filters.semantic_tag,
        curation_status: filters.curation_status,
      })
      .then((response) => {
        if (cancelled) return;
        setHits(response.hits);
        setFacets(response.facets);
        setTotal(response.total);
        setTookMs(response.took_ms);
        setError(null);
      })
      .catch((caught: ApiError) => {
        if (cancelled) return;
        setError(caught.message);
        setHits([]);
        setFacets({});
        setTotal(0);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, filters, revision]);

  return (
    <div className="app">
      <header className="app__header">
        <div>
          <h1>Curaduría de terminología clínica</h1>
          <p className="muted">
            SQLite guarda la decisión editorial. Elasticsearch la hace encontrable.
          </p>
        </div>
        <StatusStrip refreshToken={revision} />
      </header>

      <div className="app__search">
        <SearchBar
          value={queryText}
          onChange={setQueryText}
          onPick={(conceptId) => setSelectedId(conceptId)}
        />
        <AnalyzerPeek text={queryText} />
      </div>

      {error && (
        <p className="error app__error" role="alert">
          {error}
        </p>
      )}

      <main className="app__body">
        <Facets facets={facets} filters={filters} onChange={setFilters} />

        <section className="app__results" aria-label="Resultados">
          <ResultList
            hits={hits}
            total={total}
            tookMs={tookMs}
            loading={loading}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </section>

        <ConceptPanel
          conceptId={selectedId}
          onSaved={() => {
            refresh();
          }}
        />
      </main>
    </div>
  );
}
