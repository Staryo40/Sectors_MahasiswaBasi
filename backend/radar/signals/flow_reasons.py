"""Rule-based reasons for the flow score. Owned by agent B (task B4).

No LLM: every reason is a fixed template filled from computed numbers. The
wording uses inflow/outflow and accumulation/distribution, never buy/sell.
"""

from __future__ import annotations

from radar.signals import flow_config as cfg

# A component must move the score by at least this many points to be a reason.
# 2.0 keeps a 1-day foreign streak (1.5 points) out of the reasons; tuned on real data (B6).
MIN_CONTRIBUTION = 2.0

_CODES = {
    "foreign_5d": "FOREIGN_INFLOW_5D",
    "foreign_streak": "FOREIGN_STREAK",
    "broker_concentration": "BROKER_CONCENTRATION",
    "institutional_net": "INSTITUTIONAL_NET",
    "divergence": "DIVERGENCE",
    "insider": "INSIDER_ACTIVITY",
}


def _side(value: float) -> str:
    return "accumulation" if value > 0 else "distribution"


def _reason(key: str, value: float, entry: dict) -> dict:
    code = _CODES[key]
    if key == "foreign_5d":
        sigma = round(abs(value) * 3, 1)
        direction = "in" if value > 0 else "out"
        word = "inflow" if value > 0 else "outflow"
        text = f"5-day net foreign {word} is {sigma:g} standard deviations from this stock's norm"
        return {"code": code, "params": {"direction": direction, "sigma": sigma}, "text_en": text}

    if key == "foreign_streak":
        days = round(abs(value) * cfg.STREAK_CAP_DAYS)
        direction = "in" if value > 0 else "out"
        word = "inflow" if value > 0 else "outflow"
        count = f"at least {days}" if days >= cfg.STREAK_CAP_DAYS else str(days)
        unit = "trading day" if days == 1 else "trading days"
        text = f"Net foreign {word} for {count} {unit} in a row"
        return {"code": code, "params": {"days": days, "direction": direction}, "text_en": text}

    if key == "broker_concentration":
        side = _side(value)
        other = "distribution" if side == "accumulation" else "accumulation"
        text = (f"The top {cfg.TOP_BROKERS} brokers on the {side} side outweigh the top "
                f"{cfg.TOP_BROKERS} on the {other} side over the last 2 weeks")
        return {"code": code, "params": {"direction": side, "value": round(value, 2)}, "text_en": text}

    if key == "institutional_net":
        side = _side(value)
        pct = round(abs(value) * 100)
        text = f"Institutional brokers show net {side}, {pct}% of net traded value over the last 2 weeks"
        return {"code": code, "params": {"direction": side, "share_pct": pct}, "text_en": text}

    if key == "divergence":
        side = _side(value)
        ret = entry.get("return_10d")
        pct = round(abs(ret) * 100, 1) if ret is not None else 0.0
        if side == "accumulation":
            move = f"fell {pct:g}%" if ret and ret < 0 else "was flat"
        else:
            move = f"rose {pct:g}%" if ret and ret > 0 else "was flat"
        text = f"Smart-money {side} while the price {move} over {cfg.RETURN_DAYS} trading days"
        return {"code": code,
                "params": {"direction": side, "return_10d_pct": round(ret * 100, 1) if ret is not None else 0.0},
                "text_en": text}

    # insider
    side = "acquisitions" if value > 0 else "disposals"
    text = f"Insider filings in the last {cfg.INSIDER_DAYS} days lean toward {side}"
    return {"code": code, "params": {"direction": _side(value), "ratio": round(value, 2)}, "text_en": text}


def build(entry: dict, top: int = 3) -> list[dict]:
    """Reasons ``{code, params, text_en}`` for one ``flow.compute`` entry."""
    comps = [c for c in entry.get("components", []) if abs(c.get("contribution", 0.0)) >= MIN_CONTRIBUTION]
    comps.sort(key=lambda c: (-abs(c["contribution"]), c["key"]))
    reasons = [_reason(c["key"], c["value"], entry) for c in comps[:top]]

    ratio = entry.get("volume_ratio")
    if "unusual_volume" in entry.get("flags", []) and ratio is not None and len(reasons) < top:
        reasons.append({
            "code": "UNUSUAL_VOLUME",
            "params": {"ratio": round(ratio, 1)},
            "text_en": f"Volume was {round(ratio, 1):g}x its {cfg.VOLUME_MEDIAN_DAYS}-day median",
        })
    return reasons
