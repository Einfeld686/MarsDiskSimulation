"""Batch runner generating parameter sweep maps for the Mars disk model.

This script automates the production of two-dimensional maps such as the
``r_{\rm RM} \times T_M`` grid requested for Map‑1.  For each grid point a
derived YAML configuration is written, ``python -m marsdisk.run`` is executed
and the resulting ``summary.json`` / ``series/run.parquet`` files are parsed to
obtain cumulative mass loss and blow-out diagnostics.  Aggregated results are
stored in ``results/map*.csv`` while per-case outputs are written under the
``--outdir`` root.

Additional validation helpers ensure that the low-temperature blow-out failures
form a contiguous band and that the mass-loss scaling ``M / r^2`` remains nearly
constant across the successful Map‑1 cells.  These checks are persisted in a
``*_validation.json`` file for downstream inspection.
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
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from ruamel.yaml import YAML

try:  # pragma: no cover - fallback when package import fails
    from marsdisk import constants as mars_constants
except Exception:  # pragma: no cover - fallback when package import fails
    class _FallbackConstants:
        R_MARS = 3.3895e6
        M_MARS = 6.4171e23

    mars_constants = _FallbackConstants()  # type: ignore[assignment]


BLOWOUT_STATUS = "blowout"
DEFAULT_TOL_MASS_PER_R2 = 0.10
DEFAULT_BASE_CONFIG = Path("configs/map_sweep_base.yml")


@dataclass(frozen=True)
class ParamSpec:
    """Definition of a sweep parameter axis."""

    key_path: str
    values: List[float]
    csv_name: str
    label: str
    transform: Optional[Callable[[float], Any]] = None
    log_spacing: bool = False

    def apply(self, value: float) -> Any:
        """Return the value written to the YAML configuration."""

        if self.transform is None:
            return value
        return self.transform(value)


@dataclass(frozen=True)
class MapDefinition:
    """Container bundling the parameter axes for a sweep."""

    map_key: str
    output_stub: str
    param_x: ParamSpec
    param_y: ParamSpec
    preferred_partition_axis: str = "param_y"


@dataclass(frozen=True)
class VariantSpec:
    """Configuration overrides applied on top of the base map settings."""

    label: str
    overrides: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass(frozen=True)
class CaseSpec:
    """Runtime information for a single sweep case."""

    order: int
    map_key: str
    base_case_id: str
    case_id: str
    x_value: float
    y_value: float
    param_x: ParamSpec
    param_y: ParamSpec
    variant: VariantSpec
    config_path: Path
    outdir: Path
    partition_index: int = 1
    partition_count: int = 1


def build_variant_grid(
    *,
    s_min_values: Optional[List[Tuple[str, float, float]]] = None,
    chi_values: Optional[List[Tuple[str, float]]] = None,
    sink_values: Optional[List[Tuple[str, Dict[str, Any], str]]] = None,
) -> List[VariantSpec]:
    """Return the set of parameter variant combinations for Map-1 sweeps."""

    if s_min_values is None:
        s_min_values = [
            ("smin_0p1um", 1.0e-7, 0.1),
            ("smin_0p5um", 5.0e-7, 0.5),
            ("smin_1um", 1.0e-6, 1.0),
            ("smin_5um", 5.0e-6, 5.0),
        ]
    if chi_values is None:
        chi_values = [
            ("chi0p5", 0.5),
            ("chi1p0", 1.0),
            ("chi2p0", 2.0),
        ]
    if sink_values is None:
        sink_values = [
            ("sink_none", {"sinks.mode": "none", "sinks.enable_sublimation": False}, "none"),
            (
                "sink_sublimation",
                {"sinks.mode": "sublimation", "sinks.enable_sublimation": True},
                "sublimation",
            ),
        ]

    variants: List[VariantSpec] = []
    for s_label, s_value_m, s_value_um in s_min_values:
        for chi_label, chi_value in chi_values:
            for sink_label, sink_override, sink_name in sink_values:
                label = "__".join([s_label, chi_label, sink_label])
                overrides: Dict[str, Any] = {
                    "sizes.s_min": s_value_m,
                    "chi_blow": chi_value,
                }
                overrides.update(sink_override)
                metadata = {
                    "variant_label": label,
                    "variant_s_min_m": s_value_m,
                    "variant_s_min_um": s_value_um,
                    "variant_chi_blow": chi_value,
                    "variant_sink_mode": sink_name,
                }
                variants.append(
                    VariantSpec(
                        label=label,
                        overrides=overrides,
                        metadata=metadata,
                    )
                )
    return variants


VARIANT_GRID: List[VariantSpec] = build_variant_grid()
DEFAULT_VARIANT = VariantSpec(label="default", overrides={}, metadata={"variant_label": "default"})


def build_variant_grid_from_spec(spec: str) -> List[VariantSpec]:
    """Parse a variant specification string and return the corresponding grid."""

    if spec is None:
        raise ValueError("variants specification must be a non-empty string")
    tokens = {}
    for raw_part in spec.split(";"):
        part = raw_part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"無効なバリアント指定です: {raw_part}")
        key, value_str = part.split("=", 1)
        values = [v.strip() for v in value_str.split("|") if v.strip()]
        if not values:
            raise ValueError(f"バリアント値が空です: {part}")
        tokens[key.strip().lower()] = values

    required_keys = {"chi_blow", "sinks", "s_min"}
    missing = sorted(required_keys - tokens.keys())
    if missing:
        raise ValueError(f"variants 指定に必要なキーが不足しています: {', '.join(missing)}")

    def _smin_entry(value_str: str) -> Tuple[str, float, float]:
        try:
            value_m = float(value_str)
        except ValueError as exc:
            raise ValueError(f"s_min の値が不正です: {value_str}") from exc
        if value_m <= 0.0:
            raise ValueError("s_min は正である必要があります")
        micron = value_m * 1.0e6
        if math.isfinite(micron):
            if math.isclose(micron, round(micron)):
                micron_label = f"{int(round(micron))}"
            else:
                micron_label = f"{micron:.3g}"
            label = f"smin_{micron_label}um"
        else:
            label = f"smin_{value_m:.3g}m"
        return label, value_m, micron

    def _chi_entry(value_str: str) -> Tuple[str, float]:
        try:
            value = float(value_str)
        except ValueError as exc:
            raise ValueError(f"chi_blow の値が不正です: {value_str}") from exc
        if value <= 0.0:
            raise ValueError("chi_blow は正である必要があります")
        label = f"chi{value:.1f}".replace(".", "p")
        return label, value

    sink_aliases: Dict[str, Tuple[str, Dict[str, Any], str]] = {
        "none": ("sink_none", {"sinks.mode": "none", "sinks.enable_sublimation": False}, "none"),
        "sublimation": (
            "sink_sublimation",
            {"sinks.mode": "sublimation", "sinks.enable_sublimation": True},
            "sublimation",
        ),
    }

    s_min_values = [_smin_entry(val) for val in tokens["s_min"]]
    chi_values = [_chi_entry(val) for val in tokens["chi_blow"]]
    sink_values: List[Tuple[str, Dict[str, Any], str]] = []
    for sink_str in tokens["sinks"]:
        key = sink_str.lower()
        if key not in sink_aliases:
            raise ValueError(f"未知の sink モードです: {sink_str}")
        sink_values.append(sink_aliases[key])

    return build_variant_grid(
        s_min_values=s_min_values,
        chi_values=chi_values,
        sink_values=sink_values,
    )


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(description="Run marsdisk 0D sweeps")
    parser.add_argument(
        "--map",
        type=str,
        required=True,
        help="マップID (例: 1, 1b, 2, 3)",
    )
    parser.add_argument(
        "--base",
        type=str,
        default=str(DEFAULT_BASE_CONFIG),
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
    parser.add_argument(
        "--num-parts",
        type=int,
        default=1,
        help="Map-3 の s_min 軸を何分割するか (デフォルト: 1)",
    )
    parser.add_argument(
        "--part-index",
        type=int,
        default=1,
        help="実行する分割番号 (1 始まり)",
    )
    parser.add_argument(
        "--rRM_min",
        type=float,
        default=None,
        help="[旧形式] Map-1 の r/R_M 最小値を上書きします",
    )
    parser.add_argument(
        "--rRM_max",
        type=float,
        default=None,
        help="[旧形式] Map-1 の r/R_M 最大値を上書きします",
    )
    parser.add_argument(
        "--rRM_step",
        type=float,
        default=None,
        help="[旧形式] Map-1 の r/R_M ステップ幅を上書きします",
    )
    parser.add_argument(
        "--rmin_rm",
        type=float,
        default=None,
        help="Map-1 の r/R_M 最小値 (例: 1.0)",
    )
    parser.add_argument(
        "--rmax_rm",
        type=float,
        default=None,
        help="Map-1 の r/R_M 最大値 (例: 3.0)",
    )
    parser.add_argument(
        "--rstep_rm",
        type=float,
        default=None,
        help="Map-1 の r/R_M ステップ幅 (例: 0.2)",
    )
    parser.add_argument(
        "--rRM",
        nargs=3,
        type=float,
        metavar=("MIN", "MAX", "N"),
        default=None,
        help="Map-1 の r/R_M 範囲と分割数をまとめて指定します (min max count)",
    )
    parser.add_argument(
        "--TM_min",
        type=float,
        default=None,
        help="[旧形式] Map-1 の T_M 最小値 (K) を上書きします",
    )
    parser.add_argument(
        "--TM_max",
        type=float,
        default=None,
        help="[旧形式] Map-1 の T_M 最大値 (K) を上書きします",
    )
    parser.add_argument(
        "--TM_step",
        type=float,
        default=None,
        help="[旧形式] Map-1 の T_M ステップ幅 (K) を上書きします",
    )
    parser.add_argument(
        "--tmin_k",
        type=float,
        default=None,
        help="Map-1 の T_M 最小値 [K]",
    )
    parser.add_argument(
        "--tmax_k",
        type=float,
        default=None,
        help="Map-1 の T_M 最大値 [K]",
    )
    parser.add_argument(
        "--tstep_k",
        type=float,
        default=None,
        help="Map-1 の T_M ステップ幅 [K]",
    )
    parser.add_argument(
        "--TM",
        nargs=3,
        type=float,
        metavar=("MIN_K", "MAX_K", "N"),
        default=None,
        help="Map-1 の T_M グリッドをまとめて指定します (min max count)",
    )
    parser.add_argument(
        "--qpr_table",
        type=str,
        default=None,
        help="⟨Q_pr⟩ テーブルへのパス (設定時は全ケースに適用)",
    )
    parser.add_argument(
        "--metric",
        type=str,
        default="beta_ratio",
        help="主要なヒートマップ指標列名 (例: beta_ratio)",
    )
    parser.add_argument(
        "--also-metric",
        dest="also_metrics",
        action="append",
        default=None,
        help="追加で算出してCSVへ含める指標列名 (複数指定可)",
    )
    parser.add_argument(
        "--variants",
        type=str,
        default=None,
        help=(
            "Map-1 用のバリアント組み合わせを指定します "
            "(例: 'chi_blow=0.5|1.0|2.0;sinks=none|sublimation;s_min=1e-6|1e-5')"
        ),
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _float_grid(start: float, stop: float, step: float) -> List[float]:
    if step <= 0.0:
        raise ValueError("step must be positive")
    values: List[float] = []
    current = float(start)
    tol = abs(step) * 1e-6 + 1e-12
    max_iter = 10000
    while current <= stop + tol and len(values) < max_iter:
        values.append(float(np.round(current, 10)))
        current += step
    if not values or abs(values[-1] - stop) > tol:
        values.append(float(np.round(stop, 10)))
    # ensure strictly ascending and clipped to stop
    cleaned = []
    for v in values:
        if cleaned and v <= cleaned[-1] + tol:
            continue
        if v > stop + tol:
            continue
        cleaned.append(v)
    if not cleaned:
        cleaned = [float(np.round(start, 10)), float(np.round(stop, 10))]
    if cleaned[-1] < stop - tol:
        cleaned.append(float(np.round(stop, 10)))
    return cleaned


def _normalise_map_key(map_arg: str) -> str:
    key = map_arg.strip().lower()
    if key in {"1", "map1"}:
        return "1"
    if key in {"1b", "map1b"}:
        return "1b"
    if key in {"2", "map2"}:
        return "2"
    if key in {"3", "map3"}:
        return "3"
    raise ValueError(f"未知のマップIDです: {map_arg}")


def create_map_definition(
    map_arg: str,
    overrides: Optional[Dict[str, float]] = None,
) -> MapDefinition:
    """Return the parameter definition for the requested map."""

    overrides = overrides or {}
    map_key = _normalise_map_key(map_arg)
    if map_key == "1":
        r_override = (
            overrides.get("rRM_min"),
            overrides.get("rRM_max"),
            overrides.get("rRM_step"),
        )
        t_override = (
            overrides.get("TM_min"),
            overrides.get("TM_max"),
            overrides.get("TM_step"),
        )
        if any(value is not None for value in r_override):
            if not all(value is not None for value in r_override):
                raise ValueError("rRM_min, rRM_max, rRM_step を全て指定してください")
            r_min, r_max, r_step = (float(v) for v in r_override)  # type: ignore[misc]
            if r_step <= 0.0:
                raise ValueError("rRM_step は正である必要があります")
            r_values = _float_grid(r_min, r_max, r_step)
        else:
            r_values = _float_grid(1.0, 3.0, 0.2)
        if any(value is not None for value in t_override):
            if not all(value is not None for value in t_override):
                raise ValueError("TM_min, TM_max, TM_step を全て指定してください")
            t_min, t_max, t_step = (float(v) for v in t_override)  # type: ignore[misc]
            if t_step <= 0.0:
                raise ValueError("TM_step は正である必要があります")
            T_values = _float_grid(t_min, t_max, t_step)
        else:
            T_values = _float_grid(2000.0, 6000.0, 300.0)
        param_x = ParamSpec(
            key_path="geometry.r",
            values=r_values,
            csv_name="r_RM",
            label="rRM",
            transform=lambda v: float(v) * mars_constants.R_MARS,
        )
        param_y = ParamSpec(
            key_path="temps.T_M",
            values=T_values,
            csv_name="T_M [K]",
            label="TM",
        )
        return MapDefinition(map_key=map_key, output_stub="map1", param_x=param_x, param_y=param_y)
    if map_key == "1b":
        r_values = _float_grid(5.0, 7.0, 0.1)
        T_values = _float_grid(1000.0, 6000.0, 50.0)
        param_x = ParamSpec(
            key_path="geometry.r",
            values=r_values,
            csv_name="r_RM",
            label="rRM",
            transform=lambda v: float(v) * mars_constants.R_MARS,
        )
        param_y = ParamSpec(
            key_path="temps.T_M",
            values=T_values,
            csv_name="T_M [K]",
            label="TM",
        )
        return MapDefinition(map_key=map_key, output_stub="map1b", param_x=param_x, param_y=param_y)
    if map_key == "2":
        param_x = ParamSpec(
            key_path="supply.const.prod_area_rate_kg_m2_s",
            values=[1e-10, 3e-10, 1e-9, 3e-9, 1e-8],
            csv_name="prod_area",
            label="prodArea",
        )
        param_y = ParamSpec(
            key_path="temps.T_M",
            values=[1500.0, 2000.0, 2500.0],
            csv_name="T_M",
            label="TM",
        )
        return MapDefinition(map_key=map_key, output_stub="map2", param_x=param_x, param_y=param_y)
    if map_key == "3":
        alpha_values = _float_grid(3.0, 5.0, 0.1)
        s_values = list(np.logspace(-10.0, -6.0, 1000))
        param_x = ParamSpec(
            key_path="psd.alpha",
            values=alpha_values,
            csv_name="alpha",
            label="alpha",
        )
        param_y = ParamSpec(
            key_path="sizes.s_min",
            values=s_values,
            csv_name="s_min",
            label="smin",
            log_spacing=True,
        )
        return MapDefinition(
            map_key=map_key,
            output_stub="map3",
            param_x=param_x,
            param_y=param_y,
            preferred_partition_axis="param_y",
        )
    raise ValueError(f"未知のマップIDです: {map_arg}")


def format_param_value(value: float) -> str:
    """Generate a filesystem-friendly representation of a parameter value."""

    if isinstance(value, float):
        if math.isfinite(value):
            abs_v = abs(value)
            if 1e-3 <= abs_v < 1e3:
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


def partition_param_values(param: ParamSpec, num_parts: int) -> List[np.ndarray]:
    """Return indices partitioning parameter values into ``num_parts`` segments."""

    values = np.asarray(param.values, dtype=float)
    if values.ndim != 1:
        raise ValueError("parameter values must be one-dimensional")
    total = values.size
    indices = np.arange(total, dtype=int)
    if num_parts <= 1 or total == 0:
        return [indices]
    if num_parts > total:
        num_parts = total

    # ``np.array_split`` provides nearly equal sized contiguous chunks.  For the
    # logarithmically-spaced ``s_min`` axis this corresponds to an equal division
    # in log-space because ``values`` are already sorted in ascending order.
    partitions = [np.array(chunk, dtype=int) for chunk in np.array_split(indices, num_parts)]
    return partitions


COMPLETION_FLAG_NAME = "case_completed.json"


def completion_flag_path(case: CaseSpec) -> Path:
    """Return the path to the completion flag for a case."""

    return case.outdir / COMPLETION_FLAG_NAME


def mark_case_complete(case: CaseSpec, summary_path: Path, series_path: Path) -> None:
    """Persist a completion marker allowing interrupted sweeps to resume."""

    ensure_directory(case.outdir)
    metadata = {
        "case_id": case.case_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": str(summary_path),
        "series": str(series_path),
        "partition_index": case.partition_index,
        "partition_count": case.partition_count,
    }
    flag_path = completion_flag_path(case)
    with flag_path.open("w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2, sort_keys=True)


def case_is_completed(case: CaseSpec) -> bool:
    """Return ``True`` if the completion flag and summary file are present."""

    flag_path = completion_flag_path(case)
    summary_path = case.outdir / "summary.json"
    return flag_path.exists() and summary_path.exists()


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


def build_cases(
    map_def: MapDefinition,
    out_root: Path,
    y_index_filter: Optional[Iterable[int]] = None,
    *,
    partition_index: int = 1,
    partition_count: int = 1,
    variants: Optional[List[VariantSpec]] = None,
) -> List[CaseSpec]:
    """Prepare the full list of cases for the sweep."""

    cases: List[CaseSpec] = []
    order = 0
    map_dir = out_root / map_def.output_stub
    allowed_y = set(int(idx) for idx in y_index_filter) if y_index_filter is not None else None
    if variants is not None:
        variant_list = variants
    else:
        variant_list = VARIANT_GRID if map_def.map_key == "1" else [DEFAULT_VARIANT]
    for variant in variant_list:
        variant_dir = map_dir / variant.label if variant.label != "default" else map_dir
        for x in map_def.param_x.values:
            for y_idx, y in enumerate(map_def.param_y.values):
                if allowed_y is not None and y_idx not in allowed_y:
                    order += 1
                    continue
                base_case_id = build_case_id(map_def.param_x, x, map_def.param_y, y)
                if variant.label == "default":
                    case_id = base_case_id
                    case_dir = variant_dir / base_case_id
                else:
                    case_id = f"{base_case_id}__{variant.label}"
                    case_dir = variant_dir / base_case_id
                config_path = case_dir / "config.yaml"
                outdir = case_dir / "out"
                cases.append(
                    CaseSpec(
                        order=order,
                        map_key=map_def.map_key,
                        base_case_id=base_case_id,
                        case_id=case_id,
                        x_value=float(x),
                        y_value=float(y),
                        param_x=map_def.param_x,
                        param_y=map_def.param_y,
                        variant=variant,
                        config_path=config_path,
                        outdir=outdir,
                        partition_index=partition_index,
                        partition_count=partition_count,
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
        raw_data = json.load(fh)

    loss_value = search_numeric_value(raw_data, lambda k: "loss" in k.lower())
    smin_value = search_numeric_value(
        raw_data,
        lambda k: "s_min" in k.lower() or "smin" in k.lower(),
    )

    if not isinstance(raw_data, dict):
        return loss_value, smin_value, raw_data

    summary: Dict[str, Any] = dict(raw_data)
    beta_config = summary.get("beta_at_smin_config", summary.get("beta_at_smin"))
    summary["beta_at_smin_config"] = beta_config
    if "beta_at_smin" not in summary and beta_config is not None:
        summary["beta_at_smin"] = beta_config
    summary["beta_at_smin_effective"] = summary.get("beta_at_smin_effective")
    summary["s_min_components"] = summary.get("s_min_components")
    summary["T_M_source"] = summary.get("T_M_source")

    return loss_value, smin_value, summary


def _get_beta_for_checks(summary: Optional[Dict[str, Any]]) -> float:
    """Return the beta value relevant for validation thresholds."""

    if not summary:
        return math.nan
    candidate = summary.get("beta_at_smin_config")
    if candidate is None:
        candidate = summary.get("beta_at_smin")
    return _to_float(candidate)


def extract_smin_from_series(df: pd.DataFrame) -> Optional[float]:
    """Pick an effective s_min column from a time series DataFrame."""

    priority: List[Tuple[int, str]] = []
    for col in df.columns:
        name = col.lower()
        if "s_min_effective" in name or "smin_effective" in name:
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


def _to_float(value: Any) -> float:
    if value is None:
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def validate_map1_results(df: pd.DataFrame, tolerance: float = DEFAULT_TOL_MASS_PER_R2) -> Dict[str, Any]:
    """Validate Map‑1 style results for low-T failures and r^2 scaling."""

    result: Dict[str, Any] = {
        "low_temp_band": {
            "ok": True,
            "reentry_r_values": [],
            "first_row_blowout_r_values": [],
            "beta_violations_r_values": [],
            "checked_r_values": 0,
        },
        "mass_per_r2": {
            "ok": True,
            "max_relative_spread": math.nan,
            "worst_T_M": math.nan,
            "worst_r_RM": math.nan,
            "tolerance": tolerance,
        },
    }

    if df.empty:
        result["low_temp_band"]["ok"] = False
        result["mass_per_r2"]["ok"] = False
        return result

    working = df.copy()
    working["case_status"] = working["case_status"].astype(str).str.lower()
    working["run_status"] = working.get("run_status", "success").astype(str).str.lower()

    # --- Low temperature failure band ---
    reentry: List[float] = []
    first_row_blowout: List[float] = []
    beta_violations: List[float] = []
    r_values = sorted(v for v in working["param_x_value"].dropna().unique())
    for r_val in r_values:
        column = (
            working[
                (working["param_x_value"] == r_val)
                & working["run_status"].isin({"success", "cached"})
            ]
            .sort_values("param_y_value")
        )
        if column.empty:
            continue
        result["low_temp_band"]["checked_r_values"] += 1
        statuses = column["case_status"].tolist()
        if statuses and statuses[0] == BLOWOUT_STATUS:
            first_row_blowout.append(float(r_val))
        seen_success = False
        for status in statuses:
            if status == BLOWOUT_STATUS:
                seen_success = True
            else:
                if seen_success:
                    reentry.append(float(r_val))
                    break
        fails = column[column["case_status"] != BLOWOUT_STATUS]
        if not fails.empty:
            thr_series = fails["beta_threshold"].dropna()
            threshold = float(thr_series.iloc[0]) if not thr_series.empty else 0.5
            betas = fails["beta_at_smin"].dropna()
            if betas.empty or np.any(betas.to_numpy(dtype=float) >= threshold):
                beta_violations.append(float(r_val))

    if reentry or first_row_blowout or beta_violations:
        result["low_temp_band"]["ok"] = False
    result["low_temp_band"]["reentry_r_values"] = reentry
    result["low_temp_band"]["first_row_blowout_r_values"] = first_row_blowout
    result["low_temp_band"]["beta_violations_r_values"] = beta_violations

    # --- Mass-loss scaling across radii ---
    success = working[
        (working["case_status"] == BLOWOUT_STATUS)
        & working["run_status"].isin({"success", "cached"})
        & working["mass_per_r2"].notna()
    ]
    if success.empty:
        result["mass_per_r2"]["ok"] = False
    else:
        max_rel: float = -math.inf
        worst_T: float = math.nan
        worst_r: float = math.nan
        for T_M, group in success.groupby("param_y_value"):
            working_group = group.copy()
            working_group["mass_per_r2"] = pd.to_numeric(
                working_group["mass_per_r2"], errors="coerce"
            )
            working_group = working_group[np.isfinite(working_group["mass_per_r2"])]
            if working_group.shape[0] < 2:
                continue
            mean_val = float(np.nanmean(working_group["mass_per_r2"].to_numpy(dtype=float)))
            if not math.isfinite(mean_val) or mean_val == 0.0:
                continue
            diffs = (working_group["mass_per_r2"] - mean_val).abs()
            rel = float(diffs.max() / abs(mean_val))
            if rel > max_rel:
                max_rel = float(rel)
                worst_T = float(T_M)
                idx = diffs.idxmax()
                worst_r = float(working_group.loc[idx, "param_x_value"])
        if max_rel == -math.inf:
            result["mass_per_r2"]["ok"] = False
        else:
            result["mass_per_r2"]["max_relative_spread"] = max_rel
            result["mass_per_r2"]["worst_T_M"] = worst_T
            result["mass_per_r2"]["worst_r_RM"] = worst_r
            if max_rel > tolerance:
                result["mass_per_r2"]["ok"] = False

    return result


def populate_record_from_outputs(
    record: Dict[str, Any],
    case: CaseSpec,
    config_data: Dict[str, Any],
) -> Optional[str]:
    """Fill bookkeeping fields by reading prior outputs."""

    summary_path = case.outdir / "summary.json"
    series_path = case.outdir / "series" / "run.parquet"
    if not summary_path.exists():
        raise FileNotFoundError(f"summary missing for {case.case_id}")

    loss_value, smin_from_summary, summary_data = parse_summary(summary_path)
    summary_dict = summary_data if isinstance(summary_data, dict) else None
    if summary_dict is not None:
        status = str(summary_dict.get("case_status", "unknown")).lower()
        record["case_status"] = status
        record["beta_at_smin"] = _get_beta_for_checks(summary_dict)
        beta_config_val = summary_dict.get("beta_at_smin_config")
        if beta_config_val is not None:
            record["beta_at_smin_config"] = _to_float(beta_config_val)
        beta_effective_val = summary_dict.get("beta_at_smin_effective")
        if beta_effective_val is not None:
            record["beta_at_smin_effective"] = _to_float(beta_effective_val)
        tm_source = summary_dict.get("T_M_source")
        if tm_source is not None:
            record["T_M_source"] = str(tm_source)
        record["beta_threshold"] = _to_float(summary_dict.get("beta_threshold"))
        record["s_blow_m"] = _to_float(summary_dict.get("s_blow_m"))
        record["rho_used"] = _to_float(summary_dict.get("rho_used"))
        record["Q_pr_used"] = _to_float(summary_dict.get("Q_pr_used"))
        record["Q_pr_blow"] = _to_float(summary_dict.get("Q_pr_blow"))
        record["T_M_used"] = _to_float(summary_dict.get("T_M_used"))
        record["r_RM_used"] = _to_float(summary_dict.get("r_RM_used"))
        record["r_m_used"] = _to_float(summary_dict.get("r_m_used"))
        r_source_summary = summary_dict.get("r_source")
        if r_source_summary is not None:
            record["r_source"] = str(r_source_summary)
        record["s_min_effective"] = _to_float(summary_dict.get("s_min_effective"))
        record["s_min_config"] = _to_float(summary_dict.get("s_min_config"))
        sm_gt = summary_dict.get("s_min_effective_gt_config")
        if isinstance(sm_gt, bool):
            record["s_min_effective_gt_config"] = sm_gt
        table_path_summary = summary_dict.get("qpr_table_path")
        if table_path_summary is not None:
            record["qpr_table_path"] = str(table_path_summary)
        mass_blow_val = _to_float(summary_dict.get("M_out_cum"))
        mass_sink_val = _to_float(summary_dict.get("M_sink_cum"))
        if math.isfinite(mass_blow_val):
            record["mass_lost_by_blowout"] = mass_blow_val
        if math.isfinite(mass_sink_val):
            record["mass_lost_by_sinks"] = mass_sink_val
        if math.isfinite(mass_blow_val) or math.isfinite(mass_sink_val):
            safe_blow = mass_blow_val if math.isfinite(mass_blow_val) else 0.0
            safe_sink = mass_sink_val if math.isfinite(mass_sink_val) else 0.0
            denom = safe_blow + safe_sink
            if denom > 0.0 and math.isfinite(mass_blow_val):
                record["blow_fraction"] = safe_blow / denom
            else:
                record["blow_fraction"] = math.nan
    else:
        record["case_status"] = "unknown"

    smin_value: Optional[float] = None
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
    if smin_value is not None:
        record["s_min_effective"] = _to_float(smin_value)

    total_mass: Optional[float] = None
    note: Optional[str] = None
    if loss_value is not None:
        total_mass = loss_value
    else:
        if series_df is None:
            if not series_path.exists():
                raise FileNotFoundError(f"series missing for {case.case_id}")
            series_df = pd.read_parquet(series_path)
        total_mass, note = integrate_outflux(series_df, config_data, case.case_id)

    if total_mass is None:
        total_mass = math.nan
    record["total_mass_lost_Mmars"] = float(total_mass)
    if (
        case.param_x.csv_name == "r_RM"
        and math.isfinite(total_mass)
        and case.x_value > 0.0
        and str(record.get("case_status", "")).lower() == BLOWOUT_STATUS
    ):
        record["mass_per_r2"] = float(total_mass) / (case.x_value ** 2)

    if not math.isfinite(record.get("r_RM_used", math.nan)):
        record["r_RM_used"] = float(case.x_value)
    if not math.isfinite(record.get("r_m_used", math.nan)):
        try:
            record["r_m_used"] = float(case.param_x.apply(case.x_value))
        except Exception:
            pass
    if not record.get("r_source"):
        record["r_source"] = "geometry.r"

    return note


def run_case(
    case: CaseSpec,
    base_config: Dict[str, Any],
    root_dir: Path,
    python_executable: str,
    qpr_table_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a single sweep case and collect results."""

    record: Dict[str, Any] = {
        "order": case.order,
        "map_id": case.map_key,
        "base_case_id": case.base_case_id,
        "case_id": case.case_id,
        "param_x_name": case.param_x.csv_name,
        "param_x_value": case.x_value,
        "param_y_name": case.param_y.csv_name,
        "param_y_value": case.y_value,
        "partition_index": case.partition_index,
        "partition_count": case.partition_count,
        "total_mass_lost_Mmars": math.nan,
        "mass_lost_by_blowout": math.nan,
        "mass_lost_by_sinks": math.nan,
        "blow_fraction": math.nan,
        "mass_per_r2": math.nan,
        "s_min_effective": math.nan,
        "s_min_config": math.nan,
        "s_min_effective_gt_config": False,
        "beta_at_smin": math.nan,
        "beta_threshold": math.nan,
        "s_blow_m": math.nan,
        "rho_used": math.nan,
        "Q_pr_used": math.nan,
        "T_M_used": math.nan,
        "r_RM_used": math.nan,
        "r_source": None,
        "qpr_table_path": qpr_table_path,
        "outdir": str(case.outdir),
        "run_status": "pending",
        "case_status": "unknown",
        "message": "",
    }
    record.update(case.variant.metadata)
    config_data = copy.deepcopy(base_config)
    try:
        set_nested(config_data, case.param_x.key_path, case.param_x.apply(case.x_value))
        if case.param_x.key_path == "geometry.r":
            set_nested(config_data, "geometry.runtime_orbital_radius_rm", case.x_value)
        set_nested(config_data, case.param_y.key_path, case.param_y.apply(case.y_value))
        for path, value in case.variant.overrides.items():
            set_nested(config_data, path, value)
        if qpr_table_path:
            set_nested(config_data, "radiation.qpr_table_path", qpr_table_path)
        set_nested(config_data, "io.outdir", str(case.outdir))

        ensure_directory(case.config_path.parent)
        ensure_directory(case.outdir)
        if case_is_completed(case):
            try:
                note = populate_record_from_outputs(record, case, config_data)
                record["run_status"] = "cached"
                if note:
                    record["message"] = note
                else:
                    record.setdefault("message", "完了済み")
                return record
            except Exception as exc:
                flag_path = completion_flag_path(case)
                if flag_path.exists():
                    try:
                        flag_path.unlink()
                    except OSError:
                        pass
                print(f"[再実行] {case.case_id}: 既存出力の読み込みに失敗 ({exc})")

        write_config(config_data, case.config_path)

        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = f".{os.pathsep}{existing}" if existing else "."
        cmd = [python_executable, "-m", "marsdisk.run", "--config", str(case.config_path)]
        proc = subprocess.run(
            cmd,
            cwd=root_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            record["run_status"] = "failed"
            stderr = (proc.stderr or "").strip().splitlines()
            short_err = stderr[-1] if stderr else f"returncode {proc.returncode}"
            record["message"] = short_err
            print(f"[失敗] {case.case_id}: {short_err}")
            return record

        record["run_status"] = "success"
        note = populate_record_from_outputs(record, case, config_data)
        if note:
            record["message"] = note
        mark_case_complete(case, case.outdir / "summary.json", case.outdir / "series" / "run.parquet")
        return record
    except Exception as exc:  # pragma: no cover - defensive logging
        record["run_status"] = "failed"
        record["message"] = str(exc)
        print(f"[失敗] {case.case_id}: {exc}")
        return record


def _results_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(results)
    if "run_status" in df.columns:
        df["run_status"] = df["run_status"].astype(str)
    if "case_status" in df.columns:
        df["case_status"] = df["case_status"].astype(str)
    return df


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    script_path = Path(__file__).resolve()
    root_dir = script_path.parent.parent
    base_path = Path(args.base)
    if not base_path.is_absolute():
        base_path = root_dir / base_path
    if not base_path.exists():
        raise FileNotFoundError(f"ベース設定ファイルが見つかりません: {base_path}")

    def _pick(new_value: Optional[float], legacy_value: Optional[float]) -> Optional[float]:
        return new_value if new_value is not None else legacy_value

    map_overrides = {
        "rRM_min": _pick(args.rmin_rm, args.rRM_min),
        "rRM_max": _pick(args.rmax_rm, args.rRM_max),
        "rRM_step": _pick(args.rstep_rm, args.rRM_step),
        "TM_min": _pick(args.tmin_k, args.TM_min),
        "TM_max": _pick(args.tmax_k, args.TM_max),
        "TM_step": _pick(args.tstep_k, args.TM_step),
    }
    if args.rRM is not None:
        r_min, r_max, r_count = args.rRM
        if r_count <= 1:
            r_step = r_max - r_min if r_max != r_min else 0.0
        else:
            r_step = (r_max - r_min) / max(r_count - 1, 1)
        map_overrides.update({
            "rRM_min": r_min,
            "rRM_max": r_max,
            "rRM_step": r_step,
        })
    if args.TM is not None:
        T_min, T_max, T_count = args.TM
        if T_count <= 1:
            T_step = T_max - T_min if T_max != T_min else 0.0
        else:
            T_step = (T_max - T_min) / max(T_count - 1, 1)
        map_overrides.update({
            "TM_min": T_min,
            "TM_max": T_max,
            "TM_step": T_step,
        })
    map_def = create_map_definition(args.map, overrides=map_overrides)
    variant_override: Optional[List[VariantSpec]] = None
    if map_def.map_key == "1" and args.variants is not None:
        variant_override = build_variant_grid_from_spec(args.variants)
    num_parts = max(1, int(args.num_parts))
    part_index = int(args.part_index)
    if part_index < 1 or part_index > num_parts:
        raise ValueError("part-index は 1 以上 num-parts 以下で指定してください")
    if num_parts > 1 and map_def.map_key != "3":
        raise ValueError("分割実行は Map-3 にのみ対応しています")

    out_root = Path(args.outdir)
    if not out_root.is_absolute():
        out_root = root_dir / out_root
    ensure_directory(out_root / map_def.output_stub)

    base_config = load_base_config(base_path)
    partitions: Optional[List[np.ndarray]] = None
    y_filter: Optional[Iterable[int]] = None
    if num_parts > 1:
        partitions = partition_param_values(map_def.param_y, num_parts)
        if not partitions or len(partitions) != num_parts:
            raise RuntimeError("分割の生成に失敗しました")
        y_filter = partitions[part_index - 1].tolist()

    cases = build_cases(
        map_def,
        out_root,
        y_index_filter=y_filter,
        partition_index=part_index,
        partition_count=num_parts,
        variants=variant_override,
    )
    total_cases = len(cases)
    global_cases = len(map_def.param_x.values) * len(map_def.param_y.values)
    if num_parts > 1:
        part_values = [map_def.param_y.values[idx] for idx in partitions[part_index - 1]]
        smin_min = min(part_values) if part_values else float("nan")
        smin_max = max(part_values) if part_values else float("nan")
        print(
            f"マップ{map_def.map_key}: 全体 {global_cases} 件中 {total_cases} 件を実行 (分割 {part_index}/{num_parts}, "
            f"s_min∈[{smin_min:.3e}, {smin_max:.3e}] m)"
        )
    else:
        print(f"マップ{map_def.map_key}: 合計{total_cases}ケースを実行します")

    python_executable = sys.executable or "python"
    results: List[Dict[str, Any]] = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as executor:
        future_map = {
            executor.submit(
                run_case,
                case,
                base_config,
                root_dir,
                python_executable,
                args.qpr_table,
            ): case
            for case in cases
        }
        for future in concurrent.futures.as_completed(future_map):
            res = future.result()
            results.append(res)
            completed += 1
            run_status = res.get("run_status", "")
            physical_status = res.get("case_status", "")
            if str(run_status).lower() == "success":
                mass = res.get("total_mass_lost_Mmars", math.nan)
                print(
                    f"[{completed}/{total_cases}] 実行成功: {res['case_id']} (状態={physical_status}, 損失={mass:.3e} M_Mars)"
                )
            else:
                reason = res.get("message", "")
                print(f"[{completed}/{total_cases}] 実行失敗: {res['case_id']} ({reason})")

    results.sort(key=lambda rec: rec.get("order", 0))

    df = _results_dataframe(results)
    if "order" in df.columns:
        df.sort_values("order", inplace=True)
    elif {"param_x_value", "param_y_value"}.issubset(df.columns):
        df.sort_values(["param_x_value", "param_y_value"], inplace=True)

    results_dir = root_dir / "results"
    ensure_directory(results_dir)
    output_csv = results_dir / f"{map_def.output_stub}.csv"

    df_to_write = df.copy()
    metrics_requested: set[str] = set()
    primary_metric = (args.metric or "").strip()
    if primary_metric:
        metrics_requested.add(primary_metric)
    for extra_metric in getattr(args, "also_metrics", None) or []:
        name = (extra_metric or "").strip()
        if name:
            metrics_requested.add(name)
    if not metrics_requested:
        metrics_requested.add("beta_ratio")

    if "beta_ratio" in metrics_requested:
        if {"beta_at_smin_effective", "beta_threshold"}.issubset(df_to_write.columns):
            with np.errstate(divide="ignore", invalid="ignore"):
                beta_thresh = df_to_write["beta_threshold"].replace({0.0: np.nan})
                df_to_write["beta_ratio"] = df_to_write["beta_at_smin_effective"].astype(float) / beta_thresh.astype(float)
        else:
            df_to_write["beta_ratio"] = np.nan

    if "blow_fraction" in metrics_requested:
        if {"mass_lost_by_blowout", "mass_lost_by_sinks"}.issubset(df_to_write.columns):
            blow_vals = pd.to_numeric(df_to_write["mass_lost_by_blowout"], errors="coerce")
            sink_vals = pd.to_numeric(df_to_write["mass_lost_by_sinks"], errors="coerce")
            denom = blow_vals + sink_vals
            with np.errstate(divide="ignore", invalid="ignore"):
                fraction = np.where(denom > 0.0, blow_vals / denom, np.nan)
            df_to_write["blow_fraction"] = fraction
        else:
            df_to_write["blow_fraction"] = np.nan

    if primary_metric:
        df_to_write["metric_primary"] = primary_metric
    if metrics_requested:
        df_to_write["metrics_recorded"] = ",".join(sorted(metrics_requested))
    write_final = True
    if num_parts > 1:
        parts_dir = results_dir / "parts" / map_def.output_stub
        ensure_directory(parts_dir)
        part_filename = f"{map_def.output_stub}_part{part_index:02d}_of{num_parts:02d}.csv"
        part_path = parts_dir / part_filename
        df_to_write.to_csv(part_path, index=False)
        print(f"分割結果を {part_path} に保存しました")

        combined_frames: List[pd.DataFrame] = []
        all_present = True
        for idx in range(1, num_parts + 1):
            candidate = parts_dir / f"{map_def.output_stub}_part{idx:02d}_of{num_parts:02d}.csv"
            if not candidate.exists():
                all_present = False
                break
            combined_frames.append(pd.read_csv(candidate))
        if all_present and combined_frames:
            combined = pd.concat(combined_frames, ignore_index=True)
            if "case_id" in combined.columns:
                combined = combined.drop_duplicates(subset=["case_id"], keep="last")
            if "order" in combined.columns:
                combined.sort_values("order", inplace=True)
            elif {"param_x_value", "param_y_value"}.issubset(combined.columns):
                combined.sort_values(["param_x_value", "param_y_value"], inplace=True)
            df_to_write = combined
            print(f"全{num_parts}分割が揃ったため {output_csv} を更新します")
        else:
            write_final = False
            print("他の分割完了を待機中のため集約CSVは更新しません")

    column_order = [
        "map_id",
        "base_case_id",
        "case_id",
        "variant_label",
        "variant_s_min_m",
        "variant_s_min_um",
        "variant_chi_blow",
        "variant_sink_mode",
        "run_status",
        "case_status",
        "param_x_name",
        "param_x_value",
        "param_y_name",
        "param_y_value",
        "partition_index",
        "partition_count",
        "total_mass_lost_Mmars",
        "mass_lost_by_blowout",
        "mass_lost_by_sinks",
        "blow_fraction",
        "mass_per_r2",
        "s_min_effective",
        "s_min_config",
        "s_min_effective_gt_config",
        "beta_at_smin_config",
        "beta_at_smin_effective",
        "beta_at_smin",
        "beta_threshold",
        "beta_ratio",
        "s_blow_m",
        "rho_used",
        "Q_pr_used",
        "Q_pr_blow",
        "qpr_table_path",
        "r_RM_used",
        "r_m_used",
        "r_source",
        "T_M_used",
        "T_M_source",
        "outdir",
        "metric_primary",
        "metrics_recorded",
        "message",
    ]
    if write_final:
        available_columns = [col for col in column_order if col in df_to_write.columns]
        df_output = df_to_write[available_columns]
        df_output.to_csv(output_csv, index=False)
        print(f"結果を {output_csv} に保存しました")
        sweep_dir = out_root / map_def.output_stub
        ensure_directory(sweep_dir)
        df_output.to_csv(sweep_dir / f"{map_def.output_stub}.csv", index=False)
        print(f"結果を {sweep_dir / (map_def.output_stub + '.csv')} にコピーしました")
    else:
        print("集約CSVの更新は保留しました")

    if map_def.map_key in {"1", "1b"}:
        validation = validate_map1_results(df)
        validation_path = results_dir / f"{map_def.output_stub}_validation.json"
        with validation_path.open("w", encoding="utf-8") as fh:
            json.dump(validation, fh, indent=2, sort_keys=True)
        sweep_validation = out_root / f"{map_def.output_stub}_validation.json"
        with sweep_validation.open("w", encoding="utf-8") as fh:
            json.dump(validation, fh, indent=2, sort_keys=True)
        if not (validation["low_temp_band"]["ok"] and validation["mass_per_r2"]["ok"]):
            print("[警告] Map-1 検証チェックを満たしていません。詳細は validation.json を参照してください。")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()


__all__ = [
    "ParamSpec",
    "MapDefinition",
    "CaseSpec",
    "create_map_definition",
    "validate_map1_results",
]
