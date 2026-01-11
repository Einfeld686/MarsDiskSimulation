"""Generate β diagnostic maps across (r/R_M, T_M) grids.

This utility evaluates the coupled surface–radiation system described in the
specification on a two-dimensional grid.  For each grid point the particle
size distribution, optical depth and shielding factor are updated over one
orbital period using the existing Mars disk modules.  The resulting raw and
shielded radiation-pressure ratios (β) are saved as CSV and heatmap figures.

Usage example
-------------

.. code-block:: bash

    python tools/diagnostics/beta_map.py \
        --qpr-table marsdisk/io/data/qpr_planck.csv \
        --phi-table marsdisk/io/data/phi.csv \
        --config configs/base.yml \
        --outdir simulation_results/04_beta_map
"""

from __future__ import annotations

import argparse
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional, Tuple

import numpy as np
import pandas as pd

import matplotlib
import sys
import copy

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ruamel.yaml import YAML

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from marsdisk import constants
from marsdisk import grid
from marsdisk.io import tables
from marsdisk.physics import initfields, psd, radiation, sinks, sizes, surface
from marsdisk.physics.sublimation import SublimationParams, grain_temperature_graybody
from marsdisk.schema import Config

TAU_FLOOR = 1.0e-12
REL_T_VARIANCE_THRESHOLD = 0.01


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


class QPrCounter:
    """Wrapper counting successful/failed Q_pr interpolations."""

    def __init__(self, func: Callable[[float, float], float]) -> None:
        self._func = func
        self.calls = 0
        self.failures = 0

    def __call__(self, s: float, T: float) -> float:
        self.calls += 1
        try:
            return float(self._func(s, T))
        except Exception:
            self.failures += 1
            raise


@dataclass
class BetaCellResult:
    r_RM: float
    T_M: float
    beta_raw: float
    beta_eff: float
    qpr_used: float
    tau_final: float
    phi_used: float
    s_min_config: float
    a_blow_final: float
    sigma_tau1_final: float
    dt_ratio: float


@dataclass
class RuntimeContext:
    cfg: Config
    qpr_lookup: QPrCounter
    phi_fn: Optional[Callable[[float], float]]
    phi_origin: str
    sigma_func: Optional[Callable[[float], float]]
    rho_p: float
    s_min_config: float
    s_max: float
    n_bins: int
    alpha: float
    wavy_strength: float
    n_steps: int
    s_ref: float
    beta_threshold: float
    sink_mode: str
    enable_sublimation: bool
    enable_gas_drag: bool
    rho_gas: float
    sub_params_template: SublimationParams
    use_tcoll: bool
    logger: logging.Logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate β diagnostic maps.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/base.yml"),
        help="Path to the base YAML configuration.",
    )
    parser.add_argument(
        "--qpr-table",
        type=Path,
        default=tables.DATA_DIR / "qpr_planck.csv",
        help="Lookup table for ⟨Q_pr⟩ (CSV/HDF).",
    )
    parser.add_argument(
        "--phi-table",
        type=Path,
        default=None,
        help="Optional τ-only Φ(τ) lookup table. Default uses packaged table or approximation.",
    )
    parser.add_argument("--rmin", type=float, default=1.0, help="Minimum r/R_M.")
    parser.add_argument("--rmax", type=float, default=3.0, help="Maximum r/R_M.")
    parser.add_argument("--rnum", type=int, default=41, help="Number of radial samples.")
    parser.add_argument("--tmin", type=float, default=2000.0, help="Minimum T_M [K].")
    parser.add_argument("--tmax", type=float, default=6000.0, help="Maximum T_M [K].")
    parser.add_argument("--tnum", type=int, default=41, help="Number of temperature samples.")
    parser.add_argument(
        "--s-min",
        type=float,
        default=None,
        help="Minimum grain size floor [m]; overrides config.sizes.s_min when provided.",
    )
    parser.add_argument(
        "--rho-p",
        type=float,
        default=None,
        help="Particle density [kg/m^3]; overrides config.material.rho when provided.",
    )
    parser.add_argument(
        "--n-step",
        type=int,
        default=100,
        help="Number of time steps per orbit.",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("simulation_results/04_beta_map"),
        help="Directory for CSV/figure outputs.",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=Path("_logs/04_beta_map.log"),
        help="Path to the diagnostic log file.",
    )
    parser.add_argument(
        "--beta-thr",
        type=float,
        default=radiation.BLOWOUT_BETA_THRESHOLD,
        help="Radiation-pressure blowout threshold β value.",
    )
    return parser.parse_args()


