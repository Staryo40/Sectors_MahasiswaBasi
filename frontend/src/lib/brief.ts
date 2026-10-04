import type { Brief } from "../types/contracts";
import { words } from "./labels";

export function uniqueEvents(briefs: Brief[]): Brief["upcoming"] {
  const seen = new Set<string>();
  return briefs
    .flatMap((brief) => brief.upcoming)
    .filter((event) => {
      const key = [event.date, event.symbol, event.type].join("|");
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort(
      (a, b) =>
        a.date.localeCompare(b.date) || a.symbol.localeCompare(b.symbol),
    );
}

export function briefText(brief: Brief, horizon: "daily" | "weekly") {
  return [
    "Flow Radar · " + words(horizon) + " brief · " + brief.as_of,
    "",
    ...brief.items.map((item) => item.text_en),
    "",
    "Upcoming events",
    ...brief.upcoming.map(
      (event) => event.date + " · " + event.symbol + " · " + words(event.type),
    ),
    "",
    brief.disclaimer,
  ].join("\n");
}

export function downloadBrief(brief: Brief, horizon: "daily" | "weekly") {
  const url = URL.createObjectURL(
    new Blob([briefText(brief, horizon)], { type: "text/plain;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "flow-radar-" + horizon + "-" + brief.as_of + ".txt";
  document.body.append(link);
  link.click();
  link.remove();
  // Give the browser time to start consuming the download before revoking it.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
