type Numeric = number | null | undefined;
const compact = new Intl.NumberFormat("en", {
  notation: "compact",
  maximumFractionDigits: 1,
});
export const format = {
  number: (value: Numeric, decimals = 1) =>
    value == null
      ? "–"
      : value.toLocaleString("en", {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        }),
  integer: (value: Numeric) =>
    value == null ? "–" : Math.round(value).toLocaleString("en"),
  compact: (value: Numeric) => (value == null ? "–" : compact.format(value)),
  rupiah: (value: Numeric) =>
    value == null ? "–" : "Rp " + compact.format(value),
  percent: (value: Numeric, decimals = 1) =>
    value == null ? "–" : (value * 100).toFixed(decimals) + "%",
  signed: (value: Numeric, decimals = 1) =>
    value == null ? "–" : (value > 0 ? "+" : "") + value.toFixed(decimals),
  signedPercent: (value: Numeric, decimals = 2) =>
    value == null
      ? "–"
      : (value > 0 ? "+" : "") + (value * 100).toFixed(decimals) + "%",
  date: (value: string) =>
    new Date(value.slice(0, 10) + "T00:00:00Z").toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      timeZone: "UTC",
    }),
  raw: (value: Numeric, kind: string) => {
    if (value == null) return "–";
    if (kind === "pct") return format.percent(value);
    if (kind === "pct3") return format.percent(value, 3);
    if (kind === "pp") return format.signed(value * 100, 2) + " pp";
    if (kind === "x") return format.number(value, 2) + "×";
    return format.number(value, 3);
  },
};
