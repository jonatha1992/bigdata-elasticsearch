import { useEffect, useState } from "react";

import { api } from "../api";
import { useDebounced } from "../useDebounced";
import type { AnalyzeToken } from "../types";

const ANALYZERS = ["clinical_text", "clinical_exact"] as const;

/**
 * Shows what each analyzer does to the current query.
 *
 * This is the "why did that not match" tool, put where a curator can actually
 * reach it instead of buried in a curl command.
 */
export function AnalyzerPeek({ text }: { text: string }) {
  const [tokens, setTokens] = useState<Record<string, AnalyzeToken[]>>({});
  const debounced = useDebounced(text, 300);

  useEffect(() => {
    const trimmed = debounced.trim();
    if (trimmed.length < 2) {
      setTokens({});
      return;
    }
    let cancelled = false;
    Promise.all(
      ANALYZERS.map((analyzer) =>
        api
          .analyze(trimmed, analyzer)
          .then((response) => [analyzer, response.tokens] as const)
          .catch(() => [analyzer, []] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setTokens(Object.fromEntries(entries));
    });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  if (Object.keys(tokens).length === 0) return null;

  return (
    <details className="peek">
      <summary>¿Cómo se analiza esta consulta?</summary>
      <div className="peek__body">
        {ANALYZERS.map((analyzer) => (
          <div key={analyzer} className="peek__row">
            <code className="peek__name">{analyzer}</code>
            <div className="peek__tokens">
              {(tokens[analyzer] ?? []).map((token, index) => (
                <span key={`${token.token}-${index}`} className="token">
                  {token.token}
                </span>
              ))}
              {(tokens[analyzer] ?? []).length === 0 && (
                <span className="muted">sin tokens (todo era stopword)</span>
              )}
            </div>
          </div>
        ))}
        <p className="peek__note muted">
          <code>clinical_text</code> aplica stemming: reduce plurales y variantes a
          una raíz común. <code>clinical_exact</code> no. Los dos sacan las tildes.
          Si tu consulta no matchea, mirá acá primero.
        </p>
      </div>
    </details>
  );
}
