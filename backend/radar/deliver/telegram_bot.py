"""Public, read-only Telegram command bot backed by exported snapshots."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from jsonschema.exceptions import ValidationError

from radar import config
from radar.deliver import telegram
from radar.deliver.settings import settings
from radar.export.validation import validate

DISCLAIMER = "Informasi dan analisis saja. Bukan nasihat investasi."
HELP = """Flow Radar bot

Perintah:
/daily - lima sinyal Daily Flow teratas
/weekly - lima sinyal Investor Lens teratas
/brief [daily|weekly] - perubahan pasar terbaru
/stock PGEO - skor dan alasan untuk satu emiten
/top daily - alias /daily
/top investor - alias /weekly
/help - tampilkan bantuan

Kamu juga dapat mengirim ticker langsung, misalnya: PGEO

Jawaban memakai snapshot lokal terbaru dan tidak melakukan transaksi."""


def _read(directory: Path, relative: str, schema: str):
    root = directory.resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Snapshot path is invalid.")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        validate(schema, data)
        return data
    except FileNotFoundError:
        raise ValueError("Snapshot belum tersedia. Jalankan export terlebih dahulu.") from None
    except (OSError, json.JSONDecodeError, ValidationError):
        raise ValueError("Snapshot tidak dapat dibaca atau gagal validasi.") from None


def _signed(value) -> str:
    return f"{float(value):+.1f}"


def _number(value) -> str:
    return f"{float(value):.1f}"


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def _top(directory: Path, horizon: str) -> str:
    meta = _read(directory, "meta.json", "meta")
    if horizon == "daily":
        rows = _read(directory, "daily.json", "daily")[:5]
        lines = [f"Daily Flow | {meta['as_of']}"]
        lines.extend(
            f"{row['rank']}. {row['symbol']} {_signed(row['flow_score'])} | {_label(row['label'])}"
            for row in rows
        )
    else:
        rows = _read(directory, "investor.json", "investor")[:5]
        lines = [f"Investor Lens | {meta['as_of']}"]
        lines.extend(
            f"{row['rank']}. {row['symbol']} {_number(row['investor_score'])}/100 | coverage {row['coverage']:.0%}"
            for row in rows
        )
    lines.extend(("", "Gunakan /stock TICKER untuk melihat alasannya.", DISCLAIMER))
    return "\n".join(lines)


def _brief(directory: Path, horizon: str) -> str:
    brief = _read(directory, f"brief_{horizon}.json", f"brief_{horizon}")
    title = "Daily Brief" if horizon == "daily" else "Weekly Brief"
    lines = [f"{title} | {brief['as_of']}"]
    items = brief.get("items", [])
    if items:
        lines.extend(f"- {item['text_en']}" for item in items[:10])
        if len(items) > 10:
            lines.append(f"...dan {len(items) - 10} perubahan lainnya.")
    else:
        lines.append("Tidak ada perubahan material pada snapshot ini.")
    upcoming = brief.get("upcoming", [])
    if upcoming:
        lines.append("Upcoming:")
        lines.extend(
            f"- {item['date']} {item['symbol']}: {item['type'].replace('_', ' ')}"
            for item in upcoming[:5]
        )
    lines.extend(("", DISCLAIMER))
    return "\n".join(lines)


def _stock(directory: Path, raw_symbol: str) -> str:
    symbol = raw_symbol.strip().upper().removesuffix(".JK")
    if not re.fullmatch(r"[A-Z0-9]{1,12}", symbol):
        return "Format ticker tidak valid. Contoh: /stock PGEO"
    if not (directory / "stocks" / f"{symbol}.json").is_file():
        return f"Ticker {symbol} tidak ditemukan pada snapshot saat ini."
    meta = _read(directory, "meta.json", "meta")
    stock = _read(directory, f"stocks/{symbol}.json", "stock")
    daily, investor = stock["daily"], stock["investor"]
    lines = [
        f"{symbol} | {daily['name']} | {meta['as_of']}",
        f"Daily #{daily['rank']}: {_signed(daily['flow_score'])} | {_label(daily['label'])}",
        f"Investor #{investor['rank']}: {_number(investor['investor_score'])}/100 | coverage {investor['coverage']:.0%}",
        "",
        "Alasan utama:",
    ]
    reasons = daily.get("reasons", [])[:2] + investor.get("reasons", [])[:2]
    lines.extend(f"- {reason['text_en']}" for reason in reasons)
    if not reasons:
        lines.append("- Belum ada alasan yang tersedia pada snapshot ini.")
    lines.extend(("", DISCLAIMER))
    return "\n".join(lines)


def answer(text: str, directory: Path | None = None) -> str:
    """Return a deterministic reply for a command or a bare stock symbol."""
    directory = directory or config.OUT_DIR
    entered = text.strip()
    if not entered:
        return HELP
    parts = entered.split()
    command = parts[0].lower().split("@", 1)[0]
    args = parts[1:]
    try:
        if command in ("/start", "/help", "help"):
            return HELP
        if command in ("/daily", "daily"):
            return _top(directory, "daily")
        if command in ("/weekly", "/investor", "weekly", "investor"):
            return _top(directory, "investor")
        if command in ("/brief", "brief"):
            horizon = args[0].lower() if args else "daily"
            if horizon not in ("daily", "weekly"):
                return "Gunakan /brief daily atau /brief weekly."
            return _brief(directory, horizon)
        if command in ("/top", "top"):
            if not args or args[0].lower() == "daily":
                return _top(directory, "daily")
            if args[0].lower() in ("weekly", "investor"):
                return _top(directory, "investor")
            return "Gunakan /top daily atau /top investor."
        if command in ("/stock", "stock"):
            return _stock(directory, args[0] if args else "")
        if len(parts) == 1 and re.fullmatch(r"[A-Za-z0-9]{1,12}(?:\.JK)?", entered):
            return _stock(directory, entered)
        return "Perintah belum dikenali.\n\n" + HELP
    except ValueError as error:
        return f"Flow Radar belum dapat menjawab: {error}"


def handle_update(update: dict, token: str, directory: Path | None = None) -> bool:
    """Reply to any Telegram chat containing a text message."""
    message = update.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("text"), str):
        return False
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        return False
    telegram.send_to_chat(answer(message["text"], directory), chat["id"], token)
    return True


def run(directory: Path | None = None, poll_timeout: int = 25) -> int:
    """Run until interrupted, accepting commands from every Telegram chat."""
    token = settings(("TELEGRAM_BOT_TOKEN",))["TELEGRAM_BOT_TOKEN"]
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty.")
    directory = directory or config.OUT_DIR
    _read(directory, "meta.json", "meta")
    print(f"Telegram bot is listening for public commands using snapshots in {directory}.")
    offset = None
    try:
        while True:
            try:
                updates = telegram.get_updates(token, offset=offset, timeout=poll_timeout)
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        offset = update_id + 1
                    try:
                        handle_update(update, token, directory)
                    except RuntimeError as error:
                        print(f"Telegram reply failed: {error}")
            except RuntimeError as error:
                print(f"Telegram polling failed: {error} Retrying in 3 seconds.")
                time.sleep(3)
    except KeyboardInterrupt:
        print("Telegram bot stopped.")
        return 0
