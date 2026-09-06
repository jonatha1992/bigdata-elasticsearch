import { useEffect, useState } from "react";

/**
 * Delay a value until it stops changing for `delay` ms.
 *
 * Every keystroke would otherwise be one Elasticsearch query. Debouncing is the
 * difference between a search box and a load generator.
 */
export function useDebounced<T>(value: T, delay = 200): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
