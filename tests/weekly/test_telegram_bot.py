import json
from pathlib import Path

from radar import config
from radar import __main__ as cli
from radar.deliver import telegram, telegram_bot


def test_command_answers_use_validated_fixture_snapshots():
    directory = config.FIXTURES_DIR / "out"
    daily = telegram_bot.answer("/daily", directory)
    weekly = telegram_bot.answer("/top investor", directory)
    stock = telegram_bot.answer("BBCA", directory)

    assert "Daily Flow" in daily and "/stock TICKER" in daily
    assert "Investor Lens" in weekly and "coverage" in weekly
    assert "BBCA" in stock and "Alasan utama" in stock
    assert config.DISCLAIMER.split(".")[0] not in stock
    assert "Bukan nasihat investasi" in stock


def test_help_invalid_commands_and_symbols():
    directory = config.FIXTURES_DIR / "out"
    assert "/stock PGEO" in telegram_bot.answer("/help", directory)
    assert "belum dikenali" in telegram_bot.answer("hello bot", directory)
    assert "Format ticker tidak valid" in telegram_bot.answer("/stock", directory)
    assert "tidak ditemukan" in telegram_bot.answer("ZZZZ", directory)
    assert "/brief daily" in telegram_bot.answer("/brief other", directory)


def test_handle_update_accepts_any_chat(monkeypatch):
    sent = []
    monkeypatch.setattr(
        telegram,
        "send_to_chat",
        lambda text, chat_id, token: sent.append((text, chat_id, token)),
    )

    assert telegram_bot.handle_update(
        {"update_id": 10, "message": {"chat": {"id": 987654}, "text": "/daily"}},
        "test-token",
        config.FIXTURES_DIR / "out",
    )
    assert sent and sent[0][1:] == (987654, "test-token")
    assert not telegram_bot.handle_update(
        {"update_id": 11, "message": {"chat": {"id": 123}, "sticker": {}}},
        "test-token",
        config.FIXTURES_DIR / "out",
    )


def test_get_updates_posts_offset(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return b'{"ok": true, "result": [{"update_id": 8}]}'

        return Response()

    monkeypatch.setattr(telegram.urllib.request, "urlopen", urlopen)
    assert telegram.get_updates("token", offset=7, timeout=10) == [{"update_id": 8}]
    payload = json.loads(requests[0][0].data)
    assert payload == {"timeout": 10, "allowed_updates": ["message"], "offset": 7}
    assert requests[0][1] == 15


def test_bot_cli_does_not_require_database(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        cli.telegram_bot,
        "run",
        lambda directory, poll_timeout: calls.append((directory, poll_timeout)) or 0,
    )
    missing = tmp_path / "missing.db"
    out = Path("fixtures/out")
    assert cli.main(["bot", "--db", str(missing), "--out", str(out)]) == 0
    assert calls == [(out, 25)]
