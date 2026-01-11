"""Generate mass-loss heatmaps and GIFs over (r/R_M, T_M) for specified Φ tables.

The driver executes zero-dimensional Mars disk simulations for a grid of
orbital radii and Mars-facing temperatures.  Each run integrates the coupled
production (C1–C3, P1, F1–F2, D1–D2) and surface-loss (R1–R3, S0–S1) system for
one year using the configuration in ``configs/innerdisk_base.yml``.  The
results are collated into per-orbit mass-loss maps which are visualised as
static PNG heatmaps and animated GIFs for different Φ(1) cases.

This script adheres to the user brief:

* Temperature sweeps use ``radiation.TM_K`` exclusively（legacy ``temps.T_M`` は廃止）。
* Φ tables are two-point τ lookups (τ=0→Φ=1, τ=1→Φ(1) case value).
* Per-orbit mass loss is sourced from ``orbit_rollup.csv`` with consistency
  checks against ``summary.json`` (T_M provenance, β diagnostics, orbit count).
* Outputs are written to ``out/phi{code}/`` with frames stored in
  ``frames/frame_XXXX.png`` and an accompanying ``anim.gif``.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency
    Image = None  # type: ignore[assignment]

try:
    import imageio.v2 as imageio
except ImportError:  # pragma: no cover - optional dependency
    imageio = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "innerdisk_base.yml"
DEFAULT_OUTDIR = ROOT / "out"
DEFAULT_PHI_TABLES = {
    "020": ROOT / "data" / "phi_tau_phi1_020.csv",
    "037": ROOT / "data" / "phi_tau_phi1_037.csv",
    "060": ROOT / "data" / "phi_tau_phi1_060.csv",
}
PHI_CASE_VALUES = {
    "020": 0.20,
    "037": 0.37,
    "060": 0.60,
}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from marsdisk import config_utils, constants
from marsdisk.run import load_config, run_zero_d
from marsdisk.schema import Config, Radiation, Shielding


class SimulationFailure(RuntimeError):
    """Raised when a single-case simulation fails validation."""


def _resolve_table_path(path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        parquet_path = path.with_suffix(".parquet")
        if parquet_path.exists():
            if not path.exists() or parquet_path.stat().st_mtime >= path.stat().st_mtime:
                return parquet_path
    elif suffix in {".parquet", ".pq"} and not path.exists():
        csv_path = path.with_suffix(".csv")
        if csv_path.exists():
            return csv_path
    return path


def _build_temperature_grid(T_min: float, T_max: float, spacing: float) -> np.ndarray:
    if spacing <= 0.0:
        raise ValueError("Temperature spacing must be positive.")
    count = int(math.floor((T_max - T_min) / spacing + 0.5)) + 1
    grid = T_min + np.arange(count, dtype=float) * spacing
    # ensure upper bound inclusive within tolerance
    grid = grid[(grid >= T_min - 1e-9) & (grid <= T_max + 1e-9)]
    return grid


def _build_radius_grid(r_min: float, r_max: float, count: int) -> np.ndarray:
    if count < 2:
        raise ValueError("Radius grid requires at least two points.")
    if r_max <= r_min:
        raise ValueError("r_max must exceed r_min.")
    return np.linspace(r_min, r_max, count, dtype=float)


def _prepare_case_config(
    base_cfg: Config,
    *,
    r_rm: float,
    T_M: float,
    phi_table: Path,
    outdir: Path,
) -> Config:
    """Return a deep-copied configuration tailored to a single grid point."""

    cfg = base_cfg.model_copy(deep=True)

    cfg.geometry.mode = "0D"
    config_utils.ensure_disk_geometry(cfg, float(r_rm))

    if cfg.radiation is None:
        cfg.radiation = Radiation(TM_K=float(T_M))
    else:
        cfg.radiation.TM_K = float(T_M)
    cfg.radiation.Q_pr = None

    if cfg.shielding is None:
        cfg.shielding = Shielding()
    cfg.shielding.table_path = str(phi_table)

    cfg.sinks.mode = "none"
    cfg.sinks.enable_sublimation = False
    cfg.sinks.enable_gas_drag = False

    cfg.numerics.t_end_years = None
    cfg.numerics.t_end_orbits = 1.0
    cfg.numerics.dt_init = 50.0
    cfg.numerics.eval_per_step = True
    cfg.numerics.orbit_rollup = True
    cfg.numerics.dt_over_t_blow_max = 10.0

    cfg.io.outdir = outdir

    return cfg


def _validate_summary(summary: Dict[str, object], *, phi_label: str, r_rm: float, T_M: float) -> None:
    """Ensure required provenance fields are present in summary.json."""

    source = summary.get("T_M_source")
    if source != "radiation.TM_K":
        raise SimulationFailure(
            f"Unexpected T_M_source={source!r} for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
        )
    for key in ("beta_at_smin_config", "beta_at_smin_effective"):
        if summary.get(key) is None:
            raise SimulationFailure(
                f"summary.json missing {key} for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
            )
    orbits_completed = int(summary.get("orbits_completed", 0))
    T_used = float(summary.get("T_M_used", -np.inf))
    if not math.isfinite(T_used) or abs(T_used - T_M) > 1e-6:
        raise SimulationFailure(
            f"T_M_used={T_used} inconsistent with target {T_M} for Φ({phi_label}) at r={r_rm:.3f}R_M"
        )
    base = summary.get("M_out_mean_per_orbit")
    if orbits_completed > 0 and base is not None and not math.isfinite(float(base)):
        raise SimulationFailure(
            f"M_out_mean_per_orbit not finite for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
        )


def _run_single_case(
    base_cfg: Config,
    *,
    r_rm: float,
    T_M: float,
    phi_table: Path,
    phi_label: str,
) -> Tuple[Dict[str, object], pd.DataFrame]:
    """Execute one 0D run and return (summary, orbit_rollup_df)."""

    with tempfile.TemporaryDirectory(prefix="marsdisk_innerdisk_") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        case_cfg = _prepare_case_config(
            base_cfg,
            r_rm=r_rm,
            T_M=T_M,
            phi_table=phi_table,
            outdir=tmpdir,
        )
        run_zero_d(case_cfg)

        summary_path = tmpdir / "summary.json"
        if not summary_path.exists():
            raise SimulationFailure(
                f"summary.json missing for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
            )
        with summary_path.open("r", encoding="utf-8") as fh:
            summary = json.load(fh)

        orbit_path = _resolve_table_path(tmpdir / "orbit_rollup.csv")
        orbit_df: pd.DataFrame | None = None
        if orbit_path.exists():
            if orbit_path.suffix.lower() in {".parquet", ".pq"}:
                tmp_df = pd.read_parquet(orbit_path)
            else:
                tmp_df = pd.read_csv(orbit_path)
            if not tmp_df.empty:
                orbit_df = tmp_df

        orbits_completed = int(summary.get("orbits_completed", 0))
        if orbit_df is None:
            # Construct a synthetic single-orbit rollup when the integrator did not emit rows,
            # typically because coarse dt prevented the accumulator from crossing t_orb exactly.
            time_grid = summary.get("time_grid", {}) or {}
            t_end_s = float(time_grid.get("t_end_s", 0.0) or 0.0)
            if not math.isfinite(t_end_s) or t_end_s <= 0.0:
                raise SimulationFailure(
                    f"orbit_rollup.csv missing and t_end_s invalid for Φ({phi_label}) at "
                    f"r={r_rm:.3f}R_M, T={T_M:.0f}K"
                )
            target_orbits = float(time_grid.get("t_end_input", 1.0) or 1.0)
            if not math.isfinite(target_orbits) or target_orbits <= 0.0:
                target_orbits = 1.0
            estimated_orbits = max(int(round(target_orbits)), 1)
            effective_orbits = max(orbits_completed, estimated_orbits)
            t_orb_s = t_end_s / estimated_orbits
            M_out_total = float(summary.get("M_out_cum", 0.0))
            M_sink_total = float(summary.get("M_sink_cum", summary.get("M_loss_from_sinks", 0.0)))
            M_loss_total = float(summary.get("M_loss", M_out_total + M_sink_total))
            M_out_orbit = M_out_total / estimated_orbits
            M_sink_orbit = M_sink_total / estimated_orbits
            M_loss_orbit = M_loss_total / estimated_orbits
            initial_mass = float(case_cfg.initial.mass_total)
            frac_loss = float("nan")
            if initial_mass > 0.0:
                frac_loss = (M_out_orbit + M_sink_orbit) / initial_mass
            orbit_df = pd.DataFrame(
                [
                    {
                        "orbit_index": 1,
                        "time_s": t_end_s,
                        "t_orb_s": t_orb_s,
                        "M_out_orbit": M_out_orbit,
                        "M_sink_orbit": M_sink_orbit,
                        "M_loss_orbit": M_loss_orbit,
                        "M_out_per_orbit": M_out_orbit / t_orb_s if t_orb_s > 0.0 else 0.0,
                        "M_sink_per_orbit": M_sink_orbit / t_orb_s if t_orb_s > 0.0 else 0.0,
                        "M_loss_per_orbit": M_loss_orbit / t_orb_s if t_orb_s > 0.0 else 0.0,
                        "mass_loss_frac_per_orbit": frac_loss,
                        "M_out_cum": M_out_total,
                        "M_sink_cum": M_sink_total,
                        "M_loss_cum": M_loss_total,
                        "r_RM": r_rm,
                        "T_M": T_M,
                        "slope_dlnM_dlnr": None,
                    }
                ]
            )
            orbits_completed = max(orbits_completed, effective_orbits)
        else:
            if orbit_df.empty:
                raise SimulationFailure(
                    f"orbit_rollup.csv empty for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
                )

        _validate_summary(summary, phi_label=phi_label, r_rm=r_rm, T_M=T_M)

        mean_orbit = summary.get("M_out_mean_per_orbit")
        if mean_orbit is not None and math.isfinite(float(mean_orbit)):
            # Cross-check mean consistency within numerical tolerance.
            rollup_mean = float(orbit_df["M_out_orbit"].mean())
            if not math.isclose(float(mean_orbit), rollup_mean, rel_tol=5e-3, abs_tol=5e-6):
                raise SimulationFailure(
                    f"M_out_mean_per_orbit mismatch ({mean_orbit} vs {rollup_mean}) "
                    f"for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
                )

        run_cfg_path = tmpdir / "run_config.json"
        if not run_cfg_path.exists():
            raise SimulationFailure(
                f"run_config.json missing for Φ({phi_label}) at r={r_rm:.3f}R_M, T={T_M:.0f}K"
            )

        return summary, orbit_df


def _gif_backend() -> str:
    """Select GIF writer backend."""

    if imageio is not None:
        return "imageio"
    if Image is not None:
        return "pillow"
    raise RuntimeError("Neither imageio nor Pillow is available for GIF creation.")


def _save_gif(frame_paths: Iterable[Path], output_path: Path, duration_ms: int) -> None:
    backend = _gif_backend()
    frames = list(frame_paths)
    if not frames:
        raise RuntimeError("No frames were generated; cannot create GIF.")
    if backend == "imageio":  # pragma: no branch - branch selection above
        images = [imageio.imread(frame) for frame in frames]
        imageio.mimsave(output_path, images, duration=duration_ms / 1000.0)
    else:
        images = [Image.open(frame) for frame in frames]
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration_ms,
            loop=0,
        )
        for img in images:
            img.close()


def _plot_heatmap(
    data: np.ndarray,
    *,
    r_values: np.ndarray,
    T_values: np.ndarray,
    phi_label: str,
    frame_index: int,
    total_frames: int,
    output_path: Path,
    colour_range: Tuple[float, float],
) -> None:
    """Render a single heatmap frame."""

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    extent = [r_values[0], r_values[-1], T_values[0], T_values[-1]]
    masked = np.ma.masked_invalid(data)
    im = ax.imshow(
        masked,
        origin="lower",
        aspect="auto",
        extent=extent,
        cmap="viridis",
        vmin=colour_range[0],
        vmax=colour_range[1],
    )
    ax.set_xlabel("r / R_Mars")
    ax.set_ylabel("T_M [K]")
    ax.set_title(f"Φ(1)={PHI_CASE_VALUES[phi_label]:.2f} | frame {frame_index+1}/{total_frames}")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("質量損失 / orbit [M_Mars]")
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def run_sweep(
    *,
    base_config_path: Path,
    outdir: Path,
    phi_tables: Dict[str, Path],
    T_values: np.ndarray,
    r_values: np.ndarray,
    frame_duration_ms: int,
    max_frames: int | None,
) -> None:
    """Execute the full sweep for all Φ cases."""

    base_cfg = load_config(base_config_path)
    outdir.mkdir(parents=True, exist_ok=True)

    n_T = len(T_values)
    n_r = len(r_values)
    grid_total = n_T * n_r

    for phi_label, phi_path in phi_tables.items():
        if phi_label not in PHI_CASE_VALUES:
            raise ValueError(f"Unexpected Φ case label: {phi_label}")
        resolved_phi = _resolve_table_path(phi_path)
        if not resolved_phi.exists():
            raise FileNotFoundError(f"Φ table not found: {phi_path}")

        case_outdir = outdir / f"phi{phi_label}"
        frames_dir = case_outdir / "frames"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        frames_dir.mkdir(parents=True, exist_ok=True)

        per_orbit_maps: List[np.ndarray] = []
        orbit_counts = []
        total_runs = 0
        print(f"[Φ(1)={PHI_CASE_VALUES[phi_label]:.2f}] 開始: T×r = {n_T}×{n_r} = {grid_total}")

        for t_idx, T_M in enumerate(T_values):
            for r_idx, r_rm in enumerate(r_values):
                total_runs += 1
                summary, orbit_df = _run_single_case(
                    base_cfg,
                    r_rm=float(r_rm),
                    T_M=float(T_M),
                    phi_table=resolved_phi,
                    phi_label=phi_label,
                )
                orbits_recorded = int(summary.get("orbits_completed", 0))
                effective_orbits = max(orbits_recorded, len(orbit_df))
                orbit_counts.append(effective_orbits)
                frame_limit = effective_orbits
                if max_frames is not None:
                    frame_limit = min(frame_limit, max_frames)
                for _, row in orbit_df.head(frame_limit).iterrows():
                    orbit_index = int(row["orbit_index"]) - 1
                    while len(per_orbit_maps) <= orbit_index:
                        per_orbit_maps.append(
                            np.full((n_T, n_r), np.nan, dtype=np.float32)
                        )
                    per_orbit_maps[orbit_index][t_idx, r_idx] = float(row["M_out_orbit"])

                if total_runs % 500 == 0 or total_runs == grid_total:
                    print(
                        f"  進捗 Φ(1)={PHI_CASE_VALUES[phi_label]:.2f}: "
                        f"{total_runs}/{grid_total} cases 完了",
                        flush=True,
                    )

        if not per_orbit_maps:
            raise RuntimeError(f"No orbit data recorded for Φ({phi_label}).")

        # Determine global colour scale using available data prior to forward-fill.
        finite_vals: List[float] = []
        finite_max: List[float] = []
        for frame in per_orbit_maps:
            finite = frame[np.isfinite(frame)]
            if finite.size:
                finite_vals.append(float(finite.min()))
                finite_max.append(float(finite.max()))
        if not finite_vals or not finite_max:
            raise RuntimeError(f"Unable to determine colour scale for Φ({phi_label}).")
        vmin = float(min(finite_vals))
        vmax = float(max(finite_max))
        if math.isclose(vmin, vmax):
            vmax = vmin + 1e-8

        current_frame = np.full((n_T, n_r), np.nan, dtype=np.float32)
        frame_paths: List[Path] = []
        total_frames = len(per_orbit_maps)
        for orbit_idx, raw_frame in enumerate(per_orbit_maps):
            np.copyto(current_frame, current_frame)  # no-op to keep array allocated
            mask = ~np.isnan(raw_frame)
            current_frame[mask] = raw_frame[mask]
            frame_path = frames_dir / f"frame_{orbit_idx+1:04d}.png"
            _plot_heatmap(
                current_frame,
                r_values=r_values,
                T_values=T_values,
                phi_label=phi_label,
                frame_index=orbit_idx,
                total_frames=total_frames,
                output_path=frame_path,
                colour_range=(vmin, vmax),
            )
            frame_paths.append(frame_path)

        # Latest snapshot corresponds to the last fully populated frame.
        latest_png = case_outdir / "heatmap_latest.png"
        shutil.copy(frame_paths[-1], latest_png)

        gif_path = case_outdir / "anim.gif"
        _save_gif(frame_paths, gif_path, frame_duration_ms)

        meta = {
            "phi_label": phi_label,
            "phi_value": PHI_CASE_VALUES[phi_label],
            "config": str(base_config_path),
            "phi_table": str(resolved_phi),
            "temperatures_K": [float(T_values[0]), float(T_values[-1]), len(T_values)],
            "radii_RM": [float(r_values[0]), float(r_values[-1]), len(r_values)],
            "total_cases": grid_total,
            "max_orbits": int(max(orbit_counts) if orbit_counts else 0),
            "min_orbits": int(min(orbit_counts) if orbit_counts else 0),
            "frames_generated": len(frame_paths),
            "frame_duration_ms": frame_duration_ms,
            "gif_path": str(gif_path),
        }
        with (case_outdir / "metadata.json").open("w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2, ensure_ascii=False)

        print(
            f"[Φ(1)={PHI_CASE_VALUES[phi_label]:.2f}] 完了: フレーム {len(frame_paths)} 枚, "
            f"GIF -> {gif_path}",
            flush=True,
        )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="内側円盤の質量損失ヒートマップと GIF を生成するスイープドライバ"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="基準となる YAML 設定ファイル（0D ラン）",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTDIR,
        help="生成物（ヒートマップ／GIF）を書き出すルートディレクトリ",
    )
    parser.add_argument(
        "--frame-duration-ms",
        type=int,
        default=120,
        help="GIF のフレーム間隔（ミリ秒）",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="公転フレーム数の上限（デバッグ用）。未指定なら全公転を使用。",
    )
    parser.add_argument(
        "--t-min",
        type=float,
        default=1000.0,
        help="温度レンジ下限 [K]",
    )
    parser.add_argument(
        "--t-max",
        type=float,
        default=6000.0,
        help="温度レンジ上限 [K]",
    )
    parser.add_argument(
        "--t-step",
        type=float,
        default=50.0,
        help="温度ステップ [K]",
    )
    parser.add_argument(
        "--r-min",
        type=float,
        default=1.0,
        help="半径レンジ下限 [R_Mars]",
    )
    parser.add_argument(
        "--r-max",
        type=float,
        default=3.0,
        help="半径レンジ上限 [R_Mars]",
    )
    parser.add_argument(
        "--r-count",
        type=int,
        default=200,
        help="半径グリッド数（線形分割）",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    T_values = _build_temperature_grid(args.t_min, args.t_max, args.t_step)
    r_values = _build_radius_grid(args.r_min, args.r_max, args.r_count)
    run_sweep(
        base_config_path=args.config,
        outdir=args.outdir,
        phi_tables=DEFAULT_PHI_TABLES,
        T_values=T_values,
        r_values=r_values,
        frame_duration_ms=args.frame_duration_ms,
        max_frames=args.max_frames,
    )


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
