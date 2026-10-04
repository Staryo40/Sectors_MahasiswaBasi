"""Deterministic investor reasons, prioritised by score influence."""
from __future__ import annotations
from radar.signals import investor_config as cfg


def build(entry: dict, top: int = 3) -> list[dict]:
    """Reasons {code, params, text_en} for one investor.compute entry."""
    components = {c["key"]: c for c in entry.get("components", [])}
    counts = {p: sum(c.get("percentile") is not None for c in components.values() if c["pillar"] == p)
              for p in cfg.PILLAR_WEIGHTS}
    candidates = []
    def influence(key):
        c = components.get(key, {})
        percentile = c.get("percentile")
        if percentile is None:
            return 0.0
        pillar = c["pillar"]
        return cfg.PILLAR_WEIGHTS[pillar] * abs(percentile - 0.5) / max(counts[pillar], 1)
    def add(code, params, text, priority):
        candidates.append((priority, {"code": code, "params": params, "text_en": text}))

    quality = entry.get("pillars", {}).get("quality")
    if quality is not None and quality >= cfg.QUALITY_HIGH_THRESHOLD:
        add("QUALITY_HIGH", {"score": quality}, f"Quality pillar is {quality:.1f}/100 within the universe.",
            cfg.PILLAR_WEIGHTS["quality"] * (quality / 100 - 0.5))
    ratios = {key: c["raw"] for key in ("pe_relative", "pb_relative")
              if (c := components.get(key)) and c.get("raw") is not None and 0 <= c["raw"] < 1}
    if ratios:
        add("VALUATION_BELOW_PEERS", ratios, "Valuation multiples are below their peer averages (" +
            ", ".join(f"{key.split('_')[0].upper()} {value:.2f}×" for key, value in ratios.items()) + ").",
            sum(influence(key) for key in ratios))
    dividend = components.get("yield_ttm", {}).get("raw")
    if dividend is not None and dividend > 0:
        add("DIVIDEND_YIELD", {"yield": dividend}, f"Trailing dividend yield is {dividend * 100:.2f}%.", influence("yield_ttm"))
    long = [(key, components[key]) for key in ("foreign_90d", "foreign_20d")
            if key in components and components[key].get("raw") is not None and components[key]["raw"] > 0]
    if long:
        key, component = max(long, key=lambda pair: (influence(pair[0]), pair[0] == "foreign_90d"))
        days = int(key.removeprefix("foreign_").removesuffix("d"))
        value = component["raw"]
        add("FOREIGN_INFLOW_LONG", {"days": days, "net_to_market_cap": value},
            f"Net foreign accumulation equals {value * 100:.3f}% of market cap over available history in the {days}-trading-day window.", influence(key))
    shift = components.get("holder_shift", {}).get("raw")
    if shift is not None and shift != 0:
        code = "HOLDER_SHIFT_INSTITUTIONAL" if shift > 0 else "HOLDER_SHIFT_RETAIL"
        direction = "rose" if shift > 0 else "fell"
        add(code, {"pp": shift * 100, "months": cfg.HOLDER_SHIFT_SNAPSHOTS},
            f"Institutional share {direction} by {abs(shift) * 100:.2f} percentage points across the last {cfg.HOLDER_SHIFT_SNAPSHOTS} monthly snapshots.", influence("holder_shift"))
    insider = components.get("insider", {}).get("raw")
    if insider is not None and insider != 0:
        direction = "accumulation" if insider > 0 else "distribution"
        add("INSIDER_ACTIVITY", {"ratio": insider, "days": cfg.INSIDER_DAYS, "direction": direction},
            f"Insider filings show net {direction} over {cfg.INSIDER_DAYS} calendar days (ratio {insider:.2f}).", influence("insider"))
    candidates.sort(key=lambda item: (-item[0], item[1]["code"]))
    return [reason for _, reason in candidates[:max(top, 0)]]