def setup_logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("beta_map")
    logger.setLevel(logging.INFO)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def load_config(path: Path) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"Config file does not exist: {path}")
    yaml = YAML(typ="safe")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    return Config.model_validate(data)


def resolve_sigma_function(cfg: Config) -> Optional[Callable[[float], float]]:
    if cfg.disk is None or cfg.inner_disk_mass is None:
        return None

    r_in = cfg.disk.geometry.r_in_RM * constants.R_MARS
    r_out = cfg.disk.geometry.r_out_RM * constants.R_MARS
    if cfg.inner_disk_mass.use_Mmars_ratio:
        M_in = cfg.inner_disk_mass.M_in_ratio * constants.M_MARS
    else:
        M_in = cfg.inner_disk_mass.M_in_ratio
    return initfields.sigma_from_Minner(
        M_in,
        r_in,
        r_out,
        cfg.disk.geometry.p_index,
    )


def resolve_phi_function(
    explicit_path: Optional[Path],
) -> Tuple[Optional[Callable[[float], float]], str]:
    default_w0 = 0.0
    default_g = 0.0

    def _from_three_d_table(path: Path) -> Tuple[Callable[[float], float], str]:
        path = _resolve_table_path(path)
        if path.suffix.lower() in {".parquet", ".pq"}:
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        table_obj = tables.PhiTable.from_frame(df)

        def phi_fn(tau: float) -> float:
            return float(
                np.clip(
                    table_obj.interp(float(tau), default_w0, default_g),
                    0.0,
                    1.0,
                )
            )

        return phi_fn, f"table-3D:{path.resolve()}(w0={default_w0},g={default_g})"

    if explicit_path is not None:
        try:
            phi_fn = tables.load_phi_table(explicit_path)
            return phi_fn, f"table-τ:{explicit_path.resolve()}"
        except ValueError:
            return _from_three_d_table(explicit_path)

    internal = getattr(tables, "_PHI_TABLE", None)
    if internal is not None:
        default_path = tables.DATA_DIR / "phi.csv"
        try:
            phi_fn = tables.load_phi_table(default_path)
            return phi_fn, f"table-τ:{default_path.resolve()}"
        except ValueError:
            return _from_three_d_table(default_path)

    # fall back to interpolator with default w0=g=0 context
    def approx_phi(tau: float) -> float:
        return float(np.clip(tables.interp_phi(float(tau), 0.0, 0.0), 0.0, 1.0))

    return approx_phi, "approximation"


def compute_a_blow(qpr: float, rho: float, T_M: float, beta_thr: float) -> float:
    L_mars = 4.0 * math.pi * (constants.R_MARS**2) * constants.SIGMA_SB * (T_M**4)
    numerator = 3.0 * L_mars * qpr
    denominator = 16.0 * math.pi * constants.C * constants.G * constants.M_MARS * rho * beta_thr
    return numerator / denominator


def copy_sublimation_params(template: SublimationParams) -> SublimationParams:
    return copy.deepcopy(template)


