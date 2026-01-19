#!/usr/bin/env python3
"""Run a single temp-supply case using env/overrides in a cmd-compatible way."""
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def _is_true(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_args(value: str | None) -> list[str]:
    if not value:
        return []
    return shlex.split(value, posix=os.name != "nt")


def _sanitize_run_ts(value: str) -> str:
    value = value.replace(":", "")
    value = value.replace(" ", "_")
    value = value.replace("/", "-")
    value = value.replace("\\", "-")
    return value


def _sanitize_sweep_tag(value: str) -> str:
    value = value.replace(":", "")
    value = value.replace(" ", "_")
    value = value.replace("/", "-")
    value = value.replace("\\", "-")
    return value


def _format_title_token(raw: str) -> str:
    token = raw
    if token.startswith("0."):
        token = "0p" + token[2:]
    token = token.replace(".", "p")
    return token


def _run_command(
    cmd: list[str],
    *,
    capture: bool = False,
    text: bool = True,
    quiet: bool = False,
) -> subprocess.CompletedProcess:
    if not quiet:
        print(f"[debug] cmd: {' '.join(cmd)}")
    return subprocess.run(cmd, check=False, capture_output=capture, text=text)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-config", default=None)
    ap.add_argument("--t", dest="t_value", default=None)
    ap.add_argument("--eps", dest="eps_value", default=None)
    ap.add_argument("--tau", dest="tau_value", default=None)
    ap.add_argument("--i0", dest="i0_value", default=None)
    ap.add_argument("--mu", dest="mu_value", default=None)
    ap.add_argument("--seed", dest="seed_value", default=None)
    ap.add_argument("--run-ts", default=None)
    ap.add_argument("--batch-seed", default=None)
    ap.add_argument("--git-sha", default=None)
    ap.add_argument("--sweep-tag", default=None)
    ap.add_argument("--base-overrides", default=None)
    ap.add_argument("--extra-overrides", default=None)
    ap.add_argument("--case-overrides", default=None)
    ap.add_argument("--merged-overrides", default=None)
    ap.add_argument("--python-exe", default=None)
    ap.add_argument("--python-args", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    quiet_mode = _is_true(_env("QUIET_MODE"))
    debug_mode = _is_true(_env("DEBUG"))

    def log_info(message: str) -> None:
        if not quiet_mode:
            print(f"[info] {message}")

    def log_warn(message: str) -> None:
        print(f"[warn] {message}")

    def log_error(message: str) -> None:
        print(f"[error] {message}")

    def log_debug(message: str) -> None:
        if debug_mode:
            print(f"[debug] {message}")

    repo_root = Path(__file__).resolve().parents[3]

    python_exe = args.python_exe or _env("PYTHON_EXE") or sys.executable
    python_args = args.python_args or _env("PYTHON_ARGS")
    python_cmd = [python_exe] + _split_args(python_args)

    run_one_t = args.t_value or _env("RUN_ONE_T")
    run_one_eps = args.eps_value or _env("RUN_ONE_EPS")
    run_one_tau = args.tau_value or _env("RUN_ONE_TAU")
    run_one_i0 = args.i0_value or _env("RUN_ONE_I0")
    run_one_mu = args.mu_value or _env("RUN_ONE_MU") or _env("SUPPLY_MU_ORBIT10PCT")
    if not run_one_t:
        log_error("RUN_ONE_T is required for run_one.py")
        return 1
    if not run_one_eps:
        log_error("RUN_ONE_EPS is required for run_one.py")
        return 1
    if not run_one_tau:
        log_error("RUN_ONE_TAU is required for run_one.py")
        return 1
    if not run_one_i0:
        log_error("RUN_ONE_I0 is required for run_one.py")
        return 1

    run_one_seed = args.seed_value or _env("RUN_ONE_SEED")

    run_ts = args.run_ts or _env("RUN_TS")
    if not run_ts:
        timestamp_py = repo_root / "scripts/runsets/common/timestamp.py"
        result = _run_command(python_cmd + [str(timestamp_py)], capture=True, quiet=quiet_mode)
        run_ts = (result.stdout or "").strip()
    if not run_ts:
        log_error("RUN_TS is required for run_one.py")
        return 1
    run_ts_sanitized = _sanitize_run_ts(run_ts)
    if run_ts_sanitized != run_ts:
        log_warn(f'RUN_TS sanitized: "{run_ts}" -> "{run_ts_sanitized}"')
    run_ts = run_ts_sanitized

    git_sha = args.git_sha or _env("GIT_SHA")
    if not git_sha:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        git_sha = (result.stdout or "").strip()
    if not git_sha:
        git_sha = "nogit"

    batch_seed = args.batch_seed or _env("BATCH_SEED")
    if not batch_seed:
        next_seed_py = Path(_env("NEXT_SEED_PY", "") or repo_root / "scripts/runsets/common/next_seed.py")
        result = _run_command(python_cmd + [str(next_seed_py)], capture=True, quiet=quiet_mode)
        batch_seed = (result.stdout or "").strip()
    if not batch_seed:
        batch_seed = "0"

    sweep_tag = args.sweep_tag or _env("SWEEP_TAG") or "temp_supply_sweep"
    sweep_tag_sanitized = _sanitize_sweep_tag(sweep_tag)
    if sweep_tag_sanitized != sweep_tag:
        log_warn(f'SWEEP_TAG sanitized: "{sweep_tag}" -> "{sweep_tag_sanitized}"')
    sweep_tag = sweep_tag_sanitized

    base_config = args.base_config or _env("BASE_CONFIG")
    if not base_config:
        base_config = str(repo_root / "configs/sweep_temp_supply/temp_supply_T4000_eps1.yml")

    run_one_mode = _is_true(_env("RUN_ONE_MODE"))
    tmp_root = _env("TMP_ROOT")
    if not tmp_root:
        tmp_root_base = _env("TEMP") or _env("TMP") or str(repo_root / "tmp")
        tmp_root = tmp_root_base
        if run_one_mode and run_one_seed:
            tmp_root = os.path.join(
                tmp_root_base,
                f"marsdisk_tmp_{run_ts}_{batch_seed}_{run_one_seed}",
            )
    Path(tmp_root).mkdir(parents=True, exist_ok=True)

    base_overrides_file = args.base_overrides or _env("BASE_OVERRIDES_FILE")
    case_overrides_file = args.case_overrides or _env("CASE_OVERRIDES_FILE")
    merged_overrides_file = args.merged_overrides or _env("MERGED_OVERRIDES_FILE")
    if not base_overrides_file:
        base_overrides_file = str(
            Path(tmp_root) / f"marsdisk_overrides_base_{run_ts}_{batch_seed}.txt"
        )
    if not case_overrides_file:
        case_overrides_file = str(
            Path(tmp_root) / f"marsdisk_overrides_case_{run_ts}_{batch_seed}.txt"
        )
    if not merged_overrides_file:
        merged_overrides_file = str(
            Path(tmp_root) / f"marsdisk_overrides_merged_{run_ts}_{batch_seed}.txt"
        )

    extra_overrides_file = args.extra_overrides or _env("EXTRA_OVERRIDES_FILE")
    if extra_overrides_file and not Path(extra_overrides_file).exists():
        log_warn(f"EXTRA_OVERRIDES_FILE not found: {extra_overrides_file}")
        extra_overrides_file = None

    batch_root = _env("BATCH_ROOT") or _env("OUT_ROOT") or "out"
    batch_dir = Path(batch_root) / sweep_tag / f"{run_ts}__{git_sha}__seed{batch_seed}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    eps_title = _format_title_token(run_one_eps)
    tau_title = _format_title_token(run_one_tau)
    i0_title = _format_title_token(run_one_i0)
    title_parts = [
        f"T{run_one_t}",
        f"eps{eps_title}",
        f"tau{tau_title}",
        f"i0{i0_title}",
    ]
    if run_one_mu:
        mu_title = _format_title_token(run_one_mu)
        title_parts.append(f"mu{mu_title}")
    title = "_".join(title_parts)
    outdir_rel = batch_dir / title
    outdir = outdir_rel.resolve()
    (outdir / "series").mkdir(parents=True, exist_ok=True)
    (outdir / "checks").mkdir(parents=True, exist_ok=True)

    if not run_one_mode:
        missing = []
        for key in (
            "GEOMETRY_MODE",
            "SUPPLY_MODE",
            "SHIELDING_MODE",
            "SUPPLY_INJECTION_MODE",
            "SUPPLY_TRANSPORT_MODE",
        ):
            if not _env(key):
                missing.append(key)
        if missing:
            log_warn(
                "physical env missing for standalone run_one.py: "
                + ", ".join(missing)
            )

    write_base_overrides_py = repo_root / "scripts/runsets/common/write_base_overrides.py"
    result = _run_command(
        python_cmd + [str(write_base_overrides_py), "--out", base_overrides_file],
        quiet=quiet_mode,
    )
    if result.returncode != 0 or not Path(base_overrides_file).exists():
        log_error(f"failed to build base overrides: {base_overrides_file}")
        return result.returncode or 1

    seed_value = run_one_seed
    if not seed_value:
        next_seed_py = Path(_env("NEXT_SEED_PY", "") or repo_root / "scripts/runsets/common/next_seed.py")
        result = _run_command(python_cmd + [str(next_seed_py)], capture=True, quiet=quiet_mode)
        seed_value = (result.stdout or "").strip()
    if not seed_value:
        seed_value = batch_seed

    cool_mode = _env("COOL_MODE") or ""
    cool_to_k = _env("COOL_TO_K")
    cool_margin_years = _env("COOL_MARGIN_YEARS")
    cool_search_years = _env("COOL_SEARCH_YEARS")
    substep_fast_blowout = _env("SUBSTEP_FAST_BLOWOUT")
    substep_max_ratio = _env("SUBSTEP_MAX_RATIO")
    stream_mem_gb = _env("STREAM_MEM_GB")

    t_table = f"data/mars_temperature_T{run_one_t}p0K.csv"
    case_lines: list[str] = [
        f"io.outdir={outdir}",
        f"dynamics.rng_seed={seed_value}",
        f"radiation.TM_K={run_one_t}",
        f"supply.mixing.epsilon_mix={run_one_eps}",
        f"optical_depth.tau0_target={run_one_tau}",
        f"dynamics.i0={run_one_i0}",
    ]
    if run_one_mu:
        case_lines.append(f"supply.const.mu_orbit10pct={run_one_mu}")
    if cool_mode.lower() != "hyodo":
        case_lines.append(f"radiation.mars_temperature_driver.table.path={t_table}")
    if cool_to_k:
        case_lines.append(f"numerics.t_end_until_temperature_K={cool_to_k}")
        if cool_margin_years:
            case_lines.append(
                f"numerics.t_end_temperature_margin_years={cool_margin_years}"
            )
        if cool_search_years:
            case_lines.append(
                f"numerics.t_end_temperature_search_years={cool_search_years}"
            )
    if substep_fast_blowout and substep_fast_blowout != "0":
        case_lines.append("io.substep_fast_blowout=true")
        if substep_max_ratio:
            case_lines.append(f"io.substep_max_ratio={substep_max_ratio}")
    if stream_mem_gb:
        case_lines.append(f"io.streaming.memory_limit_gb={stream_mem_gb}")

    Path(case_overrides_file).write_text("\n".join(case_lines) + "\n", encoding="utf-8")

    override_builder = _env("OVERRIDE_BUILDER") or str(
        repo_root / "scripts/runsets/common/build_overrides.py"
    )
    merge_cmd = [
        *python_cmd,
        override_builder,
        "--file",
        base_overrides_file,
    ]
    if extra_overrides_file:
        merge_cmd += ["--file", extra_overrides_file]
    merge_cmd += ["--file", case_overrides_file]
    merge_result = _run_command(merge_cmd, capture=True, quiet=quiet_mode)
    if merge_result.returncode != 0:
        log_error("failed to merge overrides")
        if merge_result.stderr:
            log_error(merge_result.stderr.strip())
        return merge_result.returncode or 1
    Path(merged_overrides_file).write_text(merge_result.stdout, encoding="utf-8")

    if args.dry_run:
        log_info("dry-run: skipping marsdisk.run execution")
        log_info(f"outdir={outdir}")
        return 0

    run_cmd = [
        *python_cmd,
        "-m",
        "marsdisk.run",
        "--config",
        base_config,
        "--quiet",
        "--overrides-file",
        merged_overrides_file,
    ]
    if _is_true(_env("ENABLE_PROGRESS")):
        run_cmd.append("--progress")

    if debug_mode:
        log_debug(f"PYTHON_CMD={' '.join(python_cmd)}")
        log_debug(f"RUN_CMD={' '.join(run_cmd)}")
        log_debug(f"BASE_CONFIG={base_config}")
        log_debug(f"MERGED_OVERRIDES_FILE={merged_overrides_file}")

    run_result = _run_command(run_cmd, quiet=quiet_mode)
    if run_result.returncode != 0:
        log_warn(f"run command exited with status {run_result.returncode}")

    exit_code = 0

    if _env("PLOT_ENABLE") not in {"0", "false", "False"}:
        plot_hook = repo_root / "scripts/runsets/common/hooks/plot_sweep_run.py"
        plot_result = _run_command(
            python_cmd + [str(plot_hook), "--run-dir", str(outdir)],
            quiet=quiet_mode,
        )
        if plot_result.returncode != 0:
            log_warn(f"quicklook failed [rc={plot_result.returncode}]")

    hooks_enable = _env("HOOKS_ENABLE")
    hooks_strict = _is_true(_env("HOOKS_STRICT"))
    if hooks_enable:
        hooks_list = hooks_enable.replace(",", " ").split()
        hooks_map = {
            "preflight": "preflight_streaming.py",
            "plot": "plot_sweep_run.py",
            "eval": "evaluate_tau_supply.py",
            "archive": "archive_run.py",
        }
        for hook in hooks_list:
            script_name = hooks_map.get(hook.lower())
            if not script_name:
                log_warn(f"unknown hook: {hook}")
                continue
            hook_path = repo_root / "scripts/runsets/common/hooks" / script_name
            hook_result = _run_command(
                python_cmd + [str(hook_path), "--run-dir", str(outdir)],
                quiet=quiet_mode,
            )
            if hook_result.returncode != 0:
                log_warn(f"hook {hook} failed [rc={hook_result.returncode}]")
                if hooks_strict:
                    exit_code = hook_result.returncode or 1
                    break

    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("[info] interrupted by user")
        raise SystemExit(130)
