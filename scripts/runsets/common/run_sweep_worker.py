#!/usr/bin/env python3
"""Run sweep cases in-process for persistent worker mode."""
from __future__ import annotations

import argparse
import os
import secrets
import shlex
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Iterable, Iterator


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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp932")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")


def _iter_pairs_from_text(text: str) -> Iterator[tuple[str, str]]:
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        yield key, value


def _iter_pairs_from_lines(lines: Iterable[str]) -> Iterator[tuple[str, str]]:
    for line in lines:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        yield key, value


def _merge_pairs(pairs: Iterable[tuple[str, str]]) -> tuple[list[str], dict[str, str]]:
    order: list[str] = []
    values: dict[str, str] = {}
    for key, value in pairs:
        if key in values:
            try:
                order.remove(key)
            except ValueError:
                pass
        order.append(key)
        values[key] = value
    return order, values


def _write_overrides(order: list[str], values: dict[str, str], path: Path) -> None:
    lines = [f"{key}={values[key]}" for key in order]
    text = "\n".join(lines)
    if text:
        text += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _load_sweep_list(path: Path) -> list[tuple[str, str, str]]:
    text = _read_text(path)
    cases: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        tokens = raw.split()
        if len(tokens) < 3:
            continue
        cases.append((tokens[0], tokens[1], tokens[2]))
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sweep-list", default=None)
    ap.add_argument("--part-index", default=None)
    ap.add_argument("--part-count", default=None)
    ap.add_argument("--base-config", default=None)
    ap.add_argument("--python-exe", default=None)
    ap.add_argument("--python-args", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

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

    sweep_list_arg = args.sweep_list or _env("SWEEP_LIST_FILE")
    if not sweep_list_arg:
        log_error("SWEEP_LIST_FILE is required for run_sweep_worker.py")
        return 1
    sweep_list_path = Path(sweep_list_arg)
    if not sweep_list_path.exists():
        log_error(f"sweep list not found: {sweep_list_path}")
        return 1

    part_index = _parse_int(args.part_index or _env("SWEEP_PART_INDEX"), 1)
    part_count = _parse_int(args.part_count or _env("SWEEP_PART_COUNT"), 1)
    if part_count < 1:
        part_count = 1
    if part_index < 1 or part_index > part_count:
        log_warn(f"invalid part index {part_index}; defaulting to 1")
        part_index = 1

    run_ts = _env("RUN_TS")
    if not run_ts:
        timestamp_py = repo_root / "scripts/runsets/common/timestamp.py"
        result = _run_command(python_cmd + [str(timestamp_py)], capture=True, quiet=quiet_mode)
        run_ts = (result.stdout or "").strip()
    if not run_ts:
        log_error("RUN_TS is required for run_sweep_worker.py")
        return 1
    run_ts_sanitized = _sanitize_run_ts(run_ts)
    if run_ts_sanitized != run_ts:
        log_warn(f'RUN_TS sanitized: "{run_ts}" -> "{run_ts_sanitized}"')
    run_ts = run_ts_sanitized

    git_sha = _env("GIT_SHA")
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

    batch_seed = _env("BATCH_SEED")
    if not batch_seed:
        next_seed_py = repo_root / "scripts/runsets/common/next_seed.py"
        result = _run_command(python_cmd + [str(next_seed_py)], capture=True, quiet=quiet_mode)
        batch_seed = (result.stdout or "").strip()
    if not batch_seed:
        batch_seed = "0"

    sweep_tag = _env("SWEEP_TAG") or "temp_supply_sweep"
    sweep_tag_sanitized = _sanitize_sweep_tag(sweep_tag)
    if sweep_tag_sanitized != sweep_tag:
        log_warn(f'SWEEP_TAG sanitized: "{sweep_tag}" -> "{sweep_tag_sanitized}"')
    sweep_tag = sweep_tag_sanitized

    base_config = args.base_config or _env("BASE_CONFIG")
    if not base_config:
        base_config = str(repo_root / "configs/sweep_temp_supply/temp_supply_T4000_eps1.yml")

    tmp_root = _env("TMP_ROOT")
    if not tmp_root:
        tmp_root_base = _env("TMP_ROOT_BASE") or _env("TEMP") or _env("TMP") or str(repo_root / "tmp")
        worker_suffix = f"worker{part_index}" if part_count > 1 else "worker1"
        tmp_root = os.path.join(
            tmp_root_base,
            f"marsdisk_tmp_{run_ts}_{batch_seed}_{worker_suffix}",
        )
    Path(tmp_root).mkdir(parents=True, exist_ok=True)

    worker_tag = f"worker{part_index}"
    base_overrides_file = Path(
        _env("BASE_OVERRIDES_FILE")
        or os.path.join(tmp_root, f"marsdisk_overrides_base_{run_ts}_{batch_seed}_{worker_tag}.txt")
    )
    case_overrides_file = Path(
        _env("CASE_OVERRIDES_FILE")
        or os.path.join(tmp_root, f"marsdisk_overrides_case_{run_ts}_{batch_seed}_{worker_tag}.txt")
    )
    merged_overrides_file = Path(
        _env("MERGED_OVERRIDES_FILE")
        or os.path.join(tmp_root, f"marsdisk_overrides_merged_{run_ts}_{batch_seed}_{worker_tag}.txt")
    )

    extra_overrides_file = _env("EXTRA_OVERRIDES_FILE")
    extra_overrides_path = None
    if extra_overrides_file:
        extra_overrides_path = Path(extra_overrides_file)
        if not extra_overrides_path.exists():
            log_warn(f"EXTRA_OVERRIDES_FILE not found: {extra_overrides_file}")
            extra_overrides_path = None

    batch_dir_env = _env("BATCH_DIR")
    if batch_dir_env:
        batch_dir = Path(batch_dir_env)
    else:
        batch_root = _env("BATCH_ROOT") or _env("OUT_ROOT") or "out"
        batch_dir = Path(batch_root) / sweep_tag / f"{run_ts}__{git_sha}__seed{batch_seed}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    write_base_overrides_py = repo_root / "scripts/runsets/common/write_base_overrides.py"
    result = _run_command(
        python_cmd + [str(write_base_overrides_py), "--out", str(base_overrides_file)],
        quiet=quiet_mode,
    )
    if result.returncode != 0 or not base_overrides_file.exists():
        log_error(f"failed to build base overrides: {base_overrides_file}")
        return result.returncode or 1

    base_pairs = list(_iter_pairs_from_text(_read_text(base_overrides_file)))
    extra_pairs: list[tuple[str, str]] = []
    if extra_overrides_path:
        extra_pairs = list(_iter_pairs_from_text(_read_text(extra_overrides_path)))

    cases = _load_sweep_list(sweep_list_path)
    if not cases:
        log_error(f"sweep list empty: {sweep_list_path}")
        return 1

    cool_mode = (_env("COOL_MODE") or "").lower()
    cool_to_k = _env("COOL_TO_K")
    cool_margin_years = _env("COOL_MARGIN_YEARS")
    cool_search_years = _env("COOL_SEARCH_YEARS")
    substep_fast_blowout = _env("SUBSTEP_FAST_BLOWOUT")
    substep_max_ratio = _env("SUBSTEP_MAX_RATIO")
    stream_mem_gb = _env("STREAM_MEM_GB")

    seed_override = _env("SEED_OVERRIDE")

    exit_code = 0
    from marsdisk import run_zero_d

    for idx, (t_val, eps_val, tau_val) in enumerate(cases):
        if part_count > 1 and idx % part_count != (part_index - 1):
            continue

        t_table = f"data/mars_temperature_T{t_val}p0K.csv"
        eps_title = _format_title_token(eps_val)
        tau_title = _format_title_token(tau_val)
        if seed_override:
            seed_value = seed_override
        else:
            seed_value = str(secrets.randbelow(2**31))

        title = f"T{t_val}_eps{eps_title}_tau{tau_title}"
        outdir = (batch_dir / title).resolve()
        (outdir / "series").mkdir(parents=True, exist_ok=True)
        (outdir / "checks").mkdir(parents=True, exist_ok=True)

        log_info(f"case start T={t_val} eps={eps_val} tau={tau_val} -> {outdir}")

        case_lines = [
            f"io.outdir={outdir}",
            f"dynamics.rng_seed={seed_value}",
            f"radiation.TM_K={t_val}",
            f"supply.mixing.epsilon_mix={eps_val}",
            f"optical_depth.tau0_target={tau_val}",
        ]
        if cool_mode != "hyodo":
            case_lines.append(f"radiation.mars_temperature_driver.table.path={t_table}")
        if cool_to_k:
            case_lines.append(f"numerics.t_end_until_temperature_K={cool_to_k}")
            if cool_margin_years:
                case_lines.append(f"numerics.t_end_temperature_margin_years={cool_margin_years}")
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

        case_overrides_file.parent.mkdir(parents=True, exist_ok=True)
        case_overrides_file.write_text("\n".join(case_lines) + "\n", encoding="utf-8")

        case_pairs = list(_iter_pairs_from_lines(case_lines))
        order, values = _merge_pairs([*base_pairs, *extra_pairs, *case_pairs])
        _write_overrides(order, values, merged_overrides_file)

        if args.dry_run:
            log_info("dry-run: skipping marsdisk.run execution")
            continue

        run_args = [
            "--config",
            base_config,
            "--quiet",
            "--overrides-file",
            str(merged_overrides_file),
        ]
        if _is_true(_env("ENABLE_PROGRESS")):
            run_args.append("--progress")

        try:
            run_zero_d.main(run_args)
            rc = 0
        except SystemExit as exc:
            rc = exc.code or 0
        except Exception as exc:
            rc = 1
            log_warn(f"run failed: {exc}")
            if debug_mode:
                traceback.print_exc()

        if rc != 0:
            log_warn(f"run command exited with status {rc}")

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
            if exit_code != 0 and hooks_strict:
                break

    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("[info] interrupted by user")
        raise SystemExit(130)