def evaluate_cell(
    r_RM: float,
    T_M: float,
    ctx: RuntimeContext,
) -> BetaCellResult:
    r_m = r_RM * constants.R_MARS
    Omega = grid.omega(r_m)
    if not math.isfinite(Omega) or Omega <= 0.0:
        raise ValueError(f"Invalid Keplerian frequency at r/R_M={r_RM:.3f}")
    t_orb = 2.0 * math.pi / Omega
    dt = t_orb / ctx.n_steps
    t_blow = 1.0 / Omega
    dt_limit = 0.05 * t_blow
    dt_ratio = dt / dt_limit if dt_limit > 0.0 else float("inf")

    sub_params = copy_sublimation_params(ctx.sub_params_template)
    setattr(sub_params, "runtime_orbital_radius_m", r_m)
    setattr(sub_params, "runtime_t_orb_s", t_orb)
    setattr(sub_params, "runtime_Omega", Omega)

    sink_opts = sinks.SinkOptions(
        enable_sublimation=ctx.enable_sublimation and ctx.sink_mode != "none",
        sub_params=sub_params,
        enable_gas_drag=ctx.enable_gas_drag,
        rho_g=ctx.rho_gas,
    )

    sigma_mid = 0.0
    if ctx.sigma_func is not None:
        sigma_mid = float(max(ctx.sigma_func(r_m), 0.0))
        r_in = ctx.cfg.disk.geometry.r_in_RM if ctx.cfg.disk else None
        r_out = ctx.cfg.disk.geometry.r_out_RM if ctx.cfg.disk else None
        if r_in is not None and r_out is not None and not (r_in <= r_RM <= r_out):
            sigma_mid = 0.0

    qpr_initial = ctx.qpr_lookup(ctx.s_ref, T_M)
    a_blow = compute_a_blow(qpr_initial, ctx.rho_p, T_M, ctx.beta_threshold)
    s_min_effective = max(ctx.s_min_config, a_blow)

    psd_state = psd.update_psd_state(
        s_min=s_min_effective,
        s_max=ctx.s_max,
        alpha=ctx.alpha,
        wavy_strength=ctx.wavy_strength,
        n_bins=ctx.n_bins,
        rho=ctx.rho_p,
    )
    kappa_surf = psd.compute_kappa(psd_state)

    def phi_tau(tau: float) -> float:
        if ctx.phi_fn is not None:
            value = ctx.phi_fn(float(tau))
        else:
            value = tables.interp_phi(float(tau), 0.0, 0.0)
        return float(np.clip(value, 0.0, 1.0))

    tau_mid = kappa_surf * sigma_mid
    phi_mid = phi_tau(tau_mid)
    kappa_eff_init = float(phi_mid * kappa_surf)
    sigma_tau1_init = float(1.0 / kappa_eff_init) if kappa_eff_init > 0.0 else float("inf")

    sigma_surf = initfields.surf_sigma_init(
        sigma_mid,
        kappa_eff_init if math.isfinite(kappa_eff_init) and kappa_eff_init > 0.0 else None,
        ctx.cfg.surface.init_policy,
        sigma_override=ctx.cfg.surface.sigma_surf_init_override,
    )
    if math.isfinite(sigma_tau1_init):
        sigma_surf = min(sigma_surf, sigma_tau1_init)

    phi_val = phi_mid
    tau_val = tau_mid
    beta_raw = radiation.beta(ctx.s_ref, ctx.rho_p, T_M, Q_pr=qpr_initial)

    for _ in range(ctx.n_steps):
        qpr_val = ctx.qpr_lookup(ctx.s_ref, T_M)
        a_blow = compute_a_blow(qpr_val, ctx.rho_p, T_M, ctx.beta_threshold)
        s_min_effective = max(ctx.s_min_config, a_blow)

        T_grain = grain_temperature_graybody(T_M, r_m)
        ds_dt_val = 0.0
        if sink_opts.enable_sublimation:
            try:
                ds_dt_val = sizes.eval_ds_dt_sublimation(T_grain, ctx.rho_p, sub_params)
            except Exception as exc:
                ctx.logger.warning(
                    "ds/dt evaluation failed at r/R_M=%.3f T=%.0f K: %s",
                    r_RM,
                    T_M,
                    exc,
                )
                ds_dt_val = 0.0

        sigma_surf, _, _ = psd.apply_uniform_size_drift(
            psd_state,
            ds_dt=ds_dt_val,
            dt=dt,
            floor=s_min_effective,
            sigma_surf=sigma_surf,
        )

        kappa_surf = psd.compute_kappa(psd_state)
        tau_val = kappa_surf * sigma_surf
        if tau_val < TAU_FLOOR:
            tau_val = 0.0

        phi_val = phi_tau(tau_val)
        kappa_eff = phi_val * kappa_surf
        sigma_tau1 = float(1.0 / kappa_eff) if kappa_eff > 0.0 else float("inf")
        sigma_target = sigma_mid
        if math.isfinite(sigma_tau1):
            sigma_target = min(sigma_target, sigma_tau1)

        sink_result = sinks.total_sink_timescale(
            T_M,
            ctx.rho_p,
            Omega,
            sink_opts,
            s_ref=ctx.s_ref,
        )
        t_sink = sink_result.t_sink

        t_coll_val = None
        if ctx.use_tcoll and tau_val > TAU_FLOOR:
            try:
                t_coll_val = surface.wyatt_tcoll_S1(tau_val, Omega)
            except Exception:
                t_coll_val = None

        loss_rate = Omega
        if t_coll_val and t_coll_val > 0.0:
            loss_rate += 1.0 / t_coll_val
        if t_sink and t_sink > 0.0:
            loss_rate += 1.0 / t_sink

        prod_rate = sigma_target * loss_rate if loss_rate > 0.0 else 0.0
        res = surface.step_surface(
            sigma_surf,
            prod_rate,
            dt,
            Omega,
            tau=tau_val if ctx.use_tcoll else None,
            t_sink=t_sink,
            sigma_tau1=sigma_tau1 if math.isfinite(sigma_tau1) else None,
        )
        sigma_surf = res.sigma_surf
        beta_raw = radiation.beta(ctx.s_ref, ctx.rho_p, T_M, Q_pr=qpr_val)

    beta_eff = beta_raw * phi_val
    sigma_tau1_final = (
        float(1.0 / (phi_val * kappa_surf)) if kappa_surf > 0.0 and phi_val > 0.0 else float("inf")
    )

    return BetaCellResult(
        r_RM=r_RM,
        T_M=T_M,
        beta_raw=float(beta_raw),
        beta_eff=float(beta_eff),
        qpr_used=float(qpr_val),
        tau_final=float(tau_val),
        phi_used=float(phi_val),
        s_min_config=float(ctx.s_min_config),
        a_blow_final=float(a_blow),
        sigma_tau1_final=float(sigma_tau1_final),
        dt_ratio=float(dt_ratio),
    )


