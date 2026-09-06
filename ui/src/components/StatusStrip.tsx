import { useCallback, useEffect, useState } from "react";

import { api } from "../api";
import type { Reconcile } from "../types";

interface Props {
  refreshToken: number;
}

/**
 * Surfaces the two-store problem in the interface itself.
 *
 * When the relational count and the indexed count disagree, a curator should
 * see it rather than discover it through a search that quietly misses rows.
 */
export function StatusStrip({ refreshToken }: Props) {
  const [state, setState] = useState<Reconcile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [working, setWorking] = useState(false);

  const load = useCallback(() => {
    api
      .reconcile()
      .then((result) => {
        setState(result);
        setError(null);
      })
      .catch(() => setError("API no disponible"));
  }, []);

  useEffect(load, [load, refreshToken]);

  async function repair() {
    setWorking(true);
    try {
      await api.reindex();
      load();
    } finally {
      setWorking(false);
    }
  }

  if (error) {
    return (
      <div className="strip strip--bad">
        <span>{error}</span>
        <span className="muted">Levantá uvicorn y Docker, después recargá.</span>
      </div>
    );
  }

  if (!state) return <div className="strip">Verificando estado...</div>;

  return (
    <div className={"strip" + (state.in_sync ? "" : " strip--bad")}>
      <span>
        <strong>{state.concepts_in_database}</strong> en base ·{" "}
        <strong>{state.documents_in_index}</strong> en índice
      </span>
      {state.in_sync ? (
        <span className="ok">Sincronizado</span>
      ) : (
        <>
          <span className="warn">
            Desincronizado ({state.pending_index} pendientes)
          </span>
          <button
            type="button"
            className="button button--small"
            onClick={repair}
            disabled={working}
          >
            {working ? "Reindexando..." : "Reparar"}
          </button>
        </>
      )}
    </div>
  );
}
