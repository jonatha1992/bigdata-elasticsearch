import { useEffect, useRef, useState } from "react";

import { api } from "../api";
import { useDebounced } from "../useDebounced";
import type { SuggestItem } from "../types";

interface Props {
  value: string;
  onChange: (value: string) => void;
  onPick: (conceptId: string) => void;
}

export function SearchBar({ value, onChange, onPick }: Props) {
  const [items, setItems] = useState<SuggestItem[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const debounced = useDebounced(value, 150);
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounced.trim().length < 2) {
      setItems([]);
      return;
    }
    let cancelled = false;
    api
      .suggest(debounced.trim())
      .then((response) => {
        // A slow response for an old keystroke must never overwrite a newer one.
        if (!cancelled) {
          setItems(response.items);
          setActive(-1);
        }
      })
      .catch(() => {
        if (!cancelled) setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  useEffect(() => {
    function onClickOutside(event: MouseEvent) {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const visible = open && items.length > 0;

  function choose(index: number) {
    const item = items[index];
    if (!item) return;
    onPick(item.concept_id);
    setOpen(false);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!visible) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((current) => (current + 1) % items.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((current) => (current <= 0 ? items.length - 1 : current - 1));
    } else if (event.key === "Enter" && active >= 0) {
      event.preventDefault();
      choose(active);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  return (
    <div className="searchbar" ref={container}>
      <label className="searchbar__label" htmlFor="q">
        Buscar concepto
      </label>
      <input
        id="q"
        className="searchbar__input"
        type="search"
        autoComplete="off"
        placeholder="hipertension, DM2, dolor toracico..."
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={visible}
        aria-controls="suggest-list"
        aria-autocomplete="list"
      />
      {visible && (
        <ul className="suggest" id="suggest-list" role="listbox">
          {items.map((item, index) => (
            <li key={item.concept_id}>
              <button
                type="button"
                role="option"
                aria-selected={index === active}
                className={
                  "suggest__item" + (index === active ? " suggest__item--active" : "")
                }
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(index)}
              >
                <span className="suggest__label">{item.label}</span>
                <span className="tag">{item.semantic_tag}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="searchbar__hint">
        Sin tildes funciona igual. Los errores de tipeo también.
      </p>
    </div>
  );
}
