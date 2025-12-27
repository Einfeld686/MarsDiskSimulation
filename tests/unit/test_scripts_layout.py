from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_text(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_new_paths_exist() -> None:
    required = [
        "scripts/admin/analysis_sync.py",
        "scripts/admin/doc_sync_agent.py",
        "scripts/admin/make_qpr_table.py",
        "scripts/admin/analyze_radius_trend.py",
        "scripts/admin/collect_series.py",
        "scripts/debug/debug_blowout_chi_scaling.py",
        "scripts/plots/plot_tau_timescales.py",
        "scripts/plots/windows/plot_tau_timescales.cmd",
        "scripts/runs/run_autotuned.py",
        "scripts/sweeps/sweep_heatmaps.py",
        "scripts/runsets/windows/legacy/run_sublim_cooling_win.cmd",
    ]
    missing = [path for path in required if not (REPO_ROOT / path).is_file()]
    assert not missing, f"Missing files: {missing}"


def test_old_paths_absent() -> None:
    old_paths = [
        "scripts/analysis_sync.py",
        "scripts/doc_sync_agent.py",
        "scripts/make_qpr_table.py",
        "scripts/analyze_radius_trend.py",
        "scripts/plot_tau_timescales.py",
        "scripts/plot_tau_timescales.cmd",
        "scripts/run_autotuned.py",
        "scripts/sweep_heatmaps.py",
        "scripts/run_sublim_cooling_win.cmd",
    ]
    still_present = [path for path in old_paths if (REPO_ROOT / path).exists()]
    assert not still_present, f"Old paths still present: {still_present}"


def test_runsets_mac_wrappers_reference_common_paths() -> None:
    run_one = _read_text("scripts/runsets/mac/run_one.sh")
    assert 'CONFIG_PATH="scripts/runsets/common/base.yml"' in run_one
    assert 'OVERRIDES_PATH="scripts/runsets/mac/overrides.txt"' in run_one
    assert 'GEOMETRY_MODE="1D"' in run_one
    assert "scripts/research/run_temp_supply_sweep.sh" in run_one

    run_sweep = _read_text("scripts/runsets/mac/run_sweep.sh")
    assert 'CONFIG_PATH="scripts/runsets/common/base.yml"' in run_sweep
    assert 'OVERRIDES_PATH="scripts/runsets/mac/overrides.txt"' in run_sweep
    assert 'GEOMETRY_MODE="1D"' in run_sweep
    assert "scripts/research/run_temp_supply_sweep.sh" in run_sweep


def test_plot_tau_timescales_cmd_points_to_new_location() -> None:
    cmd_text = _read_text("scripts/plots/windows/plot_tau_timescales.cmd")
    assert r'set "REPO=%~dp0..\..\.."' in cmd_text
    assert r"scripts\plots\plot_tau_timescales.py" in cmd_text


def test_windows_legacy_run_scripts_set_repo_root() -> None:
    legacy_cmds = [
        "scripts/runsets/windows/legacy/run_sublim_cooling.cmd",
        "scripts/runsets/windows/legacy/run_sublim_cooling_2yr_0.005.cmd",
        "scripts/runsets/windows/legacy/run_sublim_cooling_win.cmd",
        "scripts/runsets/windows/legacy/run_sublim_windows.cmd",
    ]
    for rel_path in legacy_cmds:
        cmd_text = _read_text(rel_path)
        assert r"set REPO=%~dp0..\..\..\.." in cmd_text
        assert 'pushd "%REPO%"' in cmd_text
