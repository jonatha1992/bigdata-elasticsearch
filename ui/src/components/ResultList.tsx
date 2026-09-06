import type { SearchHit } from "../types";
import { STATUS_LABELS } from "../types";

interface Props {
  hits: SearchHit[];
  total: number;
  tookMs: number;
  loading: boolean;
  selectedId: string | null;
  onSelect: (conceptId: string) => void;
}

/**
 * Render the server's highlight fragments.
 *
 * Elasticsearch returns them with <mark> already inserted. We split on that tag
 * and rebuild real elements instead of using dangerouslySetInnerHTML: the
 * fragment contains curator-supplied text, and injecting it as raw HTML would be
 * an XSS hole for the sake of one bold word.
 */
function Highlighted({ fragment }: { fragment: string }) {
  const parts = fragment.split(/(<mark>.*?<\/mark>)/g);
  return (
    <>
      {parts.map((part, index) =>
        part.startsWith("<mark>") ? (
          <mark key={index}>{part.slice(6, -7)}</mark>
        ) : (
          <span key={index}>{part}</span>
        ),
      )}
    </>
  );
}

export function ResultList({
  hits,
  total,
  tookMs,
  loading,
  selectedId,
  onSelect,
}: Props) {
  if (loading) {
    return <p className="muted results__status">Buscando...</p>;
  }

  if (hits.length === 0) {
    return (
      <div className="results__empty">
        <p>Ningún concepto coincide.</p>
        <p className="muted">
          Probá con menos filtros, o con un sinónimo. La búsqueda tolera tildes
          faltantes y errores de tipeo, pero no adivina.
        </p>
      </div>
    );
  }

  return (
    <div className="results">
      <p className="results__status muted">
        {total} {total === 1 ? "concepto" : "conceptos"} · {tookMs} ms
      </p>
      <ul className="results__list">
        {hits.map((hit) => {
          const fragments = Object.values(hit.highlight).flat();
          const selected = hit.concept_id === selectedId;
          return (
            <li key={hit.concept_id}>
              <button
                type="button"
                aria-current={selected}
                className={"result" + (selected ? " result--on" : "")}
                onClick={() => onSelect(hit.concept_id)}
              >
                <div className="result__head">
                  <span className="result__term">{hit.preferred_term}</span>
                  <span className="result__score" title="Puntaje de relevancia">
                    {hit.score.toFixed(2)}
                  </span>
                </div>
                <div className="result__meta">
                  <span className="tag">{hit.semantic_tag}</span>
                  <span className={`chip chip--${hit.curation_status}`}>
                    {STATUS_LABELS[hit.curation_status]}
                  </span>
                  {!hit.active && <span className="chip chip--inactive">Inactivo</span>}
                  <code className="result__id">{hit.concept_id}</code>
                </div>
                {fragments[0] && (
                  <p className="result__highlight">
                    <Highlighted fragment={fragments[0]} />
                  </p>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
