import json
from radar import config
from radar import __main__ as cli
from tests.weekly.test_export import seed


def persisted_database(db, tmp_path):
    seed(db)
    db.commit()
    target = tmp_path / "sectors.db"
    from radar.db import connect
    from contextlib import closing
    with closing(connect(target)) as disk:
        db.backup(disk)
    return target


def test_export_command_runs_from_sqlite(db, daily_stubs, tmp_path, capsys):
    source = persisted_database(db, tmp_path)
    out = tmp_path / "out"
    assert cli.main(["export", "--db", str(source), "--out", str(out)]) == 0
    assert json.loads((out / "meta.json").read_text())["as_of"] == "2026-10-02"
    assert "Exported 2026-10-02" in capsys.readouterr().out


def test_offline_one_command_prints_both_channels(db, daily_stubs, tmp_path, capsys):
    source = persisted_database(db, tmp_path)
    assert cli.main(["run-weekly", "--skip-refresh", "--db", str(source), "--out", str(tmp_path / "out")]) == 0
    printed = capsys.readouterr().out
    assert "[Telegram dry-run]" in printed and "[Email dry-run]" in printed
    assert printed.count(config.DISCLAIMER) == 2


def test_weekly_refresh_export_delivery_order(db, tmp_path, monkeypatch):
    source = persisted_database(db, tmp_path)
    monkeypatch.setattr(config, "DB_PATH", source)
    events = []
    monkeypatch.setattr(cli.jobs, "refresh_daily", lambda: events.append("daily refresh") or 0, raising=False)
    monkeypatch.setattr(cli.jobs, "refresh_weekly", lambda: events.append("weekly refresh") or 0, raising=False)
    def export(conn, as_of, out):
        events.append("export")
        out.mkdir()
        (out / "brief_weekly.json").write_text(json.dumps({"as_of": as_of, "items": [], "upcoming": []}))
    monkeypatch.setattr(cli, "build", export)
    monkeypatch.setattr(cli.telegram, "send", lambda text, dry_run: events.append(("telegram", dry_run)))
    monkeypatch.setattr(cli.mailer, "send", lambda subject, text, dry_run: events.append(("email", dry_run)))
    assert cli.main(["run-weekly", "--out", str(tmp_path / "out")]) == 0
    assert events == ["daily refresh", "weekly refresh", "export", ("telegram", True), ("email", True)]


def test_export_failure_prevents_delivery(db, daily_stubs, tmp_path, monkeypatch):
    source = persisted_database(db, tmp_path)
    monkeypatch.setattr(cli, "build", lambda *args: (_ for _ in ()).throw(NotImplementedError()))
    def unexpected(*args, **kwargs):
        raise AssertionError("Delivery must follow successful export")
    monkeypatch.setattr(cli.telegram, "send", unexpected)
    assert cli.main(["run-daily", "--skip-refresh", "--db", str(source)]) == 1


def test_refresh_missing_stops_before_partial_run(db, tmp_path, monkeypatch, capsys):
    source = persisted_database(db, tmp_path)
    monkeypatch.setattr(config, "DB_PATH", source)
    monkeypatch.delattr(cli.jobs, "refresh_daily", raising=False)
    monkeypatch.delattr(cli.jobs, "refresh_weekly", raising=False)
    assert cli.main(["run-weekly"]) == 1
    assert "Agent A refresh jobs are not available" in capsys.readouterr().out


def test_daily_send_opt_in_attempts_both_channels(db, daily_stubs, tmp_path, monkeypatch):
    source = persisted_database(db, tmp_path)
    calls = []
    def telegram(text, dry_run):
        calls.append(("telegram", dry_run))
        raise RuntimeError("mock failure")
    monkeypatch.setattr(cli.telegram, "send", telegram)
    monkeypatch.setattr(cli.mailer, "send", lambda subject, text, dry_run: calls.append(("email", dry_run)))
    assert cli.main(["run-daily", "--skip-refresh", "--send", "--db", str(source), "--out", str(tmp_path / "out")]) == 1
    assert calls == [("telegram", False), ("email", False)]


def test_validation_failure_stops_delivery(db, daily_stubs, tmp_path, monkeypatch, capsys):
    from jsonschema.exceptions import ValidationError
    source = persisted_database(db, tmp_path)
    monkeypatch.setattr(cli, "build", lambda *args: (_ for _ in ()).throw(ValidationError("invalid")))
    assert cli.main(["run-daily", "--skip-refresh", "--db", str(source)]) == 1
    assert "did not validate" in capsys.readouterr().out


def test_noncanonical_date_rejected_before_export(db, daily_stubs, tmp_path):
    import pytest
    source = persisted_database(db, tmp_path)
    with pytest.raises(SystemExit) as error:
        cli.main(["export", "--db", str(source), "--as-of", "20261002"])
    assert error.value.code == 2