def build_heatmap(
    data: np.ndarray,
    r_values: np.ndarray,
    T_values: np.ndarray,
    beta_threshold: float,
    title: str,
    filepath: Path,
) -> None:
    X, Y = np.meshgrid(r_values, T_values)
    fig, ax = plt.subplots(figsize=(8, 6))
    mesh = ax.pcolormesh(
        X,
        Y,
        data,
        shading="auto",
        cmap="viridis",
    )
    cbar = fig.colorbar(mesh, ax=ax, label="β")
    contour = ax.contour(
        X,
        Y,
        data / beta_threshold,
        levels=[1.0],
        colors="white",
        linewidths=1.0,
    )
    if contour.allsegs:
        ax.clabel(contour, fmt="β/β_thr=1", inline=True, fontsize=8)
    ax.set_xlabel("r / R_M")
    ax.set_ylabel("T_M [K]")
    ax.set_title(title)
    fig.tight_layout()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(filepath, dpi=200)
    plt.close(fig)


def summarise_variation(
    matrix: np.ndarray,
    axis: int,
) -> np.ndarray:
    mean_vals = np.mean(matrix, axis=axis)
    std_vals = np.std(matrix, axis=axis)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.where(mean_vals != 0.0, std_vals / np.abs(mean_vals), np.nan)
    return rel


