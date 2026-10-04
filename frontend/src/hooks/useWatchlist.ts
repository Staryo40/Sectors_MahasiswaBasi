import { useCallback, useEffect, useState } from "react";
import type { Source } from "../types/contracts";

export function useWatchlist(source: Source, availableSymbols: string[]) {
  const storageKey = "flowradar:watchlist:" + source;
  const [symbols, setSymbols] = useState<Set<string>>(() => {
    try {
      const stored: unknown = JSON.parse(
        localStorage.getItem(storageKey) || "[]",
      );
      return new Set(
        Array.isArray(stored)
          ? stored.filter(
              (symbol): symbol is string =>
                typeof symbol === "string" && availableSymbols.includes(symbol),
            )
          : [],
      );
    } catch {
      return new Set();
    }
  });
  const [storageNotice, setStorageNotice] = useState("");
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify([...symbols]));
    } catch {
      setStorageNotice(
        "Browser storage is unavailable. Your watchlist lasts for this session.",
      );
    }
  }, [symbols, storageKey]);
  const toggle = useCallback((symbol: string) => {
    setSymbols((current) => {
      const next = new Set(current);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  }, []);
  return { symbols, toggle, storageNotice };
}
