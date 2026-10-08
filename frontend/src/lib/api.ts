import type {
  Brief,
  DailyEntry,
  InvestorEntry,
  Meta,
  Snapshot,
  Source,
  Stock,
} from "../types/contracts";

const sourceNames: Source[] = ["out", "fixtures", "sample"];
const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || "")
  .trim()
  .replace(/\/+$/, "");
const staticSnapshotBaseUrl = (
  import.meta.env.VITE_SNAPSHOT_BASE_URL || (import.meta.env.PROD ? "/snapshots" : "")
)
  .trim()
  .replace(/\/+$/, "");

export const productionSnapshotSource = import.meta.env.PROD
  ? import.meta.env.VITE_SNAPSHOT_SOURCE || "out"
  : null;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function snapshotFile(resource: string) {
  if (resource.startsWith("briefs/"))
    return "brief_" + resource.slice("briefs/".length) + ".json";
  return resource + ".json";
}

export function snapshotRequestUrl(
  source: Source,
  resource: string,
  staticBase = staticSnapshotBaseUrl,
  apiBase = apiBaseUrl,
) {
  return staticBase
    ? staticBase + "/" + source + "/" + snapshotFile(resource)
    : apiBase + "/api/snapshots/" + source + "/" + resource;
}

export async function readSnapshot<T>(
  source: Source,
  resource: string,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(snapshotRequestUrl(source, resource), {
    signal,
    cache: "no-store",
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({}))) as {
      detail?: unknown;
    };
    throw new ApiError(
      response.status,
      typeof error.detail === "string"
        ? error.detail
        : "Snapshot request failed.",
    );
  }
  return response.json() as Promise<T>;
}

export async function loadSnapshot(
  requested: string | null,
  signal?: AbortSignal,
): Promise<Snapshot> {
  if (requested && !sourceNames.includes(requested as Source))
    throw new Error("Unknown source. Use out, fixtures, or sample.");
  const sources = requested ? [requested as Source] : sourceNames;
  for (const source of sources) {
    let meta: Meta;
    try {
      meta = await readSnapshot<Meta>(source, "meta", signal);
    } catch (error) {
      if (
        signal?.aborted ||
        requested ||
        !(error instanceof ApiError) ||
        error.status !== 404
      )
        throw error;
      continue;
    }
    const [daily, investor, dailyBrief, weeklyBrief] = await Promise.all([
      readSnapshot<DailyEntry[]>(source, "daily", signal),
      readSnapshot<InvestorEntry[]>(source, "investor", signal),
      readSnapshot<Brief>(source, "briefs/daily", signal),
      readSnapshot<Brief>(source, "briefs/weekly", signal),
    ]);
    return { source, meta, daily, investor, dailyBrief, weeklyBrief };
  }
  throw new Error("No snapshot found. Export local data or select fixtures.");
}

export function loadStock(
  source: Source,
  symbol: string,
  signal?: AbortSignal,
) {
  return readSnapshot<Stock>(
    source,
    "stocks/" + encodeURIComponent(symbol),
    signal,
  );
}