def write_readme(
    outdir: Path,
    ctx: RuntimeContext,
    config_path: Path,
    qpr_table_path: Path,
    phi_origin: str,
    beta_raw_map: np.ndarray,
    beta_eff_map: np.ndarray,
    r_values: np.ndarray,
    T_values: np.ndarray,
    dt_warning_cells: int,
    total_cells: int,
    qpr_counter: QPrCounter,
) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    readme_path = outdir / "README.md"

    rel_std_T = summarise_variation(beta_raw_map, axis=0)
    rel_std_r = summarise_variation(beta_eff_map, axis=1)

    weak_T = np.nan_to_num(rel_std_T, nan=np.inf) <= REL_T_VARIANCE_THRESHOLD
    weak_r = np.nan_to_num(rel_std_r, nan=np.inf) <= REL_T_VARIANCE_THRESHOLD
    weak_T_count = int(np.sum(weak_T))
    weak_r_count = int(np.sum(weak_r))

    lines: list[str] = []
    lines.append("# β Diagnostic Map\n")
    lines.append("| Item | Value |\n")
    lines.append("|---|---|\n")
    lines.append(f"| Generated | {datetime.utcnow().isoformat()}Z |\n")
    lines.append(f"| Config | `{config_path}` |\n")
    lines.append(f"| Q_pr table | `{qpr_table_path}` |\n")
    lines.append(f"| Φ source | `{phi_origin}` |\n")
    lines.append(f"| s_ref [m] | {ctx.s_ref:.3e} |\n")
    lines.append(f"| ρ_p [kg/m³] | {ctx.rho_p:.1f} |\n")
    lines.append(f"| β_thr | {ctx.beta_threshold:.3f} |\n")
    lines.append(f"| Steps per orbit | {ctx.n_steps} |\n")
    lines.append(f"| Grid | r∈[{r_values[0]:.2f},{r_values[-1]:.2f}] (N={len(r_values)}), T∈[{T_values[0]:.0f},{T_values[-1]:.0f}] (N={len(T_values)}) |\n")
    lines.append(f"| dt/t_blow > 0.05 | {dt_warning_cells} / {total_cells} cells |\n")
    lines.append(f"| ⟨Q_pr⟩ lookups | {qpr_counter.calls} calls (failures: {qpr_counter.failures}) |\n")

    if weak_T_count == len(r_values):
        lines.append(
            "\n> ⚠️ β_raw shows <1% relative variation along T_M for every radius; consider refining the ⟨Q_pr⟩ table or verifying temperature dependence."
        )
    elif weak_T_count > 0:
        fraction = weak_T_count / len(r_values)
        lines.append(
            f"\n> ⚠️ β_raw exhibits <1% variation along T_M for {weak_T_count} radii ({fraction:.2%})."
        )

    if weak_r_count == len(T_values):
        lines.append(
            "\n> ⚠️ β_eff displays <1% variation with radius across all temperatures; Φ(τ) updates may be ineffective."
        )
    elif weak_r_count > 0:
        fraction = weak_r_count / len(T_values)
        lines.append(
            f"\n> ⚠️ β_eff varies by <1% with radius for {weak_r_count} temperature slices ({fraction:.2%})."
        )

    beta_raw_min = float(np.nanmin(beta_raw_map))
    beta_raw_max = float(np.nanmax(beta_raw_map))
    beta_eff_min = float(np.nanmin(beta_eff_map))
    beta_eff_max = float(np.nanmax(beta_eff_map))
    lines.append(
        f"\nβ_raw range: {beta_raw_min:.3e} – {beta_raw_max:.3e}; β_eff range: {beta_eff_min:.3e} – {beta_eff_max:.3e}."
    )

    with readme_path.open("w", encoding="utf-8") as fh:
        fh.writelines(line if line.endswith("\n") else f"{line}\n" for line in lines)


