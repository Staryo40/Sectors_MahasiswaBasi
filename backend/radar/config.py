"""Paths, constants and environment access shared by every module.

Owned by agent A. Score weights do not live here: see
``radar/signals/flow_config.py`` and ``radar/signals/investor_config.py``.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get("RADAR_ROOT", _DEFAULT_ROOT)).resolve()
DATA_DIR = Path(os.environ.get("RADAR_DATA_DIR", ROOT / "data")).resolve()
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "sectors.db"
OUT_DIR = DATA_DIR / "out"
FIXTURES_DIR = Path(
    os.environ.get("RADAR_FIXTURES_DIR", ROOT / "fixtures")
).resolve()
ENV_PATH = ROOT / ".env"

BASE_URL = "https://api.sectors.app/v2"
UNIVERSE_INDEX = "LQ45"
DEFAULT_CREDIT_CAP = 400

DISCLAIMER = "Information and analysis only. Not investment advice."


def load_env(path: Path = ENV_PATH) -> None:
    """Load KEY=VALUE lines from .env into os.environ without overriding."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("'\"")
        os.environ.setdefault(key.strip(), value)


def api_key() -> str:
    load_env()
    key = os.environ.get("SECTORS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SECTORS_API_KEY is not set. Put it in .env (see .env.example).")
    return key


def live_enabled() -> bool:
    load_env()
    return os.environ.get("SECTORS_LIVE", "").strip() == "1"


def credit_cap() -> int:
    load_env()
    raw = os.environ.get("CREDIT_CAP", "").strip()
    return int(raw) if raw else DEFAULT_CREDIT_CAP


def frontend_origins() -> tuple[str, ...]:
    """Return exact browser origins allowed to read the public API."""
    load_env()
    raw = os.environ.get("FRONTEND_ORIGINS", "")
    return tuple(
        origin.rstrip("/")
        for item in raw.split(",")
        if (origin := item.strip().rstrip("/"))
    )
