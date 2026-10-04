"""Disk cache for raw API responses, keyed by path and sorted params."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from radar import config


def cache_key(path: str, params: Mapping[str, Any] | None = None) -> str:
    items = sorted((str(k), str(v)) for k, v in (params or {}).items())
    raw = json.dumps([path.strip("/"), items], separators=(",", ":"))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else config.CACHE_DIR

    def _file(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, path: str, params: Mapping[str, Any] | None = None) -> dict | None:
        """Return the stored entry ``{path, params, status, fetched_at, body}`` or None."""
        file = self._file(cache_key(path, params))
        if not file.exists():
            return None
        return json.loads(file.read_text(encoding="utf-8"))

    def put(self, path: str, params: Mapping[str, Any] | None, status: int, body: Any) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = {
            "path": path,
            "params": dict(params or {}),
            "status": status,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "body": body,
        }
        file = self._file(cache_key(path, params))
        tmp = file.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, file)
