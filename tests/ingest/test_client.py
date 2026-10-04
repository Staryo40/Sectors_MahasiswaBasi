import json

import pytest

from radar import db
from radar.ingest import ledger
from radar.ingest.cache import Cache, cache_key
from radar.ingest.client import (
    CreditCapExceeded,
    LiveCallBlocked,
    NotFound,
    SectorsClient,
    SectorsError,
    build_url,
)

SECRET = "test-key-do-not-leak"


class FakeTransport:
    """Returns queued (status, body) pairs and records what was requested."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers)))
        status, body = self.responses.pop(0)
        return status, json.dumps(body).encode()


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    db.init_schema(connection)
    yield connection
    connection.close()


def make_client(conn, tmp_path, transport, *, live=True, credit_cap=400):
    return SectorsClient(
        conn,
        cache=Cache(tmp_path / "cache"),
        api_key=SECRET,
        live=live,
        credit_cap=credit_cap,
        transport=transport,
        sleep=lambda seconds: None,
    )


def test_success_is_billed_cached_and_sent_with_raw_key(conn, tmp_path):
    transport = FakeTransport((200, {"symbol": "BBCA.JK"}))
    client = make_client(conn, tmp_path, transport)

    assert client.get("daily/BBCA", {"start": "2026-09-01"}) == {"symbol": "BBCA.JK"}

    url, headers = transport.calls[0]
    assert url == "https://api.sectors.app/v2/daily/BBCA/?start=2026-09-01"
    assert headers["Authorization"] == SECRET
    assert ledger.credits_spent(conn) == 1


def test_cache_hit_makes_no_call_and_costs_nothing(conn, tmp_path):
    transport = FakeTransport((200, {"n": 1}))
    client = make_client(conn, tmp_path, transport)
    client.get("brokers", cost=1)

    assert client.get("brokers", cost=1) == {"n": 1}

    assert len(transport.calls) == 1
    assert ledger.credits_spent(conn) == 1
    assert ledger.live_calls(conn) == 1


def test_cache_serves_without_live_flag(conn, tmp_path):
    make_client(conn, tmp_path, FakeTransport((200, [1, 2]))).get("brokers")
    offline = make_client(conn, tmp_path, FakeTransport(), live=False)

    assert offline.get("brokers") == [1, 2]


def test_live_call_blocked_without_flag(conn, tmp_path):
    transport = FakeTransport()
    client = make_client(conn, tmp_path, transport, live=False)

    with pytest.raises(LiveCallBlocked):
        client.get("brokers")

    assert transport.calls == []
    assert ledger.credits_spent(conn) == 0


def test_credit_cap_refuses_before_calling(conn, tmp_path):
    transport = FakeTransport((200, {}))
    client = make_client(conn, tmp_path, transport, credit_cap=3)
    client.get("brokers/top", {"date": "2026-10-01"}, cost=2)

    with pytest.raises(CreditCapExceeded):
        client.get("most-traded", cost=2)

    assert len(transport.calls) == 1
    assert ledger.credits_spent(conn) == 2


def test_429_is_retried_and_only_success_is_billed(conn, tmp_path):
    transport = FakeTransport((429, {"error": "RATE_LIMIT_EXCEEDED"}), (200, {"ok": True}))
    client = make_client(conn, tmp_path, transport)

    assert client.get("brokers") == {"ok": True}
    assert len(transport.calls) == 2
    assert ledger.credits_spent(conn) == 1


def test_5xx_gives_up_after_retries_and_is_free(conn, tmp_path):
    transport = FakeTransport(*[(503, {})] * 4)
    client = make_client(conn, tmp_path, transport)

    with pytest.raises(SectorsError) as err:
        client.get("brokers")

    assert err.value.status == 503
    assert len(transport.calls) == 4
    assert ledger.credits_spent(conn) == 0


def test_404_is_billed_one_credit_once(conn, tmp_path):
    transport = FakeTransport((404, {"error": "NOT_FOUND"}))
    client = make_client(conn, tmp_path, transport)

    with pytest.raises(NotFound):
        client.get("company/report/ZZZZ", {"sections": "overview"}, cost=1)
    with pytest.raises(NotFound):
        client.get("company/report/ZZZZ", {"sections": "overview"}, cost=1)

    assert len(transport.calls) == 1
    assert ledger.credits_spent(conn) == 1


def test_400_is_free_and_not_retried(conn, tmp_path):
    transport = FakeTransport((400, {"error": "BAD_REQUEST"}))
    client = make_client(conn, tmp_path, transport)

    with pytest.raises(SectorsError) as err:
        client.get("daily/BBCA", {"start": "nonsense"})

    assert err.value.status == 400
    assert len(transport.calls) == 1
    assert ledger.credits_spent(conn) == 0


def test_key_never_reaches_ledger_or_cache(conn, tmp_path):
    client = make_client(conn, tmp_path, FakeTransport((200, {"ok": True})))
    client.get("brokers")

    urls = [row["url"] for row in conn.execute("SELECT url FROM api_calls")]
    cached = "".join(p.read_text() for p in (tmp_path / "cache").iterdir())
    assert SECRET not in "".join(urls)
    assert SECRET not in cached


def test_cache_key_ignores_param_order_and_slashes():
    assert cache_key("/daily/BBCA/", {"a": 1, "b": 2}) == cache_key("daily/BBCA", {"b": 2, "a": 1})
    assert cache_key("daily/BBCA", {"a": 1}) != cache_key("daily/BBRI", {"a": 1})
    assert build_url("/daily/BBCA/") == "https://api.sectors.app/v2/daily/BBCA/"
