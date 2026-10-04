"""Sectors Financial API client with cache, credit ledger and spending guards.

Billing rules (docs.sectors.app): 2xx costs the endpoint's stated price, 404
costs 1 credit, and 400/401/403/429/5xx are free.
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping

from radar import config
from radar.ingest import ledger
from radar.ingest.cache import Cache

MAX_RETRIES = 3
# Cloudflare rejects the default Python-urllib agent (error 1010).
USER_AGENT = "sectors-radar/0.1"
TIMEOUT_SECONDS = 30

# (url, headers, timeout) -> (status, body bytes)
Transport = Callable[[str, Mapping[str, str], float], tuple[int, bytes]]


class SectorsError(Exception):
    def __init__(self, status: int, url: str, body: Any = None) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status = status
        self.url = url
        self.body = body


class NotFound(SectorsError):
    """404: the addressed symbol or slug does not exist. Billed 1 credit."""


class LiveCallBlocked(Exception):
    """A request was not in the cache and SECTORS_LIVE is not 1."""


class CreditCapExceeded(Exception):
    """The request would push total spend past CREDIT_CAP."""


def _urllib_transport(url: str, headers: Mapping[str, str], timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def build_url(path: str, params: Mapping[str, Any] | None = None) -> str:
    url = f"{config.BASE_URL}/{path.strip('/')}/"
    if params:
        url += "?" + urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items()))
    return url


def _decode(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return raw.decode("utf-8", errors="replace")


class SectorsClient:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        cache: Cache | None = None,
        api_key: str | None = None,
        live: bool | None = None,
        credit_cap: int | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.conn = conn
        self.cache = cache if cache is not None else Cache()
        self._api_key = api_key
        self.live = config.live_enabled() if live is None else live
        self.credit_cap = config.credit_cap() if credit_cap is None else credit_cap
        self.transport = transport or _urllib_transport
        self.sleep = sleep

    def get(self, path: str, params: Mapping[str, Any] | None = None, cost: int = 1) -> Any:
        """GET ``path`` and return the decoded JSON body.

        ``cost`` is the endpoint's credit price for a successful call, taken
        from docs/sectors-api.md. Cached responses are free and need no key.
        """
        url = build_url(path, params)

        cached = self.cache.get(path, params)
        if cached is not None:
            ledger.record(self.conn, url, cached["status"], 0, from_cache=True)
            if cached["status"] == 404:
                raise NotFound(404, url, cached["body"])
            return cached["body"]

        if not self.live:
            raise LiveCallBlocked(f"Not cached and SECTORS_LIVE is not 1: {url}")

        spent = ledger.credits_spent(self.conn)
        if spent + cost > self.credit_cap:
            raise CreditCapExceeded(
                f"{spent} credits spent, this call costs {cost}, cap is {self.credit_cap}: {url}"
            )

        key = self._api_key if self._api_key is not None else config.api_key()
        headers = {"Authorization": key, "Accept": "application/json", "User-Agent": USER_AGENT}

        status, raw = 0, b""
        for attempt in range(MAX_RETRIES + 1):
            status, raw = self.transport(url, headers, TIMEOUT_SECONDS)
            if status != 429 and status < 500:
                break
            if attempt < MAX_RETRIES:
                self.sleep(2**attempt)

        body = _decode(raw)
        if 200 <= status < 300:
            self.cache.put(path, params, status, body)
            ledger.record(self.conn, url, status, cost, from_cache=False)
            return body
        if status == 404:
            # Cached so the same unknown symbol is never billed twice.
            self.cache.put(path, params, status, body)
            ledger.record(self.conn, url, status, 1, from_cache=False)
            raise NotFound(status, url, body)

        ledger.record(self.conn, url, status, 0, from_cache=False)
        raise SectorsError(status, url, body)
