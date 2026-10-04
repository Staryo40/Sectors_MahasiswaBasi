import importlib

import pytest

from radar import config, db

TABLES = {
    "companies",
    "prices",
    "foreign_flow",
    "broker_summary",
    "brokers",
    "holder_mix",
    "filings",
    "corporate_actions",
    "suspensions",
    "api_calls",
}

INTERFACES = {
    "radar.signals.common": ["trading_days", "percentile_rank"],
    "radar.signals.flow": ["compute", "top_brokers", "insider_ratio"],
    "radar.signals.changes_daily": ["diff"],
    "radar.signals.investor": ["compute"],
    "radar.signals.changes_weekly": ["diff"],
}


def test_init_schema_creates_every_contract_table():
    conn = db.connect(":memory:")
    db.init_schema(conn)
    db.init_schema(conn)  # idempotent

    names = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert TABLES <= names


@pytest.mark.parametrize("module, functions", INTERFACES.items())
def test_interface_functions_exist(module, functions):
    loaded = importlib.import_module(module)
    for name in functions:
        assert callable(getattr(loaded, name))


def test_load_env_does_not_override(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nFOO_RADAR=from_file\nBAR_RADAR='quoted'\n")
    monkeypatch.setenv("FOO_RADAR", "from_shell")
    monkeypatch.delenv("BAR_RADAR", raising=False)

    config.load_env(env)

    import os

    assert os.environ["FOO_RADAR"] == "from_shell"
    assert os.environ["BAR_RADAR"] == "quoted"
