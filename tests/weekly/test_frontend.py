"""Run the React interaction suite against fixtures and exported market data."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"


@pytest.mark.parametrize("source", ["fixtures", "out"])
def test_frontend_contract_and_interactions(source):
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm or not (FRONTEND / "node_modules/vitest").exists():
        pytest.skip("Run npm ci in frontend to install the React test dependencies")
    if source == "out" and not (ROOT / "data/out/meta.json").exists():
        pytest.skip("Real exported output is not available")
    environment = dict(os.environ, RADAR_TEST_SOURCE=source, NO_COLOR="1")
    result = subprocess.run(
        [npm, "run", "test", "--", "src/test/dashboard.test.tsx"],
        cwd=FRONTEND,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
