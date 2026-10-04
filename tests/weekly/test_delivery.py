import io
import json
from unittest.mock import MagicMock
import pytest
from radar import config
from radar.deliver import telegram, mailer
from radar.deliver.settings import settings

@pytest.fixture
def blank_env(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENV_PATH", tmp_path / "empty.env")
    for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"):
        monkeypatch.delenv(key, raising=False)


def test_format_and_both_dry_runs(blank_env, capsys):
    brief = {"as_of": "2026-10-02", "items": [{"text_en": "BBCA entered the top five."}],
             "upcoming": [{"date": "2026-10-08", "symbol": "TLKM", "type": "dividend_ex_date"}]}
    text = telegram.format_brief(brief)
    assert "BBCA entered the top five." in text
    assert "2026-10-08 — TLKM: dividend ex date" in text
    assert config.DISCLAIMER in text
    telegram.send(text)
    mailer.send("Weekly radar", text)
    printed = capsys.readouterr().out
    assert "[Telegram dry-run]" in printed
    assert "[Email dry-run]" in printed
    assert printed.count(config.DISCLAIMER) == 2


def test_empty_channels_skipped(blank_env, capsys):
    telegram.send("brief", dry_run=False)
    mailer.send("subject", "brief", dry_run=False)
    printed = capsys.readouterr().out
    assert "Telegram skipped" in printed
    assert "Email skipped" in printed


def test_settings_does_not_load_live_flag(blank_env, monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("SECTORS_LIVE=1\nSECTORS_API_KEY=never-read\nTELEGRAM_CHAT_ID=from-file\n")
    monkeypatch.setattr(config, "ENV_PATH", env)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "from-environment")
    assert settings(("TELEGRAM_CHAT_ID",)) == {"TELEGRAM_CHAT_ID": "from-environment"}
    import os
    assert "SECTORS_LIVE" not in os.environ


def test_telegram_mocked_request(blank_env, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    requests = []
    def urlopen(request, timeout):
        requests.append(request)
        assert timeout == 30
        return io.BytesIO(b'{"ok":true}')
    monkeypatch.setattr(telegram.urllib.request, "urlopen", urlopen)
    telegram.send("brief", dry_run=False)
    assert json.loads(requests[0].data) == {"chat_id": "test-chat", "text": "brief"}
    assert requests[0].get_method() == "POST"


def test_telegram_chunking_keeps_unicode():
    text = "😀" * 3000
    chunks = list(telegram._chunks(text))
    assert "".join(chunks) == text
    assert all(len(chunk.encode("utf-16-le")) // 2 <= 4000 for chunk in chunks)


def test_telegram_errors_do_not_expose_token(blank_env, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-secret")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")
    def fail(*args, **kwargs):
        raise telegram.urllib.error.URLError("test-secret")
    monkeypatch.setattr(telegram.urllib.request, "urlopen", fail)
    with pytest.raises(RuntimeError) as error:
        telegram.send("brief", dry_run=False)
    assert "test-secret" not in str(error.value)


def test_smtp_starttls_and_html(blank_env, monkeypatch):
    for key, value in {"SMTP_HOST": "smtp.example.invalid", "SMTP_PORT": "587", "SMTP_USER": "user", "SMTP_PASSWORD": "secret", "EMAIL_FROM": "from@example.invalid", "EMAIL_TO": "one@example.invalid, two@example.invalid"}.items():
        monkeypatch.setenv(key, value)
    smtp = MagicMock()
    constructor = MagicMock()
    constructor.return_value.__enter__.return_value = smtp
    monkeypatch.setattr(mailer.smtplib, "SMTP", constructor)
    mailer.send("Weekly radar", "plain brief", html="<p>plain brief</p>", dry_run=False)
    constructor.assert_called_once_with("smtp.example.invalid", 587, timeout=30)
    assert smtp.ehlo.call_count == 2
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("user", "secret")
    message = smtp.send_message.call_args.args[0]
    assert message["Subject"] == "Weekly radar"
    assert message.is_multipart()
    assert smtp.send_message.call_args.kwargs["to_addrs"] == ["one@example.invalid", "two@example.invalid"]
    methods = [call[0] for call in smtp.method_calls]
    assert methods.index("starttls") < methods.index("login") < methods.index("send_message")
