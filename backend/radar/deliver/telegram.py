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


def _api(token: str, method: str, payload: dict, timeout: int = 30):
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
        if not result.get("ok"):
            raise RuntimeError("Telegram API did not accept the request.")
        return result.get("result")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Telegram API request failed (HTTP {error.code}).") from None
    except (urllib.error.URLError, OSError, ValueError):
        raise RuntimeError("Telegram API request failed; check connection and bot settings.") from None


def send_to_chat(text: str, chat_id: int | str, token: str) -> None:
    """Send text to a chat selected by an incoming update."""
    for chunk in _chunks(text):
        _api(token, "sendMessage", {"chat_id": chat_id, "text": chunk})


def get_updates(token: str, offset: int | None = None, timeout: int = 25) -> list[dict]:
    """Long-poll text messages without configuring a public webhook."""
    payload: dict = {"timeout": timeout, "allowed_updates": ["message"]}
    if offset is not None:
        payload["offset"] = offset
    result = _api(token, "getUpdates", payload, timeout=timeout + 5)
    return result if isinstance(result, list) else []


def send(text: str, dry_run: bool = True) -> None:
    if dry_run:
        print(f"[Telegram dry-run]\n{text}")
        return
    values = settings(("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))
    token, chat_id = values["TELEGRAM_BOT_TOKEN"], values["TELEGRAM_CHAT_ID"]
    if not token or not chat_id:
        print("Telegram skipped: channel settings are empty.")
        return
    send_to_chat(text, chat_id, token)
    print("Telegram brief delivered.")
