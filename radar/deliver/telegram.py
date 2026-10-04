"""Deterministic brief formatting and opt-in Telegram delivery."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from radar import config
from radar.deliver.settings import settings


def format_brief(brief: dict) -> str:
    """Minimal default text drawn solely from computed brief fields."""
    lines = [f"Sectors Radar — {brief['as_of']}"]
    if brief.get("items"):
        lines.extend(f"• {item['text_en']}" for item in brief["items"])
    else:
        lines.append("No material changes in this brief.")
    if brief.get("upcoming"):
        lines.append("Upcoming events:")
        lines.extend(f"• {event['date']} — {event['symbol']}: {event['type'].replace('_', ' ')}" for event in brief["upcoming"])
    lines.extend(("", brief.get("disclaimer") or config.DISCLAIMER))
    return "\n".join(lines)


def _chunks(text, limit=4000):
    # Telegram's cap counts UTF-16 units; avoid splitting non-BMP characters.
    chunk, units = [], 0
    for char in text:
        size = len(char.encode("utf-16-le")) // 2
        if units + size > limit:
            yield "".join(chunk)
            chunk, units = [], 0
        chunk.append(char)
        units += size
    if chunk:
        yield "".join(chunk)


def send(text: str, dry_run: bool = True) -> None:
    if dry_run:
        print(f"[Telegram dry-run]\n{text}")
        return
    values = settings(("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))
    token, chat_id = values["TELEGRAM_BOT_TOKEN"], values["TELEGRAM_CHAT_ID"]
    if not token or not chat_id:
        print("Telegram skipped: channel settings are empty.")
        return
    for chunk in _chunks(text):
        request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                         data=json.dumps({"chat_id": chat_id, "text": chunk}).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            if not result.get("ok"):
                raise RuntimeError("Telegram delivery was not accepted.")
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Telegram delivery failed (HTTP {error.code}).") from None
        except (urllib.error.URLError, OSError, ValueError):
            raise RuntimeError("Telegram delivery failed; check connection and channel settings.") from None
    print("Telegram brief delivered.")
