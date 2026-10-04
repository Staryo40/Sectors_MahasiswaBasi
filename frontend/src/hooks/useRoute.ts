import { useEffect, useState } from "react";
export function useRoute() {
  const [route, setRoute] = useState(
    () => location.hash.slice(1) || "overview",
  );
  useEffect(() => {
    const onHashChange = () => setRoute(location.hash.slice(1) || "overview");
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);
  const [view, encodedSymbol] = route.split("/");
  let symbol = "";
  try {
    symbol = decodeURIComponent(encodedSymbol || "").toUpperCase();
  } catch {
    /* A malformed hash shows the stock error state. */
  }
  return { view, symbol };
}
