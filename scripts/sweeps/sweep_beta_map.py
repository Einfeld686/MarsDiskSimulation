"""Generate β(r/R_M, T_M, t) cubes for movie rendering.

Each grid point executes the 0D coupled loop defined in :mod:`marsdisk.run` for
one orbital period while enforcing ``dt / t_blow ≤ dt_over_t_blow_max``.  The
resulting time series of ``β`` (evaluated at ``s_min_effective =
max(s_min_config, a_blow)``) are consolidated into a Zarr array and a compact
``map_spec.json`` manifest that drives downstream visualisation tools.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Sequence

import numpy as np
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marsdisk.analysis import BetaSamplingConfig, sample_beta_over_orbit
from marsdisk.schema import Config


def _parse_grid(start: float, stop: float, count: int, label: str) -> np.ndarray:
    if count < 2:
        raise ValueError(f"{label} requires at least 2 samples")
    if stop <= start:
        raise ValueError(f"{label} stop must exceed start")
    grid = np.linspace(start, stop, count, dtype=float)
    return grid


def _load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if not isinstance(data, dict):
        raise TypeError("YAML configuration must be a mapping")
    return Config.model_validate(data)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)


def _write_zarr_array(path: Path, data: np.ndarray, *, axes: Sequence[str]) -> None:
    """Write a contiguous Zarr v2 array without extra dependencies."""

    path.mkdir(parents=True, exist_ok=True)
    array_meta = {
        "zarr_format": 2,
        "shape": list(data.shape),
        "chunks": list(data.shape),
        "dtype": str(data.dtype),
        "compressor": None,
        "fill_value": None,
        "filters": None,
        "order": "C",
    }
    attrs = {
        "axes": list(axes),
        "description": "β(r/R_M, T_M, t) sampled over one orbital period",
    }
    (path / ".zgroup").write_text(json.dumps({"zarr_format": 2}, indent=2), encoding="utf-8")
    (path / ".zarray").write_text(json.dumps(array_meta, indent=2), encoding="utf-8")
    (path / ".zattrs").write_text(json.dumps(attrs, indent=2), encoding="utf-8")
    chunk_path = path / (".".join("0" for _ in data.shape))
    with chunk_path.open("wb") as fh:
        fh.write(data.tobytes(order="C"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sweep β over (r/R_M, T_M) and store as a Zarr cube.")
    parser.add_argument("--config", type=Path, default=Path("configs/base.yml"), help="Base YAML configuration.")
    parser.add_argument(
        "--rRM",
        nargs=3,
        type=float,
        metavar=("START", "STOP", "COUNT"),
        required=True,
        help="Radial grid specification in Mars radii.",
    )
    parser.add_argument(
        "--TM",
        nargs=3,
        type=float,
        metavar=("START", "STOP", "COUNT"),
        required=True,
        help="Temperature grid specification in Kelvin.",
    )
    parser.add_argument("--qpr", type=Path, required=True, help="Path to the ⟨Q_pr⟩ lookup table.")
    parser.add_argument("--outdir", type=Path, required=True, help="Output directory for the sweep products.")
    parser.add_argument("--jobs", type=int, default=1, help="Parallel worker processes.")
    parser.add_argument("--min-steps", type=int, default=100, help="Minimum number of steps per orbit.")
    parser.add_argument(
        "--dt-over-tblow-max",
        type=float,
        default=0.1,
        help="Hard limit applied to dt/t_blow within the sequential coupling loop.",
    )
    parser.add_argument(
        "--enforce-mass-budget",
        action="store_true",
        help="Propagate mass budget violations from individual runs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "logs").mkdir(exist_ok=True, parents=True)
    log_path = outdir / "logs" / "beta_sweep.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Starting β sweep with arguments: %s", vars(args))

    r_start, r_stop, r_count = args.rRM
    t_start, t_stop, t_count = args.TM
    r_grid = _parse_grid(r_start, r_stop, int(r_count), "r/R_M grid")
    T_grid = _parse_grid(t_start, t_stop, int(t_count), "T_M grid")

    base_cfg = _load_config(args.config)
    sampling_cfg = BetaSamplingConfig(
        base_config=base_cfg,
        r_values=r_grid,
        T_values=T_grid,
        qpr_table_path=args.qpr,
        jobs=args.jobs,
        min_steps=args.min_steps,
        dt_over_t_blow_max=args.dt_over_tblow_max,
        capture_example_run_config=True,
        enforce_mass_budget=args.enforce_mass_budget,
    )

    r_vals, T_vals, time_grid, beta_cube = sample_beta_over_orbit(sampling_cfg)

    # Persist the beta cube and metadata.
    cube_path = outdir / "beta_cube.zarr"
    _write_zarr_array(cube_path, beta_cube, axes=("r_RM", "T_M", "time_s"))

    map_spec = {
        "r_RM_values": r_vals.tolist(),
        "T_M_values": T_vals.tolist(),
        "time_orbit_fraction": sampling_cfg.diagnostics.get("time_grid_fraction", []),
        "time_s": sampling_cfg.diagnostics.get("time_grid_s_reference", []),
        "t_orb_reference_s": sampling_cfg.diagnostics.get("t_orb_reference_s"),
        "t_orb_range_s": sampling_cfg.diagnostics.get("t_orb_range_s"),
        "time_steps_per_orbit": sampling_cfg.diagnostics.get("time_steps_per_orbit"),
        "dt_over_t_blow_cap": args.dt_over_tblow_max,
        "dt_over_t_blow_median": sampling_cfg.diagnostics.get("dt_over_t_blow_median"),
        "dt_over_t_blow_p90": sampling_cfg.diagnostics.get("dt_over_t_blow_p90"),
        "dt_over_t_blow_max_observed": sampling_cfg.diagnostics.get("dt_over_t_blow_max_observed"),
        "min_steps": args.min_steps,
        "jobs": args.jobs,
        "qpr_table_path": str(args.qpr),
        "config_path": str(args.config),
        "n_r": int(r_vals.size),
        "n_T": int(T_vals.size),
        "n_time": int(beta_cube.shape[2]),
        "Q_pr_used_stats": sampling_cfg.diagnostics.get("qpr_used_stats"),
    }
    _write_json(outdir / "map_spec.json", map_spec)

    example_cfg = sampling_cfg.diagnostics.get("example_run_config")
    if isinstance(example_cfg, dict):
        _write_json(outdir / "logs" / "example_run_config.json", example_cfg)
        logging.info("Stored example run_config with Q_pr_used=%.6f", example_cfg.get("run_inputs", {}).get("Q_pr_used", float("nan")))

    logging.info(
        "β sweep complete: r=%d, T=%d, steps=%d, dt/t_blow median=%.3f",
        int(r_vals.size),
        int(T_vals.size),
        int(beta_cube.shape[2]),
        sampling_cfg.diagnostics.get("dt_over_t_blow_median", float("nan")),
    )


if __name__ == "__main__":
    main()
