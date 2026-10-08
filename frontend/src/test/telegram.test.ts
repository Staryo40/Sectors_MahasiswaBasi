import { afterEach, describe, expect, it, vi } from "vitest";
import { resolve } from "node:path";
import {
  answerTelegram,
  chunkTelegramText,
  type TelegramSnapshot,
} from "../../../lib/telegram";
import { GET, POST } from "../../../api/telegram";
import { snapshotRequestUrl } from "../lib/api";

const repositoryRoot = resolve(import.meta.dirname, "../../..");

afterEach(() => {
  delete process.env.RADAR_SNAPSHOT_DIR;
  delete process.env.TELEGRAM_BOT_TOKEN;
  delete process.env.TELEGRAM_WEBHOOK_SECRET;
  vi.unstubAllGlobals();
});

const snapshot: TelegramSnapshot = {
  meta: { as_of: "2026-10-07" },
  daily: [
    {
      symbol: "PGEO",
      name: "PT Pertamina Geothermal Energy Tbk",
      rank: 1,
      flow_score: 12.3,
      label: "strong_accumulation",
      reasons: [{ text_en: "Foreign buyers accumulated shares" }],
    },
  ],
  investor: [
    {
      symbol: "PGEO",
      name: "PT Pertamina Geothermal Energy Tbk",
      rank: 2,
      investor_score: 71.25,
      coverage: 0.8,
      reasons: [{ text_en: "Valuation is attractive versus peers" }],
    },
  ],
  dailyBrief: { as_of: "2026-10-07", items: [] },
  weeklyBrief: { as_of: "2026-10-07", items: [] },
};

describe("Vercel snapshot URLs", () => {
  it("maps API resources to the frozen static files", () => {
    expect(snapshotRequestUrl("out", "meta", "/snapshots")).toBe(
      "/snapshots/out/meta.json",
    );
    expect(snapshotRequestUrl("out", "briefs/daily", "/snapshots")).toBe(
      "/snapshots/out/brief_daily.json",
    );
    expect(snapshotRequestUrl("out", "stocks/PGEO", "/snapshots")).toBe(
      "/snapshots/out/stocks/PGEO.json",
    );
  });
});

describe("Telegram webhook replies", () => {
  it("answers rankings and stock lookups from the frozen snapshot", () => {
    expect(answerTelegram("/daily", snapshot)).toContain("1. PGEO +12.3");
    const reply = answerTelegram("pgeo.jk", snapshot);
    expect(reply).toContain("PGEO | PT Pertamina Geothermal Energy Tbk");
    expect(reply).toContain("Valuation is attractive versus peers");
    expect(reply).toContain("Bukan nasihat investasi");
  });

  it("validates commands and splits messages on UTF-16 boundaries", () => {
    expect(answerTelegram("/brief monthly", snapshot)).toBe(
      "Gunakan /brief daily atau /brief weekly.",
    );
    expect(chunkTelegramText("abc🙂def", 5)).toEqual(["abc🙂", "def"]);
  });
});

describe("Telegram Vercel function", () => {
  it("exposes health without revealing configuration", async () => {
    expect(await GET().json()).toEqual({
      status: "ok",
      service: "flow-radar-telegram-webhook",
    });
  });

  it("rejects forged requests and answers authenticated updates", async () => {
    process.env.RADAR_SNAPSHOT_DIR = resolve(repositoryRoot, "data/out");
    process.env.TELEGRAM_BOT_TOKEN = "test-token";
    process.env.TELEGRAM_WEBHOOK_SECRET = "test-secret";
    const send = vi.fn(
      async (_input: string | URL | Request, _init?: RequestInit) =>
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    vi.stubGlobal("fetch", send);

    const forged = await POST(
      new Request("https://example.test/api/telegram", {
        method: "POST",
        body: JSON.stringify({ message: { text: "/daily", chat: { id: 1 } } }),
      }),
    );
    expect(forged.status).toBe(401);
    expect(send).not.toHaveBeenCalled();

    const accepted = await POST(
      new Request("https://example.test/api/telegram", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-telegram-bot-api-secret-token": "test-secret",
        },
        body: JSON.stringify({ message: { text: "/daily", chat: { id: 1 } } }),
      }),
    );
    expect(accepted.status).toBe(200);
    expect(send).toHaveBeenCalledOnce();
    expect(send.mock.calls[0][0]).toBe(
      "https://api.telegram.org/bottest-token/sendMessage",
    );
    expect(JSON.parse(String(send.mock.calls[0][1]?.body)).text).toContain(
      "Daily Flow | 2026-10-07",
    );
  });
});
