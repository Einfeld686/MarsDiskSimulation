from __future__ import annotations

import importlib.util
import json
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_module(path: Path):
    module_name = "hook_" + "_".join(path.parts[-4:]).replace(".", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_plot_sweep_run_hook_invokes_research_script(tmp_path: Path, monkeypatch) -> None:
    module = _load_module(REPO_ROOT / "scripts/runsets/common/hooks/plot_sweep_run.py")
    calls: dict[str, object] = {}

    def fake_run(cmd, cwd=None, **_kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.sys, "argv", ["plot_sweep_run.py", "--run-dir", str(tmp_path)])

    rc = module.main()

    assert rc == 0
    expected_script = REPO_ROOT / "scripts" / "research" / "plot_sweep_run.py"
    cmd = calls["cmd"]
    assert cmd[0] == module.sys.executable
    assert Path(cmd[1]) == expected_script
    assert cmd[2] == str(tmp_path)
    assert Path(calls["cwd"]) == REPO_ROOT


def test_preflight_streaming_hook_invokes_research_script(tmp_path: Path, monkeypatch) -> None:
    module = _load_module(REPO_ROOT / "scripts/runsets/common/hooks/preflight_streaming.py")
    calls: dict[str, object] = {}

    def fake_run(cmd, cwd=None, **_kwargs):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module.sys, "argv", ["preflight_streaming.py", "--run-dir", str(tmp_path)])

    rc = module.main()

    assert rc == 0
    expected_script = REPO_ROOT / "scripts" / "research" / "preflight_streaming_check.py"
    cmd = calls["cmd"]
    assert cmd[0] == module.sys.executable
    assert Path(cmd[1]) == expected_script
    assert cmd[2] == str(tmp_path)
    assert Path(calls["cwd"]) == REPO_ROOT


def test_evaluate_tau_supply_hook_writes_json(tmp_path: Path, monkeypatch) -> None:
    module = _load_module(REPO_ROOT / "scripts/runsets/common/hooks/evaluate_tau_supply.py")
    calls: dict[str, object] = {}

    payload = {"success": True, "reason": "ok"}

    def fake_run(cmd, cwd=None, capture_output=False, text=False):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return types.SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(
        module.sys,
        "argv",
        [
            "evaluate_tau_supply.py",
            "--run-dir",
            str(tmp_path),
            "--window-spans",
            "0.5-1.0",
            "--min-duration-days",
            "0.1",
            "--threshold-factor",
            "0.9",
        ],
    )

    rc = module.main()

    assert rc == 0
    expected_script = REPO_ROOT / "scripts" / "research" / "evaluate_tau_supply.py"
    cmd = calls["cmd"]
    assert cmd[0] == module.sys.executable
    assert Path(cmd[1]) == expected_script
    assert "--run-dir" in cmd
    assert str(tmp_path) in cmd
    assert "--window-spans" in cmd
    assert "0.5-1.0" in cmd
    assert "--min-duration-days" in cmd
    assert "0.1" in cmd
    assert "--threshold-factor" in cmd
    assert "0.9" in cmd
    assert Path(calls["cwd"]) == REPO_ROOT

    out_path = tmp_path / "checks" / "tau_supply_eval.json"
    assert out_path.is_file()
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert written == payload
