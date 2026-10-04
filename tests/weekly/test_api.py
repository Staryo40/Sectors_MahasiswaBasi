"""REST contracts, missing data, invalid paths and local frontend serving."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from radar import config
from radar.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client():
    return TestClient(create_app({"fixtures": ROOT / "fixtures/out"}))


@pytest.mark.parametrize("route,file_name", [
    ("meta", "meta.json"), ("daily", "daily.json"),
    ("investor", "investor.json"), ("briefs/daily", "brief_daily.json"),
    ("briefs/weekly", "brief_weekly.json"), ("stocks/bbca", "stocks/BBCA.json"),
])
def test_api_preserves_export_contracts(client, route, file_name):
    response = client.get(f"/api/snapshots/fixtures/{route}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == json.loads((ROOT / "fixtures/out" / file_name).read_text())


@pytest.mark.parametrize("route,status", [
    ("out/meta", 404), ("fixtures/stocks/MISSING", 404),
    ("other/meta", 422), ("fixtures/briefs/monthly", 422),
    ("fixtures/stocks/BBCA.JK", 422), ("fixtures/stocks/%2Eenv", 422),
])
def test_api_rejects_unavailable_or_invalid_requests(client, route, status):
    response = client.get(f"/api/snapshots/{route}")
    assert response.status_code == status
    assert "detail" in response.json()


def test_invalid_exports_fail_and_next_request_reads_new_data(tmp_path):
    client = TestClient(create_app({"out": tmp_path}))
    meta = tmp_path / "meta.json"
    meta.write_text('{broken')
    assert client.get("/api/snapshots/out/meta").status_code == 503
    meta.write_text('{}')
    assert client.get("/api/snapshots/out/meta").status_code == 503
    meta.write_text((ROOT / "fixtures/out/meta.json").read_text())
    assert client.get("/api/snapshots/out/meta").status_code == 200


def test_health_is_offline_and_paths_stay_at_repository_root(client):
    assert client.get("/api/health").json() == {"status": "ok", "sources": ["fixtures"]}
    assert config.ROOT == ROOT
    assert config.DB_PATH == ROOT / "data/sectors.db"


def test_built_frontend_and_unknown_api_are_separate(tmp_path):
    (tmp_path / "index.html").write_text('<div id="root"></div>')
    client = TestClient(create_app({}, tmp_path))
    assert client.get("/").status_code == 200
    assert client.get("/api/not-a-route").status_code == 404