def main() -> None:
    args = parse_args()
    logger = setup_logger(args.log_path)
    cfg = load_config(args.config)

    qpr_table = _resolve_table_path(args.qpr_table).resolve()
    if not qpr_table.exists():
        raise FileNotFoundError(f"Q_pr table not found: {qpr_table}")
    qpr_lookup_fn = tables.load_qpr_table(qpr_table)
    qpr_counter = QPrCounter(qpr_lookup_fn)

    phi_fn, phi_origin = resolve_phi_function(args.phi_table)

    rho_p = float(args.rho_p if args.rho_p is not None else cfg.material.rho)
    s_min_config = float(args.s_min if args.s_min is not None else cfg.sizes.s_min)
    s_max = float(cfg.sizes.s_max)
    n_bins = int(cfg.sizes.n_bins)
    alpha = float(cfg.psd.alpha)
    wavy_strength = float(cfg.psd.wavy_strength)
    s_ref = s_min_config

    sub_params_template = SublimationParams(**cfg.sinks.sub_params.model_dump())

    ctx = RuntimeContext(
        cfg=cfg,
        qpr_lookup=qpr_counter,
        phi_fn=phi_fn,
        phi_origin=phi_origin,
        sigma_func=resolve_sigma_function(cfg),
        rho_p=rho_p,
        s_min_config=s_min_config,
        s_max=s_max,
        n_bins=n_bins,
        alpha=alpha,
        wavy_strength=wavy_strength,
        n_steps=int(args.n_step),
        s_ref=s_ref,
        beta_threshold=float(args.beta_thr),
        sink_mode=cfg.sinks.mode,
        enable_sublimation=cfg.sinks.enable_sublimation,
        enable_gas_drag=cfg.sinks.enable_gas_drag,
        rho_gas=float(cfg.sinks.rho_g),
        sub_params_template=sub_params_template,
        use_tcoll=cfg.surface.use_tcoll,
        logger=logger,
    )

    r_values = np.linspace(args.rmin, args.rmax, args.rnum)
    T_values = np.linspace(args.tmin, args.tmax, args.tnum)
    beta_raw_map = np.zeros((len(T_values), len(r_values)))
    beta_eff_map = np.zeros_like(beta_raw_map)

    results: list[BetaCellResult] = []
    dt_warning_cells = 0

    logger.info("Config: %s", args.config.resolve())
    logger.info("Q_pr table: %s", qpr_table)
    logger.info("Φ source: %s", phi_origin)
    logger.info("Grid: r=[%.2f, %.2f] N=%d; T=[%.0f, %.0f] N=%d", r_values[0], r_values[-1], len(r_values), T_values[0], T_values[-1], len(T_values))

    for j, T_val in enumerate(T_values):
        for i, r_val in enumerate(r_values):
            cell = evaluate_cell(r_val, T_val, ctx)
            results.append(cell)
            beta_raw_map[j, i] = cell.beta_raw
            beta_eff_map[j, i] = cell.beta_eff
            if cell.dt_ratio > 1.0:
                dt_warning_cells += 1
                logger.warning(
                    "dt/t_blow exceeds 0.05 at r/R_M=%.3f T=%.0f K (ratio=%.2f)",
                    r_val,
                    T_val,
                    cell.dt_ratio,
                )

    outdir = args.outdir.resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(
        {
            "r_RM": [row.r_RM for row in results],
            "T_M": [row.T_M for row in results],
            "beta_raw": [row.beta_raw for row in results],
            "beta_eff": [row.beta_eff for row in results],
            "qpr_used": [row.qpr_used for row in results],
            "tau_final": [row.tau_final for row in results],
            "phi_used": [row.phi_used for row in results],
            "s_min_config": [row.s_min_config for row in results],
            "a_blow_final": [row.a_blow_final for row in results],
        }
    )
    df.to_csv(outdir / "beta_map.csv", index=False)
    logger.info("Wrote CSV to %s", outdir / "beta_map.csv")

    build_heatmap(
        beta_raw_map,
        r_values,
        T_values,
        ctx.beta_threshold,
        "β_raw",
        outdir / "fig_beta_raw.png",
    )
    logger.info("Wrote β_raw heatmap to %s", outdir / "fig_beta_raw.png")

    build_heatmap(
        beta_eff_map,
        r_values,
        T_values,
        ctx.beta_threshold,
        "β_eff",
        outdir / "fig_beta_eff.png",
    )
    logger.info("Wrote β_eff heatmap to %s", outdir / "fig_beta_eff.png")

    write_readme(
        outdir,
        ctx,
        args.config.resolve(),
        qpr_table,
        phi_origin,
        beta_raw_map,
        beta_eff_map,
        r_values,
        T_values,
        dt_warning_cells,
        len(results),
        qpr_counter,
    )
    logger.info("Readme written to %s", outdir / "README.md")


if __name__ == "__main__":
    main()
