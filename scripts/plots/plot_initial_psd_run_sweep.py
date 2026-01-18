"""Plot the initial PSD for the run_sweep.cmd defaults."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from marsdisk import config_utils, grid, physics_step, run_zero_d
from marsdisk.physics import psd, radiation, tempdriver
from paper.plot_style import apply_default_style


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the initial PSD distribution for run_sweep defaults."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=REPO_ROOT / "scripts" / "runsets" / "common" / "base.yml",
        help="Path to the base config YAML.",
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=REPO_ROOT / "scripts" / "runsets" / "windows" / "overrides.txt",
        help="Path to the overrides file used by run_sweep.cmd.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "figures" / "thesis" / "psd_initial_run_sweep.png",
        help="Output PNG path.",
    )
    return parser.parse_args()


def _load_config(config_path: Path, overrides_path: Path) -> run_zero_d.Config:
    overrides = config_utils.read_overrides_file(overrides_path)
    return run_zero_d.load_config(config_path, overrides=overrides)


def _prepare_qpr_lookup(cfg: run_zero_d.Config) -> float | None:
    rad_cfg = cfg.radiation
    qpr_override = None
    if rad_cfg is not None:
        qpr_cache_cfg = getattr(rad_cfg, "qpr_cache", None)
        round_tol_cfg = getattr(qpr_cache_cfg, "round_tol", None) if qpr_cache_cfg is not None else None
        radiation.configure_qpr_cache(
            enabled=bool(getattr(qpr_cache_cfg, "enabled", True)) if qpr_cache_cfg is not None else True,
            maxsize=int(getattr(qpr_cache_cfg, "maxsize", 1024)) if qpr_cache_cfg is not None else 1024,
            round_tol=float(round_tol_cfg) if round_tol_cfg is not None and float(round_tol_cfg) > 0.0 else None,
        )
        radiation.configure_qpr_fallback(strict=bool(getattr(rad_cfg, "qpr_strict", False)))
        qpr_override = getattr(rad_cfg, "Q_pr", None)
        if rad_cfg.qpr_table_resolved is not None:
            radiation.load_qpr_table(rad_cfg.qpr_table_resolved)
    return qpr_override


def _initial_psd_state(cfg: run_zero_d.Config) -> dict:
    rho_used = float(getattr(cfg.material, "rho", 3000.0))
    r_m, _, _ = config_utils.resolve_reference_radius(cfg)
    Omega = grid.omega_kepler(r_m)
    t_orb = 2.0 * np.pi / Omega

    qpr_override = _prepare_qpr_lookup(cfg)
    temp_runtime = tempdriver.resolve_temperature_driver(cfg.radiation, t_orb=t_orb)
    T_use = temp_runtime.initial_value

    s_min_config = float(cfg.sizes.s_min)
    rad_init = physics_step.compute_radiation_parameters(
        s_min_config,
        rho_used,
        T_use,
        qpr_override=qpr_override,
    )
    a_blow = float(rad_init.a_blow)
    psd_floor_mode = getattr(getattr(cfg.psd, "floor", None), "mode", "fixed")
    if str(psd_floor_mode).lower() == "none":
        s_min_effective = s_min_config
    else:
        s_min_effective = float(max(s_min_config, a_blow))

    psd_state = psd.update_psd_state(
        s_min=s_min_effective,
        s_max=cfg.sizes.s_max,
        alpha=cfg.psd.alpha,
        wavy_strength=cfg.psd.wavy_strength,
        n_bins=cfg.sizes.n_bins,
        rho=rho_used,
    )

    s0_mode_value = str(getattr(cfg.initial, "s0_mode", "upper") or "upper").lower()
    if s0_mode_value == "mono":
        n_bins = psd_state["sizes"].size
        s_mono = 1.5
        psd_state["sizes"] = np.full(n_bins, s_mono, dtype=float)
        psd_state["s"] = psd_state["sizes"]
        psd_state["widths"] = np.ones(n_bins, dtype=float)
        psd_state["number"] = np.ones(n_bins, dtype=float)
        psd_state["n"] = psd_state["number"]
        psd_state["edges"] = np.linspace(0.0, float(n_bins), n_bins + 1)
        psd_state["s_min"] = s_mono
        psd_state["s_max"] = s_mono
        psd_state["sizes_version"] = int(psd_state.get("sizes_version", 0)) + 1
    elif s0_mode_value in {"melt_lognormal_mixture", "melt_truncated_powerlaw"}:
        melt_cfg = getattr(cfg.initial, "melt_psd", None)
        if melt_cfg is None:
            raise ValueError("initial.melt_psd must be provided when using melt_* s0_mode")
        if s0_mode_value == "melt_lognormal_mixture":
            mass_weights = psd.mass_weights_lognormal_mixture(
                psd_state["sizes"],
                psd_state["widths"],
                f_fine=getattr(melt_cfg, "f_fine", 0.0),
                s_fine=getattr(melt_cfg, "s_fine", 1.0e-4),
                s_meter=getattr(melt_cfg, "s_meter", 1.5),
                width_dex=getattr(melt_cfg, "width_dex", 0.3),
                s_cut=getattr(melt_cfg, "s_cut_condensation", None),
            )
        else:
            mass_weights = psd.mass_weights_truncated_powerlaw(
                psd_state["sizes"],
                psd_state["widths"],
                alpha_solid=getattr(melt_cfg, "alpha_solid", 3.5),
                s_min_solid=getattr(melt_cfg, "s_min_solid", s_min_effective),
                s_max_solid=getattr(melt_cfg, "s_max_solid", cfg.sizes.s_max),
                s_cut=getattr(melt_cfg, "s_cut_condensation", None),
            )
        psd_state = psd.apply_mass_weights(
            psd_state,
            mass_weights,
            rho=rho_used,
        )
        psd_state["s_min"] = s_min_effective
    elif s0_mode_value != "upper":
        raise ValueError(f"Unknown initial.s0_mode={s0_mode_value!r}")

    psd.ensure_psd_state_contract(psd_state)
    psd.sanitize_and_normalize_number(psd_state, normalize=False)
    return psd_state


def main() -> int:
    args = _parse_args()
    cfg = _load_config(args.config, args.overrides)
    psd_state = _initial_psd_state(cfg)

    sizes = np.asarray(psd_state.get("sizes"), dtype=float)
    number = np.asarray(psd_state.get("number"), dtype=float)
    widths = np.asarray(psd_state.get("widths"), dtype=float)
    if sizes.size == 0 or number.size != sizes.size or widths.size != sizes.size:
        raise RuntimeError("PSD state is empty or inconsistent")

    rho_used = float(psd_state.get("rho", 3000.0))
    mass_per_particle = (4.0 / 3.0) * np.pi * rho_used * (sizes**3)
    mass_proxy = number * (sizes**3) * widths
    total_mass = float(np.sum(mass_proxy))
    if not np.isfinite(total_mass) or total_mass <= 0.0:
        raise RuntimeError("Initial PSD mass weights are invalid")
    mass_fraction = mass_proxy / total_mass

    mask = (
        np.isfinite(mass_per_particle)
        & np.isfinite(mass_fraction)
        & (mass_per_particle > 0.0)
        & (mass_fraction > 0.0)
    )
    mass_per_particle = mass_per_particle[mask]
    mass_fraction = mass_fraction[mask]

    apply_default_style({"figure.figsize": (6.5, 4.0)})
    fig, ax = plt.subplots()
    ax.plot(mass_per_particle, mass_fraction, color="#1f4e79")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("m [kg]")
    ax.set_ylabel("mass fraction per bin [arb]")
    ax.grid(True, which="both", alpha=0.25)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=200)
    plt.close(fig)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
