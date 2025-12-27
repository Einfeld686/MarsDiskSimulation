from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_run_one_dry_run_skips_setup(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["SKIP_SETUP"] = "1"
    env["OUT_ROOT"] = str(tmp_path)
    cmd = [
        "bash",
        str(REPO_ROOT / "scripts/runsets/mac/run_one.sh"),
        "--t",
        "4000",
        "--eps",
        "1.0",
        "--tau",
        "1.0",
        "--dry-run",
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)

    output = (result.stdout or "") + (result.stderr or "")
    assert result.returncode == 0, output
    assert "[setup] SKIP_SETUP=1; skipping venv setup" in output
    assert "[dry-run]" in output
    assert "python" in output
    assert "-m" in output
    assert "marsdisk.run" in output
    assert "--config" in output
    assert "scripts/runsets/common/base.yml" in output
