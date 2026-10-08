import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { App } from "../App";
import { loadSnapshot } from "../lib/api";
import { briefText, uniqueEvents } from "../lib/brief";
import type { Brief, DailyEntry, Source, Stock } from "../types/contracts";

const repositoryRoot = resolve(import.meta.dirname, "../../..");
const requested = process.env.RADAR_TEST_SOURCE;
const sources: Source[] = requested
  ? [requested as Source]
  : ["fixtures", "out"];

function readOutput<T>(source: Source, file: string): T {
  return JSON.parse(
    readFileSync(
      resolve(
        repositoryRoot,
        source === "out" ? "data/out" : "fixtures/out",
        file,
      ),
      "utf8",
    ),
  ) as T;
}
function resourceFile(resource: string) {
  if (resource.startsWith("briefs/"))
    return "brief_" + resource.split("/")[1] + ".json";
  return resource + ".json";
}
async function openView(hash: string) {
  await act(async () => {
    location.hash = hash;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}
async function openWorkspace() {
  render(<App />);
  await screen.findByRole("heading", { name: /Follow the flow/ });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

for (const source of sources) {
  describe.skipIf(
    source === "out" &&
      !existsSync(resolve(repositoryRoot, "data/out/meta.json")),
  )("React dashboard: " + source, () => {
    const daily = readOutput<DailyEntry[]>(source, "daily.json");
    beforeEach(() => {
      localStorage.clear();
      history.replaceState(null, "", "/?src=" + source + "#overview");
      vi.stubGlobal(
        "fetch",
        vi.fn(async (input: string | URL | Request) => {
          const url = String(input);
          const match = url.match(
            /^\/api\/snapshots\/(out|fixtures|sample)\/(.+)$/,
          );
          if (!match)
            return new Response(JSON.stringify({ detail: "Unknown route" }), {
              status: 404,
            });
          try {
            return new Response(
              JSON.stringify(
                readOutput(
                  match[1] as Source,
                  resourceFile(decodeURIComponent(match[2])),
                ),
              ),
              { status: 200 },
            );
          } catch {
            return new Response(
              JSON.stringify({ detail: "Snapshot is not available." }),
              { status: 404 },
            );
          }
        }),
      );
    });

    it("renders computed overview metrics and clearly labels the source", async () => {
      await openWorkspace();
      expect(
        screen.getByText(
          source === "out" ? "EXPORTED MARKET DATA" : "ILLUSTRATIVE FIXTURES",
        ),
      ).toBeTruthy();
      expect(
        screen.getByRole("heading", { name: "Daily flow leaders" }),
      ).toBeTruthy();
      expect(
        screen.getByRole("heading", { name: "The investor shortlist" }),
      ).toBeTruthy();
      const breadth = screen.getByRole("img", { name: /Strong accumulation:/ });
      expect(breadth.getAttribute("aria-label")).toContain(
        "Accumulation: " +
          daily.filter((entry) => entry.label === "accumulation").length,
      );
    });

    it("filters rankings, resets empty results, and preserves score explanations", async () => {
      const user = userEvent.setup();
      await openWorkspace();
      await openView("daily");
      await screen.findByRole("heading", { name: "Where capital is moving." });
      await user.click(screen.getByRole("button", { name: "Accumulation" }));
      expect(document.querySelectorAll("article.row").length).toBe(
        daily.filter((entry) => entry.label.includes("accumulation")).length,
      );
      await user.type(
        screen.getByRole("searchbox", { name: "Search stocks" }),
        "no-such-stock",
      );
      expect(
        screen.getByRole("heading", { name: "No signals match just yet." }),
      ).toBeTruthy();
      await user.click(screen.getByRole("button", { name: "Reset filters" }));
      expect(document.querySelectorAll("article.row").length).toBe(
        daily.length,
      );
      expect(screen.getAllByText("Explain this score").length).toBe(
        daily.length,
      );
    });

    it("saves symbols across views and restores them after remount", async () => {
      const user = userEvent.setup();
      await openWorkspace();
      await openView("daily");
      await user.click(
        screen.getByRole("button", {
          name: "Save " + daily[0].symbol + " to watchlist",
        }),
      );
      expect(
        JSON.parse(
          localStorage.getItem("flowradar:watchlist:" + source) || "[]",
        ),
      ).toEqual([daily[0].symbol]);
      await openView("watchlist");
      expect(document.querySelectorAll("article.row").length).toBe(2);
      cleanup();
      render(<App />);
      await screen.findByRole("heading", {
        name: "Keep your signals in sight.",
      });
      expect(document.querySelectorAll("article.row").length).toBe(2);
      await user.click(
        screen.getAllByRole("button", {
          name: "Remove " + daily[0].symbol + " from watchlist",
        })[0],
      );
      expect(
        screen.getByRole("heading", { name: "Your watchlist starts here." }),
      ).toBeTruthy();
    });

    it("uses the stock search and supports keyboard shortcuts", async () => {
      const user = userEvent.setup();
      await openWorkspace();
      await user.keyboard("/");
      const input = screen.getByRole("combobox", {
        name: "Find a stock by symbol",
      });
      expect(document.activeElement).toBe(input);
      await user.type(input, daily[0].symbol.toLowerCase() + ".JK");
      await user.keyboard("{Enter}");
      await screen.findByRole("heading", {
        name: daily[0].symbol,
      });
      expect(location.hash).toBe("#stock/" + daily[0].symbol);
    });

    it("renders six stock charts, range controls, keyboard values and evidence", async () => {
      const user = userEvent.setup();
      await openWorkspace();
      await openView("stock/" + daily[0].symbol);
      await screen.findByRole("heading", {
        name: daily[0].symbol,
      });
      const charts = document.querySelectorAll(".chart svg");
      expect(charts.length).toBe(6);
      await user.click(screen.getByRole("button", { name: "20 sessions" }));
      expect(
        screen
          .getByRole("button", { name: "20 sessions" })
          .getAttribute("aria-pressed"),
      ).toBe("true");
      const stock = readOutput<Stock>(
        source,
        "stocks/" + daily[0].symbol + ".json",
      );
      const priceCard = screen
        .getByRole("heading", { name: "Price" })
        .closest("section")!;
      expect(priceCard.querySelectorAll("tbody tr").length).toBe(
        Math.min(20, stock.series.price.length),
      );
      const holderCard = screen
        .getByRole("heading", { name: "Ownership mix" })
        .closest("section")!;
      expect(holderCard.querySelectorAll("tbody tr").length).toBe(
        stock.series.holder_mix.length,
      );
      const foreignFlowCard = screen
        .getByRole("heading", { name: "Daily foreign flow" })
        .closest("section")!;
      for (const bar of foreignFlowCard.querySelectorAll(".chart-bar")) {
        const x = Number(bar.getAttribute("x"));
        const width = Number(bar.getAttribute("width"));
        expect(x).toBeGreaterThanOrEqual(66);
        expect(x + width).toBeLessThanOrEqual(622);
        expect(width).toBeLessThanOrEqual(36);
      }
      const priceChart = within(priceCard).getByRole("img", {
        name: "Price",
      });
      fireEvent.focus(priceChart);
      fireEvent.keyDown(priceChart, { key: "Home" });
      expect(within(priceCard).getByRole("status").textContent).toContain(
        "Close:",
      );
      await user.click(screen.getByRole("button", { name: "All" }));
      expect(priceCard.querySelectorAll("tbody tr").length).toBe(
        stock.series.price.length,
      );
      expect(
        screen.getByRole("heading", { name: "Net accumulators" }),
      ).toBeTruthy();
      expect(
        screen.getByRole("heading", { name: "Fundamentals & peer context" }),
      ).toBeTruthy();
    });

    it("deduplicates calendar events and downloads local daily and weekly briefs", async () => {
      const user = userEvent.setup();
      await openWorkspace();
      await openView("changes");
      const dailyBrief = readOutput<Brief>(source, "brief_daily.json");
      const weeklyBrief = readOutput<Brief>(source, "brief_weekly.json");
      const upcoming = uniqueEvents([dailyBrief, weeklyBrief]);
      expect(document.querySelectorAll("tbody tr").length).toBe(
        upcoming.length,
      );
      const create = vi.fn(() => "blob:local-brief");
      Object.defineProperty(URL, "createObjectURL", {
        value: create,
        configurable: true,
      });
      Object.defineProperty(URL, "revokeObjectURL", {
        value: vi.fn(),
        configurable: true,
      });
      const click = vi
        .spyOn(HTMLAnchorElement.prototype, "click")
        .mockImplementation(() => {});
      await user.click(screen.getByRole("button", { name: "Daily brief" }));
      await user.click(screen.getByRole("button", { name: "Weekly brief" }));
      expect(create).toHaveBeenCalledTimes(2);
      expect(click).toHaveBeenCalledTimes(2);
      expect(briefText(dailyBrief, "daily")).toContain(dailyBrief.disclaimer);
      for (const item of dailyBrief.items)
        expect(briefText(dailyBrief, "daily")).toContain(item.text_en);
    });

    it("shows a missing-stock state and a route back to rankings", async () => {
      await openWorkspace();
      await openView("stock/MISSING");
      await screen.findByRole("heading", {
        name: "MISSING research unavailable",
      });
      expect(
        screen
          .getByRole("link", { name: "Back to rankings" })
          .getAttribute("href"),
      ).toBe("#daily");
    });
  });
}

describe("data loading failures", () => {
  beforeEach(() => history.replaceState(null, "", "/?src=out#overview"));
  it("keeps a pinned source and provides an actionable retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: "Export local data first." }), {
            status: 404,
          }),
      ),
    );
    render(<App />);
    await screen.findByRole("heading", { name: "Snapshot unavailable" });
    expect(screen.getByText("Export local data first.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it("falls back only when an automatic source is missing", async () => {
    const fetcher = vi.fn(async (input: string) =>
      input.includes("/out/")
        ? new Response("{}", { status: 404 })
        : new Response(
            JSON.stringify(
              readOutput(
                "fixtures",
                resourceFile(input.split("/fixtures/")[1]),
              ),
            ),
          ),
    );
    vi.stubGlobal("fetch", fetcher);
    expect((await loadSnapshot(null)).source).toBe("fixtures");
    fetcher.mockImplementation(
      async () =>
        new Response(JSON.stringify({ detail: "Invalid snapshot" }), {
          status: 503,
        }),
    );
    await expect(loadSnapshot(null)).rejects.toThrow("Invalid snapshot");
  });
});
