import { useEffect, useState } from "react";

import { api, ApiError } from "../api";
import type { Concept, CurationStatus } from "../types";
import { CURATION_STATUSES, STATUS_LABELS } from "../types";

interface Props {
  conceptId: string | null;
  onSaved: () => void;
}

export function ConceptPanel({ conceptId, onSaved }: Props) {
  const [concept, setConcept] = useState<Concept | null>(null);
  const [status, setStatus] = useState<CurationStatus>("draft");
  const [note, setNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!conceptId) {
      setConcept(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSaved(false);
    api
      .getConcept(conceptId)
      .then((found) => {
        if (cancelled) return;
        setConcept(found);
        setStatus(found.curation_status);
        setNote(found.curation_note ?? "");
      })
      .catch((caught: ApiError) => {
        if (!cancelled) setError(caught.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [conceptId]);

  if (!conceptId) {
    return (
      <section className="panel panel--empty">
        <p className="muted">
          Elegí un concepto de la lista para revisarlo y cambiar su estado.
        </p>
      </section>
    );
  }

  if (loading) return <section className="panel"><p className="muted">Cargando...</p></section>;
  if (error) return <section className="panel"><p className="error">{error}</p></section>;
  if (!concept) return null;

  const dirty =
    status !== concept.curation_status || note !== (concept.curation_note ?? "");

  async function save() {
    if (!concept) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await api.updateConcept(concept.concept_id, {
        curation_status: status,
        curation_note: note.trim() === "" ? null : note,
      });
      setConcept(updated);
      setSaved(true);
      onSaved();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Error al guardar");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel" aria-label="Detalle del concepto">
      <header className="panel__head">
        <code className="panel__id">{concept.concept_id}</code>
        <h2>{concept.fsn}</h2>
        <div className="panel__meta">
          <span className="tag">{concept.semantic_tag}</span>
          <span className="tag tag--soft">{concept.module}</span>
          {!concept.active && <span className="chip chip--inactive">Inactivo</span>}
        </div>
      </header>

      <div className="panel__section">
        <h3>Descripciones</h3>
        <ul className="terms">
          {concept.descriptions.map((description) => (
            <li key={description.id} className="term">
              <span className="term__text">{description.term}</span>
              <span className="term__flags">
                <span className="tag tag--soft">{description.type}</span>
                {description.preferred && <span className="tag">preferido</span>}
                <span className="tag tag--soft">{description.language}</span>
              </span>
            </li>
          ))}
          {concept.descriptions.length === 0 && (
            <li className="muted">Sin descripciones cargadas.</li>
          )}
        </ul>
      </div>

      <div className="panel__section">
        <h3>Curaduría</h3>
        <label className="field">
          <span>Estado</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as CurationStatus);
              setSaved(false);
            }}
          >
            {CURATION_STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span>Nota</span>
          <textarea
            rows={3}
            value={note}
            placeholder="Motivo de la decisión, solapamientos, dudas..."
            onChange={(event) => {
              setNote(event.target.value);
              setSaved(false);
            }}
          />
        </label>

        <div className="panel__actions">
          <button
            type="button"
            className="button"
            disabled={!dirty || saving}
            onClick={save}
          >
            {saving ? "Guardando..." : "Guardar"}
          </button>
          {saved && !dirty && <span className="ok">Guardado y reindexado</span>}
        </div>
      </div>

      <footer className="panel__foot muted">
        <div>
          Índice:{" "}
          {concept.pending_index ? (
            <strong className="warn">pendiente</strong>
          ) : (
            <>sincronizado</>
          )}
        </div>
        <div>Actualizado: {new Date(concept.updated_at).toLocaleString("es-AR")}</div>
      </footer>
    </section>
  );
}
