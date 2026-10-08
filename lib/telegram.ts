export const DISCLAIMER = "Informasi dan analisis saja. Bukan nasihat investasi.";

export const HELP = `Flow Radar bot

Perintah:
/daily - lima sinyal Daily Flow teratas
/weekly - lima sinyal Investor Lens teratas
/brief [daily|weekly] - perubahan pasar terbaru
/stock PGEO - skor dan alasan untuk satu emiten
/top daily - alias /daily
/top investor - alias /weekly
/help - tampilkan bantuan

Kamu juga dapat mengirim ticker langsung, misalnya: PGEO

Jawaban memakai snapshot pasar yang sama dengan dashboard dan tidak melakukan transaksi.`;

interface Reason {
  text_en?: string;
}

interface DailyRow {
  symbol: string;
  name: string;
  rank: number;
  flow_score: number;
  label: string;
  reasons?: Reason[];
}

interface InvestorRow {
  symbol: string;
  name: string;
  rank: number;
  investor_score: number;
  coverage: number;
  reasons?: Reason[];
}

interface BriefItem {
  text_en?: string;
}

interface UpcomingItem {
  date: string;
  symbol: string;
  type: string;
}

interface Brief {
  as_of: string;
  items?: BriefItem[];
  upcoming?: UpcomingItem[];
}

export interface TelegramSnapshot {
  meta: { as_of: string };
  daily: DailyRow[];
  investor: InvestorRow[];
  dailyBrief: Brief;
  weeklyBrief: Brief;
}

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

function number(value: number) {
  return value.toFixed(1);
}

function label(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function top(snapshot: TelegramSnapshot, horizon: "daily" | "investor") {
  const lines: string[] = [];
  if (horizon === "daily") {
    lines.push(`Daily Flow | ${snapshot.meta.as_of}`);
    lines.push(
      ...snapshot.daily
        .slice(0, 5)
        .map(
          (row) =>
            `${row.rank}. ${row.symbol} ${signed(row.flow_score)} | ${label(row.label)}`,
        ),
    );
  } else {
    lines.push(`Investor Lens | ${snapshot.meta.as_of}`);
    lines.push(
      ...snapshot.investor
        .slice(0, 5)
        .map(
          (row) =>
            `${row.rank}. ${row.symbol} ${number(row.investor_score)}/100 | coverage ${(row.coverage * 100).toFixed(0)}%`,
        ),
    );
  }
  lines.push("", "Gunakan /stock TICKER untuk melihat alasannya.", DISCLAIMER);
  return lines.join("\n");
}

function brief(snapshot: TelegramSnapshot, horizon: "daily" | "weekly") {
  const data = horizon === "daily" ? snapshot.dailyBrief : snapshot.weeklyBrief;
  const lines = [
    `${horizon === "daily" ? "Daily Brief" : "Weekly Brief"} | ${data.as_of}`,
  ];
  const items = data.items ?? [];
  if (items.length) {
    lines.push(...items.slice(0, 10).map((item) => `- ${item.text_en ?? "Update pasar"}`));
    if (items.length > 10) lines.push(`...dan ${items.length - 10} perubahan lainnya.`);
  } else {
    lines.push("Tidak ada perubahan material pada snapshot ini.");
  }
  const upcoming = data.upcoming ?? [];
  if (upcoming.length) {
    lines.push("Upcoming:");
    lines.push(
      ...upcoming
        .slice(0, 5)
        .map((item) => `- ${item.date} ${item.symbol}: ${item.type.replaceAll("_", " ")}`),
    );
  }
  lines.push("", DISCLAIMER);
  return lines.join("\n");
}

function stock(snapshot: TelegramSnapshot, rawSymbol: string) {
  const symbol = rawSymbol.trim().toUpperCase().replace(/\.JK$/, "");
  if (!/^[A-Z0-9]{1,12}$/.test(symbol))
    return "Format ticker tidak valid. Contoh: /stock PGEO";

  const daily = snapshot.daily.find((row) => row.symbol === symbol);
  const investor = snapshot.investor.find((row) => row.symbol === symbol);
  if (!daily || !investor)
    return `Ticker ${symbol} tidak ditemukan pada snapshot saat ini.`;

  const reasons = [...(daily.reasons ?? []).slice(0, 2), ...(investor.reasons ?? []).slice(0, 2)];
  const lines = [
    `${symbol} | ${daily.name} | ${snapshot.meta.as_of}`,
    `Daily #${daily.rank}: ${signed(daily.flow_score)} | ${label(daily.label)}`,
    `Investor #${investor.rank}: ${number(investor.investor_score)}/100 | coverage ${(investor.coverage * 100).toFixed(0)}%`,
    "",
    "Alasan utama:",
  ];
  if (reasons.length)
    lines.push(...reasons.map((reason) => `- ${reason.text_en ?? "Alasan belum tersedia"}`));
  else lines.push("- Belum ada alasan yang tersedia pada snapshot ini.");
  lines.push("", DISCLAIMER);
  return lines.join("\n");
}

export function answerTelegram(text: string, snapshot: TelegramSnapshot) {
  const entered = text.trim();
  if (!entered) return HELP;

  const parts = entered.split(/\s+/);
  const command = parts[0].toLowerCase().split("@", 1)[0];
  const args = parts.slice(1);

  if (["/start", "/help", "help"].includes(command)) return HELP;
  if (["/daily", "daily"].includes(command)) return top(snapshot, "daily");
  if (["/weekly", "/investor", "weekly", "investor"].includes(command))
    return top(snapshot, "investor");
  if (["/brief", "brief"].includes(command)) {
    const horizon = (args[0] ?? "daily").toLowerCase();
    if (horizon !== "daily" && horizon !== "weekly")
      return "Gunakan /brief daily atau /brief weekly.";
    return brief(snapshot, horizon);
  }
  if (["/top", "top"].includes(command)) {
    const horizon = (args[0] ?? "daily").toLowerCase();
    if (horizon === "daily") return top(snapshot, "daily");
    if (["weekly", "investor"].includes(horizon)) return top(snapshot, "investor");
    return "Gunakan /top daily atau /top investor.";
  }
  if (["/stock", "stock"].includes(command)) return stock(snapshot, args[0] ?? "");
  if (parts.length === 1 && /^[A-Z0-9]{1,12}(?:\.JK)?$/i.test(entered))
    return stock(snapshot, entered);
  return `Perintah belum dikenali.\n\n${HELP}`;
}

export function chunkTelegramText(text: string, limit = 4000) {
  if (!Number.isInteger(limit) || limit < 1)
    throw new Error("Telegram chunk limit must be a positive integer.");
  const chunks: string[] = [];
  let current = "";
  for (const character of text) {
    if (current.length + character.length > limit) {
      chunks.push(current);
      current = "";
    }
    current += character;
  }
  if (current) chunks.push(current);
  return chunks;
}
