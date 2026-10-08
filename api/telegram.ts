import { timingSafeEqual } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import {
  answerTelegram,
  chunkTelegramText,
  type TelegramSnapshot,
} from "../lib/telegram";

interface TelegramUpdate {
  message?: {
    text?: unknown;
    chat?: { id?: unknown };
  };
}

let cachedSnapshot: Promise<TelegramSnapshot> | undefined;

async function readJson(file: string): Promise<unknown> {
  const root = process.env.RADAR_SNAPSHOT_DIR
    ? resolve(process.env.RADAR_SNAPSHOT_DIR)
    : join(process.cwd(), "data", "out");
  return JSON.parse(await readFile(join(root, file), "utf8"));
}

async function loadSnapshot() {
  cachedSnapshot ??= Promise.all([
    readJson("meta.json"),
    readJson("daily.json"),
    readJson("investor.json"),
    readJson("brief_daily.json"),
    readJson("brief_weekly.json"),
  ]).then(([meta, daily, investor, dailyBrief, weeklyBrief]) => {
    if (
      !meta ||
      typeof meta !== "object" ||
      !("as_of" in meta) ||
      typeof meta.as_of !== "string" ||
      !Array.isArray(daily) ||
      !Array.isArray(investor)
    )
      throw new Error("Frozen snapshot has an invalid shape.");
    return { meta, daily, investor, dailyBrief, weeklyBrief } as TelegramSnapshot;
  });
  return cachedSnapshot;
}

function matchesSecret(received: string | null, expected: string) {
  if (!received) return false;
  const left = Buffer.from(received);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

async function sendMessage(token: string, chatId: string | number, text: string) {
  for (const chunk of chunkTelegramText(text)) {
    const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: chunk }),
    });
    const result = (await response.json().catch(() => null)) as
      | { ok?: boolean; description?: string }
      | null;
    if (!response.ok || result?.ok !== true)
      throw new Error(result?.description || `Telegram returned HTTP ${response.status}.`);
  }
}

export function GET() {
  return Response.json({ status: "ok", service: "flow-radar-telegram-webhook" });
}

export async function POST(request: Request) {
  const token = process.env.TELEGRAM_BOT_TOKEN?.trim();
  const secret = process.env.TELEGRAM_WEBHOOK_SECRET?.trim();
  if (!token || !secret)
    return Response.json({ detail: "Telegram webhook is not configured." }, { status: 503 });

  if (!matchesSecret(request.headers.get("x-telegram-bot-api-secret-token"), secret))
    return Response.json({ detail: "Unauthorized webhook request." }, { status: 401 });

  let update: TelegramUpdate;
  try {
    update = (await request.json()) as TelegramUpdate;
  } catch {
    return Response.json({ detail: "Invalid JSON body." }, { status: 400 });
  }

  const message = update.message;
  if (
    !message ||
    typeof message.text !== "string" ||
    (typeof message.chat?.id !== "string" && typeof message.chat?.id !== "number")
  )
    return Response.json({ ok: true, ignored: true });

  try {
    const snapshot = await loadSnapshot();
    await sendMessage(token, message.chat.id, answerTelegram(message.text, snapshot));
    return Response.json({ ok: true });
  } catch (error) {
    console.error("Telegram webhook failed:", error instanceof Error ? error.message : error);
    return Response.json({ detail: "Telegram reply failed." }, { status: 502 });
  }
}
