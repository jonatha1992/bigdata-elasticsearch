import type { CurationStatus, Facet, Filters } from "../types";
import { STATUS_LABELS } from "../types";

interface Props {
  facets: Record<string, Facet[]>;
  filters: Filters;
  onChange: (filters: Filters) => void;
}

export function Facets({ facets, filters, onChange }: Props) {
  const tags = facets["semantic_tag"] ?? [];
  const statuses = facets["curation_status"] ?? [];
  const hasFilters = filters.semantic_tag !== null || filters.curation_status !== null;

  return (
    <aside className="facets" aria-label="Filtros">
      <div className="facets__header">
        <h2>Filtros</h2>
        {hasFilters && (
          <button
            type="button"
            className="link"
            onClick={() => onChange({ semantic_tag: null, curation_status: null })}
          >
            Limpiar
          </button>
        )}
      </div>

      <section className="facets__group">
        <h3>Tipo semántico</h3>
        {tags.length === 0 && <p className="muted">Sin resultados</p>}
        <ul>
          {tags.map((facet) => {
            const selected = filters.semantic_tag === facet.value;
            return (
              <li key={facet.value}>
                <button
                  type="button"
                  aria-pressed={selected}
                  className={"facet" + (selected ? " facet--on" : "")}
                  onClick={() =>
                    onChange({
                      ...filters,
                      semantic_tag: selected ? null : facet.value,
                    })
                  }
                >
                  <span>{facet.value}</span>
                  <span className="facet__count">{facet.count}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="facets__group">
        <h3>Estado de curaduría</h3>
        {statuses.length === 0 && <p className="muted">Sin resultados</p>}
        <ul>
          {statuses.map((facet) => {
            const status = facet.value as CurationStatus;
            const selected = filters.curation_status === status;
            return (
              <li key={facet.value}>
                <button
                  type="button"
                  aria-pressed={selected}
                  className={"facet" + (selected ? " facet--on" : "")}
                  onClick={() =>
                    onChange({
                      ...filters,
                      curation_status: selected ? null : status,
                    })
                  }
                >
                  <span>{STATUS_LABELS[status] ?? facet.value}</span>
                  <span className="facet__count">{facet.count}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <p className="facets__note">
        Los conteos vienen de agregaciones de Elasticsearch sobre el resultado
        completo, no sobre la página visible.
      </p>
    </aside>
  );
}
