#!/usr/bin/env python3
"""Parameter sweep utility for Mars disk zero-dimensional runs.

This script automates two-dimensional sweeps over selected configuration
parameters and aggregates the resulting mass loss from each simulation.  It
supports three predefined maps described in the task instructions.  Each case
creates a derived YAML configuration, executes ``python -m marsdisk.run`` and
parses the outputs to obtain the cumulative mass loss and effective minimum
grain size.  Results are written to ``results/map{ID}.csv``.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from ruamel.yaml import YAML

try:
    from marsdisk import constants as mars_constants
except Exception:  # pragma: no cover - fallback when package import fails
    class _FallbackConstants:
        R_MARS = 3.3895e6
        M_MARS = 6.4171e23

    mars_constants = _FallbackConstants()  # type: ignore[assignment]


@dataclass(frozen=True)
class ParamSpec:
    """Definition of a sweep parameter axis."""

    key_path: str
    values: List[float]
    csv_name: str
    label: str
    transform: Optional[Callable[[float], Any]] = None

    def apply(self, value: float) -> Any:
        """Return the value written to the YAML configuration."""

        if self.transform is None:
            return value
        return self.transform(value)


@dataclass(frozen=True)
class MapDefinition:
    """Container bundling the parameter axes for a sweep."""

    map_id: int
    param_x: ParamSpec
    param_y: ParamSpec


@dataclass(frozen=True)
class CaseSpec:
    """Runtime information for a single sweep case."""

    order: int
    map_id: int
    case_id: str
    x_value: float
    y_value: float
    param_x: ParamSpec
    param_y: ParamSpec
    config_path: Path
    outdir: Path


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(description="Run marsdisk 0D sweeps")
    parser.add_argument("--map", type=int, choices=(1, 2, 3), required=True, help="カラーマップID")
    parser.add_argument(
        "--base",
        type=str,
        default="config.base.yaml",
        help="ベースとなるYAML設定ファイル",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="sweeps",
        help="感度掃引の出力ルートディレクトリ",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=4,
        help="並列実行するワーカー数",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def create_map_definition(map_id: int) -> MapDefinition:
    """Return the parameter definition for the requested map."""

    if map_id == 1:
        param_x = ParamSpec(
            key_path="geometry.r",
            values=[3.0, 4.0, 5.0, 6.0],
            csv_name="r_RM",
            label="rRM",
            transform=lambda v: float(v) * mars_constants.R_MARS,
        )
        param_y = ParamSpec(
            key_path="temps.T_M",
            values=[1500.0, 1750.0, 2000.0, 2250.0, 2500.0],
            csv_name="T_M",
            label="TM",
        )
        return MapDefinition(map_id=map_id, param_x=param_x, param_y=param_y)
    if map_id == 2:
        param_x = ParamSpec(
            key_path="supply.const.prod_area_rate_kg_m2_s",
            values=[1e-10, 3e-10, 1e-9, 3e-9, 1e-8],
            csv_name="prod_area_rate",
            label="prodArea",
        )
        param_y = ParamSpec(
            key_path="temps.T_M",
            values=[1500.0, 2000.0, 2500.0],
            csv_name="T_M",
            label="TM",
        )
        return MapDefinition(map_id=map_id, param_x=param_x, param_y=param_y)
    if map_id == 3:
        param_x = ParamSpec(
            key_path="psd.alpha",
            values=[3.0, 3.5, 4.0, 4.5],
            csv_name="alpha",
            label="alpha",
        )
        param_y = ParamSpec(
            key_path="sizes.s_min",
            values=[1e-8, 3e-8, 1e-7, 3e-7, 1e-6],
            csv_name="s_min",
            label="smin",
        )
        return MapDefinition(map_id=map_id, param_x=param_x, param_y=param_y)
    raise ValueError(f"未知のマップIDです: {map_id}")


def format_param_value(value: float) -> str:
    """Generate a filesystem-friendly representation of a parameter value."""

    if isinstance(value, float):
        if math.isfinite(value):
            abs_v = abs(value)
            if abs_v >= 1e-3 and abs_v < 1e3:
                if math.isclose(value, round(value)):
                    return f"{value:.1f}"
                return f"{value:.6g}"
            formatted = f"{value:.3g}"
            return formatted.replace("e+0", "e+").replace("e-0", "e-")
        return "nan"
    return str(value)


def build_case_id(param_x: ParamSpec, x_value: float, param_y: ParamSpec, y_value: float) -> str:
    """Construct a case identifier from parameter names and values."""

    x_str = format_param_value(float(x_value))
    y_str = format_param_value(float(y_value))
    return f"{param_x.label}_{x_str}__{param_y.label}_{y_str}"


def set_nested(data: Dict[str, Any], path: str, value: Any) -> None:
    """Assign a value to a nested dictionary path."""

    keys = path.split(".")
    cursor: Dict[str, Any] = data
    for key in keys[:-1]:
        if key not in cursor or cursor[key] is None:
            cursor[key] = {}
        cursor = cursor[key]
    cursor[keys[-1]] = value


def get_nested(data: Dict[str, Any], path: str) -> Any:
    """Retrieve a nested value from a dictionary."""

    keys = path.split(".")
    cursor: Any = data
    for key in keys:
        if cursor is None:
            return None
        if isinstance(cursor, dict) and key in cursor:
            cursor = cursor[key]
        else:
            return None
    return cursor


def ensure_directory(path: Path) -> None:
    """Create a directory if it does not exist."""

    path.mkdir(parents=True, exist_ok=True)


def load_base_config(base_path: Path) -> Dict[str, Any]:
    """Load the base YAML configuration using ruamel.yaml."""

    yaml = YAML(typ="safe")
    with base_path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if data is None:
        raise ValueError(f"YAML設定が空です: {base_path}")
    if not isinstance(data, dict):
        raise TypeError("YAML設定はマッピング形式である必要があります")
    return data


def write_config(config: Dict[str, Any], path: Path) -> None:
    """Serialize a configuration dictionary to YAML."""

    yaml = YAML()
    yaml.default_flow_style = False
    with path.open("w", encoding="utf-8") as fh:
        yaml.dump(config, fh)


def build_cases(map_def: MapDefinition, out_root: Path) -> List[CaseSpec]:
    """Prepare the full list of cases for the sweep."""

    cases: List[CaseSpec] = []
    order = 0
    map_dir = out_root / f"map{map_def.map_id}"
    for x in map_def.param_x.values:
        for y in map_def.param_y.values:
            case_id = build_case_id(map_def.param_x, x, map_def.param_y, y)
            case_dir = map_dir / case_id
            config_path = case_dir / "config.yaml"
            outdir = case_dir / "out"
            cases.append(
                CaseSpec(
                    order=order,
                    map_id=map_def.map_id,
                    case_id=case_id,
                    x_value=float(x),
                    y_value=float(y),
                    param_x=map_def.param_x,
                    param_y=map_def.param_y,
                    config_path=config_path,
                    outdir=outdir,
                )
            )
            order += 1
    return cases


def compute_area_from_config(config: Dict[str, Any]) -> Optional[float]:
    """Compute the surface area associated with a configuration."""

    geometry = config.get("geometry", {}) if isinstance(config, dict) else {}
    disk = config.get("disk") if isinstance(config, dict) else None

    if isinstance(disk, dict):
        disk_geom = disk.get("geometry")
        if isinstance(disk_geom, dict):
            r_in_rm = disk_geom.get("r_in_RM")
            r_out_rm = disk_geom.get("r_out_RM")
            if r_in_rm is not None and r_out_rm is not None:
                r_in = float(r_in_rm) * mars_constants.R_MARS
                r_out = float(r_out_rm) * mars_constants.R_MARS
                return math.pi * (r_out ** 2 - r_in ** 2)
    if isinstance(geometry, dict):
        r = geometry.get("r")
        if r is not None:
            return math.pi * float(r) ** 2
        r_in = geometry.get("r_in")
        r_out = geometry.get("r_out")
        if r_in is not None and r_out is not None:
            return math.pi * (float(r_out) ** 2 - float(r_in) ** 2)
    return None


def search_numeric_value(data: Any, key_pred: Callable[[str], bool]) -> Optional[float]:
    """Recursively search for a numeric value whose key matches a predicate."""

    if isinstance(data, dict):
        for key, value in data.items():
            if key_pred(str(key)) and isinstance(value, (int, float)):
                return float(value)
            result = search_numeric_value(value, key_pred)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = search_numeric_value(item, key_pred)
            if result is not None:
                return result
    return None


def parse_summary(summary_path: Path) -> Tuple[Optional[float], Optional[float], Optional[Dict[str, Any]]]:
    """Load the summary JSON and extract loss/s_min related values."""

    if not summary_path.exists():
        return None, None, None
    with summary_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    loss_value = search_numeric_value(data, lambda k: "loss" in k.lower())
    smin_value = search_numeric_value(
        data,
        lambda k: "s_min" in k.lower() or "smin" in k.lower(),
    )
    return loss_value, smin_value, data


def extract_smin_from_series(df: pd.DataFrame) -> Optional[float]:
    """Pick an effective s_min column from a time series DataFrame."""

    priority: List[Tuple[int, str]] = []
    for col in df.columns:
        name = col.lower()
        if "s_min_eff" in name:
            priority.append((0, col))
        elif "smin_eff" in name:
            priority.append((0, col))
        elif "s_min" in name or "smin" in name:
            priority.append((1, col))
    if not priority:
        return None
    priority.sort()
    chosen = priority[0][1]
    series = df[chosen]
    if series.empty:
        return None
    value = series.iloc[-1]
    if pd.isna(value):
        return None
    return float(value)


def _build_time_array(df: pd.DataFrame) -> Optional[np.ndarray]:
    if "time" in df.columns:
        return df["time"].to_numpy(dtype=float)
    if "t" in df.columns:
        return df["t"].to_numpy(dtype=float)
    if "dt" in df.columns:
        dt_vals = df["dt"].to_numpy(dtype=float)
        return np.cumsum(dt_vals)
    return None


def integrate_outflux(
    df: pd.DataFrame,
    config: Dict[str, Any],
    case_id: str,
) -> Tuple[float, Optional[str]]:
    """Integrate an outflux-like column to obtain total mass loss."""

    if df.empty:
        return math.nan, "series empty"
    times = _build_time_array(df)
    if times is None:
        return math.nan, "time column not found"
    outflux_cols = [col for col in df.columns if "outflux" in col.lower()]
    flux_values: Optional[np.ndarray] = None
    note: Optional[str] = None
    for col in outflux_cols:
        candidate = df[col].to_numpy(dtype=float)
        if col.lower().endswith("surface"):
            area = compute_area_from_config(config)
            if area is None:
                note = "surface outflux requires area"
                candidate = None
            else:
                candidate = (candidate * area) / mars_constants.M_MARS
        if candidate is not None:
            flux_values = candidate
            break
    else:
        m_out_cols = [col for col in df.columns if "m_out_dot" in col.lower()]
        if m_out_cols:
            col = m_out_cols[0]
            flux_values = df[col].to_numpy(dtype=float)
        else:
            print(f"[{case_id}] 利用可能な列: {list(df.columns)}")
            return math.nan, "outflux column missing"
    if flux_values is None:
        return math.nan, note
    if len(times) != len(flux_values):
        return math.nan, "time/flux length mismatch"
    if len(times) == 1:
        if "dt" in df.columns:
            total = float(flux_values[0] * float(df["dt"].iloc[0]))
            return total, note
        return math.nan, "insufficient samples"
    total = float(np.trapz(flux_values, times))
    return total, note


def run_case(
    case: CaseSpec,
    base_config: Dict[str, Any],
    root_dir: Path,
    python_executable: str,
) -> Dict[str, Any]:
    """Execute a single sweep case and collect results."""

    record: Dict[str, Any] = {
        "order": case.order,
        "map_id": case.map_id,
        "case_id": case.case_id,
        "param_x_name": case.param_x.csv_name,
        "param_x_value": case.x_value,
        "param_y_name": case.param_y.csv_name,
        "param_y_value": case.y_value,
        "total_mass_lost_Mmars": math.nan,
        "s_min_effective": math.nan,
        "outdir": str(case.outdir),
        "case_status": "pending",
        "message": "",
    }
    config_data = copy.deepcopy(base_config)
    try:
        set_nested(config_data, case.param_x.key_path, case.param_x.apply(case.x_value))
        set_nested(config_data, case.param_y.key_path, case.param_y.apply(case.y_value))
        set_nested(config_data, "io.outdir", str(case.outdir))

        ensure_directory(case.config_path.parent)
        ensure_directory(case.outdir)
        write_config(config_data, case.config_path)

        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        if existing:
            env["PYTHONPATH"] = f".{os.pathsep}{existing}"
        else:
            env["PYTHONPATH"] = "."
        cmd = [python_executable, "-m", "marsdisk.run", "--config", str(case.config_path)]
        proc = subprocess.run(
            cmd,
            cwd=root_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            record["case_status"] = "failed"
            stderr = (proc.stderr or "").strip().splitlines()
            short_err = stderr[-1] if stderr else f"returncode {proc.returncode}"
            record["message"] = short_err
            print(f"[失敗] {case.case_id}: {short_err}")
            return record

        summary_path = case.outdir / "summary.json"
        series_path = case.outdir / "series" / "run.parquet"
        loss_value, smin_from_summary, _ = parse_summary(summary_path)
        smin_value = None
        series_df: Optional[pd.DataFrame] = None
        if series_path.exists():
            series_df = pd.read_parquet(series_path)
            smin_from_series = extract_smin_from_series(series_df)
            if smin_from_series is not None:
                smin_value = smin_from_series
        if smin_value is None and smin_from_summary is not None:
            smin_value = smin_from_summary
        if smin_value is None:
            smin_value = get_nested(config_data, "sizes.s_min")
            if smin_value is not None:
                smin_value = float(smin_value)

        total_mass = None
        note: Optional[str] = None
        if loss_value is not None:
            total_mass = loss_value
        else:
            if series_df is None:
                if not series_path.exists():
                    record["case_status"] = "failed"
                    record["message"] = "series missing"
                    print(f"[失敗] {case.case_id}: series missing")
                    return record
                series_df = pd.read_parquet(series_path)
            total, note = integrate_outflux(series_df, config_data, case.case_id)
            total_mass = total
        if total_mass is None:
            total_mass = math.nan
        record["total_mass_lost_Mmars"] = float(total_mass)
        record["s_min_effective"] = float(smin_value) if smin_value is not None else math.nan
        record["case_status"] = "success"
        if note:
            record["message"] = note
        return record
    except Exception as exc:
        record["case_status"] = "failed"
        record["message"] = str(exc)
        print(f"[失敗] {case.case_id}: {exc}")
        return record


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    script_path = Path(__file__).resolve()
    root_dir = script_path.parent.parent
    base_path = Path(args.base)
    if not base_path.is_absolute():
        base_path = root_dir / base_path
    if not base_path.exists():
        raise FileNotFoundError(f"ベース設定ファイルが見つかりません: {base_path}")

    map_def = create_map_definition(args.map)
    out_root = Path(args.outdir)
    if not out_root.is_absolute():
        out_root = root_dir / out_root
    ensure_directory(out_root / f"map{map_def.map_id}")

    base_config = load_base_config(base_path)
    cases = build_cases(map_def, out_root)
    total_cases = len(cases)
    print(f"マップ{map_def.map_id}: 合計{total_cases}ケースを実行します")

    python_executable = sys.executable or "python"
    results: List[Dict[str, Any]] = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        future_map = {
            executor.submit(run_case, case, base_config, root_dir, python_executable): case
            for case in cases
        }
        for future in concurrent.futures.as_completed(future_map):
            res = future.result()
            results.append(res)
            completed += 1
            status = res["case_status"]
            if status == "success":
                mass = res["total_mass_lost_Mmars"]
                print(
                    f"[{completed}/{total_cases}] 成功: {res['case_id']} (損失={mass:.3e} M_Mars)"
                )
            else:
                reason = res.get("message", "")
                print(f"[{completed}/{total_cases}] 失敗: {res['case_id']} ({reason})")

    results.sort(key=lambda rec: rec.get("order", 0))
    for rec in results:
        rec.pop("order", None)

    results_dir = root_dir / "results"
    ensure_directory(results_dir)
    output_csv = results_dir / f"map{map_def.map_id}.csv"
    df = pd.DataFrame(results)
    df.to_csv(output_csv, index=False)
    print(f"結果を {output_csv} に保存しました")


if __name__ == "__main__":
    main()
