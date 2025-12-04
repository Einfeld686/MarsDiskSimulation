"""Orchestrator and CLI for the simplified Mars disk model.

The implementation in this repository is intentionally lightweight yet it
follows the structure laid out in ``AGENTS.md``.  The module offers two
interfaces:

``step`` / ``run_n_steps``
    Legacy helpers used in the unit tests and documentation.  These provide a
    minimal coupling between the optical-depth clipping (S0) and the surface
    layer evolution (S1).

``main``
    Command line entry point invoked via ``python -m marsdisk.run``.  It reads
    a YAML configuration, constructs an initial particle size distribution and
    evolves the coupled S0/S1 system for a fixed number of steps.  The run
    writes Parquet, JSON and CSV outputs and logs a few key diagnostics such as
    the blow-out size ``a_blow`` and the opacity ``kappa``.
"""
# Phase7リサーチ概要:
# - surface.step_surface は Σ_surf を暗黙Eulerで進め、outflux=Sigma_new*Omega（放射圧）、sink_flux=Sigma_new/t_sink を返す; t_blow=1/Omega は内部評価 (marsdisk/physics/surface.py)。
# - run_zero_d 内では t_blow=chi_blow_eff/Omega を毎ステップ再評価し、Wyatt型 t_coll=1/(Omega*tau) は collisions_active かつ tau>TAU_MIN のとき surface._safe_tcoll 由来で使われる。
# - 遮蔽は shielding.effective_kappa/sigma_tau1 をサブステップ直前に適用し、kappa_eff と sigma_tau1_limit を保持したまま step_surface へ渡し diagnostics にも流す。
# - writer.write_parquet/write_orbit_rollup は DataFrame をそのままシリアライズし、units/definitions は writer.write_parquet 内で管理。summary/mass_budget は run_zero_d 終端で writer.write_summary/write_mass_budget が出力。
# - blowout_gate_factor は _compute_gate_factor 由来で t_blow と t_solid（昇華 or 衝突競合）から計算され、tau_gate_blocked による強制遮断は enable_blowout_step を false にして outflux=0 とする。τゲートは radiation.tau_gate.enable でオン。
# - docs/devnotes には phase3/phase5/phase6 のメモと phase7_minimal_diagnostics があり、命名・互換方針・テスト観点の参照先となっている。
from __future__ import annotations

import argparse
import copy
import logging
import math
import random
import shutil
import subprocess
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd
import numpy as np

from . import grid
from .schema import Config
from .physics import (
    psd,
    surface,
    radiation,
    sinks,
    supply,
    initfields,
    shielding,
    sizes,
    tempdriver,
    phase as phase_mod,
    smol,
    dynamics,
    collide,
    collisions_smol,
)
from .io import writer, tables
from .physics.sublimation import SublimationParams, p_sat, grain_temperature_graybody, sublimation_sink_from_dsdt
from . import constants

logger = logging.getLogger(__name__)
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
MAX_STEPS = 5000
TAU_MIN = 1e-12
KAPPA_MIN = 1e-12
DEFAULT_SEED = 12345
MASS_BUDGET_TOLERANCE_PERCENT = 0.5
SINK_REF_SIZE = 1e-6
FAST_BLOWOUT_RATIO_THRESHOLD = 3.0
FAST_BLOWOUT_RATIO_STRICT = 10.0
PHASE7_SCHEMA_VERSION = "phase7-minimal-v1"


def _parse_override_value(raw: str) -> Any:
    """Return a Python value parsed from a CLI override string."""

    text = raw.strip()
    lower = text.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    if lower in {"none", "null"}:
        return None
    if lower in {"nan"}:
        return float("nan")
    if lower in {"inf", "+inf", "+infinity", "infinity"}:
        return float("inf")
    if lower in {"-inf", "-infinity"}:
        return float("-inf")
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            pass
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    return text


def _apply_overrides_dict(payload: Dict[str, Any], overrides: Sequence[str]) -> Dict[str, Any]:
    """Apply dotted-path overrides to a configuration dictionary."""

    if not overrides:
        return payload
    for item in overrides:
        if not isinstance(item, str):  # pragma: no cover - defensive
            continue
        key, sep, value_str = item.partition("=")
        if not sep:
            raise ValueError(f"Invalid override '{item}'; expected path=value")
        path = key.strip()
        if not path:
            raise ValueError(f"Invalid override '{item}'; empty path")
        if path.startswith("physics."):
            path = path[len("physics.") :]
        parts = [segment for segment in path.split(".") if segment]
        if not parts:
            raise ValueError(f"Invalid override '{item}'; empty path")
        target: Any = payload
        for segment in parts[:-1]:
            if isinstance(target, dict):
                if segment not in target or target[segment] is None:
                    target[segment] = {}
                target = target[segment]
            else:
                raise TypeError(
                    f"Cannot traverse into non-mapping for override '{item}' at '{segment}'"
                )
        final_key = parts[-1]
        value = _parse_override_value(value_str)
        if isinstance(target, dict):
            target[final_key] = value
        else:
            raise TypeError(f"Cannot set override '{item}'; target is not a mapping")
    return payload


def _merge_physics_section(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Inline the optional ``physics`` mapping into the root config tree."""

    if not isinstance(payload, dict):  # pragma: no cover - defensive guard
        return payload
    physics_block = payload.pop("physics", None)
    if isinstance(physics_block, dict):
        for key, value in physics_block.items():
            target_key = "physics_mode" if key == "mode" else key
            if target_key in payload:
                logger.debug(
                    "load_config: skipping physics.%s because top-level key exists",
                    target_key,
                )
                continue
            payload[target_key] = value
    return payload


def _safe_float(value: Any) -> Optional[float]:
    """Return ``value`` cast to float when finite, otherwise ``None``."""

    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _derive_seed_components(cfg: Config) -> str:
    parts: list[str] = []
    parts.append(f"geometry.r={getattr(cfg.geometry, 'r', None)!r}")
    if cfg.disk is not None:
        parts.append(
            f"disk.r_in_RM={cfg.disk.geometry.r_in_RM!r},r_out_RM={cfg.disk.geometry.r_out_RM!r}"
        )
    parts.append(f"temps.T_M={cfg.temps.T_M!r}")
    parts.append(f"initial.mass_total={cfg.initial.mass_total!r}")
    return "|".join(parts)


def _resolve_seed(cfg: Config) -> tuple[int, str, str]:
    """Return the RNG seed, seed expression description, and basis."""

    if cfg.dynamics.rng_seed is not None:
        seed_val = int(cfg.dynamics.rng_seed)
        return seed_val, "cfg.dynamics.rng_seed", "user"

    basis = _derive_seed_components(cfg)
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()
    seed_val = int(digest[:8], 16) % (2**31)
    safe_basis = basis.replace("'", r"\'")
    expr = f"sha256('{safe_basis}') % 2**31"
    return seed_val, expr, basis


def _auto_chi_blow(beta: float, qpr: float) -> float:
    """Return an automatic chi_blow scaling based on β and ⟨Q_pr⟩."""

    if not math.isfinite(beta) or beta <= 0.0:
        beta = 0.5
    if not math.isfinite(qpr) or qpr <= 0.0:
        qpr = 1.0
    beta_ratio = beta / 0.5
    chi_beta = 1.0 / (1.0 + 0.5 * (beta_ratio - 1.0))
    chi_beta = max(0.1, chi_beta)
    chi_qpr = min(max(qpr, 0.5), 1.5)
    chi = chi_beta * chi_qpr
    return float(min(max(chi, 0.5), 2.0))


def _fast_blowout_correction_factor(ratio: float) -> float:
    """Return the effective loss fraction ``f_fast = 1 - exp(-Δt/t_blow)``.

    This quantity represents the integrated hazard of an exponential decay
    process over a finite step ``Δt``.  It is bounded within ``[0, 1]`` and
    captures the fraction of the surface reservoir removed by blow-out during
    the step when the rate is resolved exactly.
    """

    if ratio <= 0.0 or math.isinf(ratio):
        return 0.0 if ratio <= 0.0 else 1.0
    # numerically stable evaluation of 1 - exp(-ratio)
    value = -math.expm1(-ratio)
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _compute_gate_factor(t_blow: Optional[float], t_solid: Optional[float]) -> float:
    """Return gate coefficient f_gate=t_solid/(t_solid+t_blow) clipped to [0,1]."""

    if t_blow is None or t_solid is None:
        return 1.0
    try:
        t_blow_val = float(t_blow)
        t_solid_val = float(t_solid)
    except (TypeError, ValueError):
        return 1.0
    if not (math.isfinite(t_blow_val) and math.isfinite(t_solid_val)):
        return 1.0
    if t_blow_val <= 0.0 or t_solid_val <= 0.0:
        return 1.0
    factor = t_solid_val / (t_solid_val + t_blow_val)
    if factor < 0.0:
        return 0.0
    if factor > 1.0:
        return 1.0
    return factor


def _normalise_single_process_mode(value: Any) -> str:
    """Return the canonical single-process mode string."""

    if value is None:
        return "off"
    text = str(value).strip().lower()
    if text in {"", "off", "none", "default", "full", "both"}:
        return "off"
    if text in {"sublimation_only", "sublimation"}:
        return "sublimation_only"
    if text in {"collisions_only", "collisional_only", "collision_only"}:
        return "collisions_only"
    logger.warning("Unknown single_process_mode=%s; defaulting to 'off'", value)
    return "off"


def _normalise_physics_mode(value: Any) -> str:
    """Return the canonical physics.mode string."""

    if value is None:
        return "default"
    text = str(value).strip().lower()
    if text in {"", "default", "off", "none", "full", "both"}:
        return "default"
    if text in {"sublimation_only", "sublimation"}:
        return "sublimation_only"
    if text in {"collisions_only", "collisional_only", "collision_only"}:
        return "collisions_only"
    logger.warning("Unknown physics_mode=%s; defaulting to 'default'", value)
    return "default"


def _physics_mode_from_single_process(mode: str) -> str:
    """Map the internal single-process flag to the user-facing physics mode."""

    if mode == "sublimation_only":
        return "sublimation_only"
    if mode == "collisions_only":
        return "collisions_only"
    return "default"


def _clone_config(cfg: Config) -> Config:
    """Return a deep copy of a configuration object."""

    if hasattr(cfg, "model_copy"):  # pydantic v2
        return cfg.model_copy(deep=True)  # type: ignore[attr-defined]
    return cfg.copy(deep=True)  # type: ignore[attr-defined]


def _resolve_time_grid(numerics: Any, Omega: float, t_orb: float) -> tuple[float, float, float, int, Dict[str, Any]]:
    """Return (t_end, dt_nominal, dt_step, n_steps, info) for the integrator."""

    if numerics.t_end_orbits is not None:
        t_end = float(numerics.t_end_orbits) * t_orb
        t_end_basis = "t_end_orbits"
        t_end_input = float(numerics.t_end_orbits)
    elif numerics.t_end_years is not None:
        t_end = float(numerics.t_end_years) * SECONDS_PER_YEAR
        t_end_basis = "t_end_years"
        t_end_input = float(numerics.t_end_years)
    else:  # pragma: no cover - validated upstream, safeguard for runtime configs
        raise ValueError("numerics must provide t_end_years or t_end_orbits")

    if not math.isfinite(t_end) or t_end <= 0.0:
        raise ValueError("Resolved integration duration must be positive and finite")

    dt_input = numerics.dt_init
    dt_mode = "auto" if isinstance(dt_input, str) and dt_input.lower() == "auto" else "explicit"
    dt_sources: Dict[str, float] = {}
    t_blow_nominal = float("inf")
    if Omega > 0.0 and math.isfinite(Omega):
        t_blow_nominal = 1.0 / Omega

    if dt_mode == "auto":
        candidates: List[float] = []
        if math.isfinite(t_blow_nominal) and t_blow_nominal > 0.0:
            value = 0.05 * t_blow_nominal
            dt_sources["0.05*t_blow"] = value
            if value > 0.0 and math.isfinite(value):
                candidates.append(value)
        value = t_end / 200.0
        dt_sources["t_end/200"] = value
        if value > 0.0 and math.isfinite(value):
            candidates.append(value)
        if not candidates:
            dt_nominal = t_end
        else:
            dt_nominal = min(candidates)
        dt_nominal = max(min(dt_nominal, t_end), 1.0e-9)
    else:
        dt_nominal = float(dt_input)
        if not math.isfinite(dt_nominal) or dt_nominal <= 0.0:
            raise ValueError("dt_init must be positive and finite")
        dt_sources["explicit"] = dt_nominal

    n_steps = max(1, int(math.ceil(t_end / max(dt_nominal, 1.0e-9))))
    dt_step = t_end / n_steps

    info = {
        "t_end_basis": t_end_basis,
        "t_end_input": t_end_input,
        "t_end_seconds": t_end,
        "dt_mode": dt_mode,
        "dt_input": dt_input,
        "dt_sources": dt_sources,
        "dt_nominal": dt_nominal,
        "dt_step": dt_step,
        "t_blow_nominal": t_blow_nominal if math.isfinite(t_blow_nominal) else None,
        "n_steps": n_steps,
    }
    return t_end, dt_nominal, dt_step, n_steps, info


@dataclass
class _Phase5VariantResult:
    """Artifacts recorded for a variant within the Phase 5 comparison."""

    variant: str
    mode: str
    outdir: Path
    summary: Dict[str, Any]
    run_config: Dict[str, Any]
    series_paths: Dict[str, Path]
    mass_budget_path: Optional[Path]
    orbit_rollup_path: Optional[Path]


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _hash_payload(payload: Mapping[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _prepare_phase5_variants(compare_cfg: Any) -> List[Dict[str, str]]:
    """Return normalized variant specifications or raise when insufficient."""

    if compare_cfg is None:
        raise ValueError("phase5.compare must be configured when requesting comparison runs")

    def _normalize_label(label: Optional[str], mode: str) -> str:
        return str(label) if label not in (None, "") else mode

    mode_a_raw = getattr(compare_cfg, "mode_a", None)
    mode_b_raw = getattr(compare_cfg, "mode_b", None)
    if mode_a_raw is None or mode_b_raw is None:
        raise ValueError("phase5.compare.mode_a and mode_b must be provided for comparison runs")

    mode_a = _normalise_single_process_mode(mode_a_raw)
    mode_b = _normalise_single_process_mode(mode_b_raw)
    if mode_a == "off" or mode_b == "off":
        raise ValueError("phase5.compare modes must specify active single-process modes (not 'off')")

    label_a = _normalize_label(getattr(compare_cfg, "label_a", None), mode_a)
    label_b = _normalize_label(getattr(compare_cfg, "label_b", None), mode_b)
    return [
        {"mode": mode_a, "label": label_a},
        {"mode": mode_b, "label": label_b},
    ]


# ---------------------------------------------------------------------------
# Legacy helpers retained for backward compatibility
# ---------------------------------------------------------------------------


@dataclass
class RunConfig:
    """Configuration parameters for a zero-dimensional run."""

    r: float                # orbital radius [m]
    Omega: float            # Keplerian frequency [s^-1]
    prod_rate: float        # production rate of sub-blow-out grains
    area: float | None = None  # surface area factor

    def __post_init__(self) -> None:
        if self.area is None:
            self.area = math.pi * self.r ** 2


@dataclass
class RunState:
    """State variables evolved during the run."""

    sigma_surf: float
    psd_state: Dict[str, Any]
    M_loss_cum: float = 0.0
    time: float = 0.0


@dataclass
class ZeroDHistory:
    """Per-step history bundle used by the full-feature zero-D driver."""

    records: List[Dict[str, Any]] = field(default_factory=list)
    psd_hist_records: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    mass_budget: List[Dict[str, float]] = field(default_factory=list)
    step_diag_records: List[Dict[str, Any]] = field(default_factory=list)
    debug_records: List[Dict[str, Any]] = field(default_factory=list)
    orbit_rollup_rows: List[Dict[str, float]] = field(default_factory=list)
    temperature_track: List[float] = field(default_factory=list)
    beta_track: List[float] = field(default_factory=list)
    ablow_track: List[float] = field(default_factory=list)
    gate_factor_track: List[float] = field(default_factory=list)
    t_solid_track: List[float] = field(default_factory=list)
    phase7_total_rate_track: List[float] = field(default_factory=list)
    phase7_total_rate_time_track: List[float] = field(default_factory=list)
    phase7_ts_ratio_track: List[float] = field(default_factory=list)
    mass_budget_violation: Optional[Dict[str, float]] = None
    violation_triggered: bool = False
    tau_gate_block_time: float = 0.0
    total_time_elapsed: float = 0.0


def step(config: RunConfig, state: RunState, dt: float) -> Dict[str, float]:
    """Advance the coupled S0/S1 system by one time-step.

    This is a lean helper for tests and tutorials; it does not exercise the
    full zero-D driver, PSD floor handling, or the rich I/O used by
    :func:`run_zero_d`.
    """

    kappa_surf = psd.compute_kappa(state.psd_state)
    tau = kappa_surf * state.sigma_surf
    kappa_eff, sigma_tau1 = shielding.apply_shielding(kappa_surf, tau, 0.0, 0.0)
    if kappa_eff <= KAPPA_MIN:
        sigma_tau1 = None
    res = surface.step_surface_density_S1(
        state.sigma_surf,
        config.prod_rate,
        dt,
        config.Omega,
        sigma_tau1=sigma_tau1,
    )
    state.sigma_surf = res.sigma_surf

    t_blow = 1.0 / config.Omega
    # kg/s -> M_Mars/s
    M_out_dot = (res.outflux * config.area) / constants.M_MARS
    state.M_loss_cum += M_out_dot * dt
    state.time += dt

    record = {
        "time": state.time,
        "dt": dt,
        "outflux_surface": res.outflux,
        "sink_flux_surface": res.sink_flux,
        "t_blow": t_blow,
        "M_out_dot": M_out_dot,  # M_Mars/s
        "M_loss_cum": state.M_loss_cum,  # M_Mars
    }
    logger.info(
        "run.step: t=%e t_blow=%e outflux=%e M_out_dot[M_Mars/s]=%e M_loss_cum[M_Mars]=%e",
        state.time,
        t_blow,
        res.outflux,
        M_out_dot,
        state.M_loss_cum,
    )
    return record


def run_n_steps(
    config: RunConfig,
    state: RunState,
    n: int,
    dt: float,
    out_dir: Path | None = None,
) -> pd.DataFrame:
    """Run ``n`` steps and optionally serialise results.

    Intended for quick checks; the production-oriented :func:`run_zero_d`
    performs full configuration validation, adaptive floors, and richer output.
    """

    records: List[Dict[str, float]] = []
    for _ in range(n):
        records.append(step(config, state, dt))

    df = pd.DataFrame(records)
    if out_dir is not None:
        writer.write_parquet(df, Path(out_dir) / "series" / "run.parquet")
        summary = {"M_loss": state.M_loss_cum}  # M_Mars
        writer.write_summary(summary, Path(out_dir) / "summary.json")
    return df


# ---------------------------------------------------------------------------
# Configuration loading and CLI run
# ---------------------------------------------------------------------------


def load_config(path: Path, overrides: Optional[Sequence[str]] = None) -> Config:
    """Load a YAML configuration file into a :class:`Config` instance."""

    from ruamel.yaml import YAML

    yaml = YAML(typ="safe")
    source_path = Path(path).resolve()
    with source_path.open("r", encoding="utf-8") as fh:
        data = yaml.load(fh)
    if overrides:
        if not isinstance(data, dict):
            raise TypeError(
                "Configuration overrides require the YAML root to be a mapping"
            )
        data = _apply_overrides_dict(data, overrides)
    if isinstance(data, dict):
        data = _merge_physics_section(data)
    cfg = Config(**data)
    try:
        setattr(cfg, "_source_path", source_path)
    except Exception:
        pass
    return cfg


def _gather_git_info() -> Dict[str, Any]:
    """Return basic git metadata for provenance recording."""

    repo_root = Path(__file__).resolve().parents[1]
    info: Dict[str, Any] = {}
    try:
        info["commit"] = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        info["commit"] = "unknown"
    try:
        info["branch"] = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root, text=True
        ).strip()
    except Exception:
        info["branch"] = "unknown"
    try:
        status = subprocess.check_output(
            ["git", "status", "--short"], cwd=repo_root, text=True
        )
        info["dirty"] = bool(status.strip())
    except Exception:
        info["dirty"] = None
    return info


class MassBudgetViolationError(RuntimeError):
    """Raised when the mass budget tolerance is exceeded."""


def _resolve_single_process_choice(
    cli_mode: Optional[str],
    physics_mode: Optional[str],
    cfg_single_process_mode: Optional[str],
    legacy_mode: Optional[str],
) -> tuple[str, str]:
    """Return (mode, source) respecting CLI > physics.mode > single_process > legacy priority."""

    if cli_mode is not None:
        return _normalise_single_process_mode(cli_mode), "cli"
    physics_norm = _normalise_physics_mode(physics_mode)
    if physics_norm != "default":
        resolved = _normalise_single_process_mode(physics_norm)
        return resolved, "physics_mode"
    config_norm = _normalise_single_process_mode(cfg_single_process_mode)
    if config_norm != "off":
        return config_norm, "single_process_mode"
    legacy_norm = _normalise_single_process_mode(legacy_mode)
    if legacy_norm != "off":
        return legacy_norm, "modes"
    return "off", "default"


def _write_zero_d_history(
    cfg: Config,
    df: pd.DataFrame,
    history: ZeroDHistory,
    *,
    step_diag_enabled: bool,
    step_diag_format: str,
    step_diag_path_cfg: Optional[Path],
    orbit_rollup_enabled: bool,
    phase7_enabled: bool,
) -> None:
    """Persist time series, diagnostics, and rollups for a zero-D run."""

    outdir = Path(cfg.io.outdir)
    step_diag_path = None
    if step_diag_enabled:
        if step_diag_path_cfg is not None:
            step_diag_path = Path(step_diag_path_cfg)
            if not step_diag_path.is_absolute():
                step_diag_path = outdir / step_diag_path
        else:
            ext = "jsonl" if step_diag_format == "jsonl" else "csv"
            step_diag_path = outdir / "series" / f"step_diagnostics.{ext}"
    writer.write_parquet(df, outdir / "series" / "run.parquet")
    if history.psd_hist_records:
        psd_hist_df = pd.DataFrame(history.psd_hist_records)
        writer.write_parquet(psd_hist_df, outdir / "series" / "psd_hist.parquet")
    if history.diagnostics:
        diag_df = pd.DataFrame(history.diagnostics)
        writer.write_parquet(diag_df, outdir / "series" / "diagnostics.parquet")
    if step_diag_enabled and step_diag_path is not None:
        writer.write_step_diagnostics(history.step_diag_records, step_diag_path, fmt=step_diag_format)
    if orbit_rollup_enabled:
        rows_for_rollup = history.orbit_rollup_rows
        required_phase7_cols = {
            "mloss_blowout_rate",
            "mloss_sink_rate",
            "mloss_total_rate",
            "ts_ratio",
            "dt",
            "time",
            "blowout_gate_factor",
        }
        if phase7_enabled and rows_for_rollup and not df.empty and required_phase7_cols.issubset(set(df.columns)):
            df_end = df["time"].to_numpy()
            df_start = (df["time"] - df["dt"]).to_numpy()
            blow_rates = df["mloss_blowout_rate"].to_numpy()
            sink_rates = df["mloss_sink_rate"].to_numpy()
            total_rates = df["mloss_total_rate"].to_numpy()
            ts_ratio_series = df["ts_ratio"].to_numpy()
            gate_factor_series = df["blowout_gate_factor"].to_numpy()

            def _safe_peak(arr: np.ndarray, mask: np.ndarray) -> float:
                subset = arr[mask]
                subset = subset[np.isfinite(subset)]
                if subset.size == 0:
                    return float("nan")
                return float(np.max(subset))

            def _safe_median(arr: np.ndarray, mask: np.ndarray) -> float:
                subset = arr[mask]
                subset = subset[np.isfinite(subset)]
                if subset.size == 0:
                    return float("nan")
                return float(np.median(subset))

            gate_factor_median_all = _safe_median(
                gate_factor_series,
                np.ones_like(gate_factor_series, dtype=bool),
            )

            rows_for_rollup = []
            orbit_start_time = 0.0
            for row in history.orbit_rollup_rows:
                orbit_end_time = _safe_float(row.get("time_s_end"))
                if orbit_end_time is None:
                    t_orb_row = _safe_float(row.get("t_orb_s"))
                    orbit_end_time = orbit_start_time + (t_orb_row if t_orb_row is not None else 0.0)
                mask = (df_end > orbit_start_time) & (df_start <= orbit_end_time)
                blow_peak = _safe_peak(blow_rates, mask)
                sink_peak = _safe_peak(sink_rates, mask)
                total_peak = _safe_peak(total_rates, mask)
                ts_ratio_med = _safe_median(ts_ratio_series, mask)
                gate_factor_med = _safe_median(gate_factor_series, mask)
                if not math.isfinite(gate_factor_med):
                    gate_factor_med = gate_factor_median_all
                row_aug = dict(row)
                row_aug["mloss_blowout_rate_mean"] = row.get("M_out_per_orbit")
                row_aug["mloss_sink_rate_mean"] = row.get("M_sink_per_orbit")
                row_aug["mloss_total_rate_mean"] = row.get("M_loss_per_orbit")
                row_aug["mloss_blowout_rate_peak"] = blow_peak
                row_aug["mloss_sink_rate_peak"] = sink_peak
                row_aug["mloss_total_rate_peak"] = total_peak
                row_aug["ts_ratio_median"] = ts_ratio_med
                row_aug["gate_factor_median"] = gate_factor_med
                rows_for_rollup.append(row_aug)
                orbit_start_time = orbit_end_time
        writer.write_orbit_rollup(rows_for_rollup, outdir / "orbit_rollup.csv")


def run_zero_d(
    cfg: Config,
    *,
    enforce_mass_budget: bool = False,
    single_process_override: Optional[str] = None,
    single_process_source: Optional[str] = None,
) -> None:
    """Execute the full-feature zero-dimensional simulation.

    This is the production driver: it resolves configuration, builds PSD
    floors, advances the coupled physics, and emits the on-disk artifacts.
    The lightweight :func:`step` / :func:`run_n_steps` helpers remain available
    for tutorial or unit-test scenarios.

    Parameters
    ----------
    cfg:
        Parsed configuration object.
    """

    config_source_path_raw = getattr(cfg, "_source_path", None)
    config_source_path: Optional[Path] = None
    if config_source_path_raw:
        try:
            config_source_path = Path(config_source_path_raw).resolve()
        except Exception:
            config_source_path = None

    scope_cfg = getattr(cfg, "scope", None)
    process_cfg = getattr(cfg, "process", None)
    modes_cfg = getattr(cfg, "modes", None)
    physics_mode_cfg = getattr(cfg, "physics_mode", None)
    single_process_mode_cfg = getattr(cfg, "single_process_mode", None)
    legacy_single_process = None
    if modes_cfg is not None:
        legacy_single_process = getattr(modes_cfg, "single_process", None)
    mode_input_cli = single_process_override
    mode_input_cfg = physics_mode_cfg
    mode_input_legacy = legacy_single_process
    single_process_mode_resolved, single_process_mode_source = _resolve_single_process_choice(
        mode_input_cli,
        mode_input_cfg,
        single_process_mode_cfg,
        mode_input_legacy,
    )
    if single_process_source:
        single_process_mode_source = single_process_source
    single_process_mode = single_process_mode_resolved
    physics_mode = _physics_mode_from_single_process(single_process_mode)
    physics_mode_source = single_process_mode_source
    scope_region = getattr(scope_cfg, "region", "inner") if scope_cfg else "inner"
    analysis_window_years = float(getattr(scope_cfg, "analysis_years", 2.0)) if scope_cfg else 2.0
    if scope_region != "inner":
        raise ValueError("scope.region must be 'inner' during the inner-disk campaign")
    primary_process_cfg = getattr(process_cfg, "primary", "collisions_only") if process_cfg else "collisions_only"
    primary_process = primary_process_cfg
    single_process_requested = single_process_mode in {"sublimation_only", "collisions_only"}
    if single_process_requested:
        primary_process = single_process_mode
    process_fields_set = set(getattr(process_cfg, "__fields_set__", set())) if process_cfg else set()
    primary_field_explicit = "primary" in process_fields_set
    primary_scenario = "combined"
    if single_process_requested:
        primary_scenario = single_process_mode
    elif primary_field_explicit:
        primary_scenario = primary_process_cfg
    state_tagging_enabled = bool(
        getattr(getattr(process_cfg, "state_tagging", None), "enabled", False)
    )
    state_phase_tag = "solid" if state_tagging_enabled else None
    inner_scope_flag = scope_region == "inner"
    radiation_field = "mars"
    radiation_cfg = getattr(cfg, "radiation", None)
    solar_rp_requested = False
    mars_rp_enabled_cfg = True
    if radiation_cfg is not None:
        source_raw = getattr(radiation_cfg, "source", "mars")
        radiation_field = str(source_raw).lower()
        mars_rp_enabled_cfg = bool(getattr(radiation_cfg, "use_mars_rp", True))
        solar_rp_requested = bool(getattr(radiation_cfg, "use_solar_rp", False))
        if radiation_field == "off":
            mars_rp_enabled_cfg = False
    if not mars_rp_enabled_cfg:
        radiation_field = "off"
    if solar_rp_requested:
        logger.info("radiation: solar radiation toggle requested but disabled (gas-poor scope)")
    if cfg.numerics.t_end_years is None and cfg.numerics.t_end_orbits is None:
        cfg.numerics.t_end_years = analysis_window_years
    logger.info(
        "scope=%s, window=%.3f yr, radiation=%s, primary=%s, scenario=%s%s",
        scope_region,
        analysis_window_years,
        radiation_field,
        primary_process,
        primary_scenario,
        " (state_tag=solid)" if state_tagging_enabled else "",
    )
    enforce_collisions_only = primary_scenario == "collisions_only"
    enforce_sublimation_only = primary_scenario == "sublimation_only"
    collisions_active = not enforce_sublimation_only
    diagnostics_cfg = getattr(cfg, "diagnostics", None)
    phase7_cfg = getattr(diagnostics_cfg, "phase7", None)
    phase7_enabled = bool(getattr(phase7_cfg, "enable", False))
    phase7_schema_version = getattr(phase7_cfg, "schema_version", PHASE7_SCHEMA_VERSION)

    seed, seed_expr, seed_basis = _resolve_seed(cfg)
    random.seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    e0_effective = cfg.dynamics.e0
    i0_effective = cfg.dynamics.i0
    delta_r_sample = None

    if cfg.dynamics.e_mode == "mars_clearance":
        if cfg.geometry.r is None:
            raise ValueError(
                "dynamics.e_mode='mars_clearance' requires geometry.r in meters"
            )
        a_m = cfg.geometry.r
        dr_min = cfg.dynamics.dr_min_m
        dr_max = cfg.dynamics.dr_max_m
        if dr_min is not None and dr_max is not None:
            if dr_min > dr_max:
                raise ValueError(
                    "dynamics.dr_min_m must be smaller than dynamics.dr_max_m in meters"
                )
            if cfg.dynamics.dr_dist == "uniform":
                delta_r_sample = float(rng.uniform(dr_min, dr_max))
            else:
                if dr_min <= 0.0 or dr_max <= 0.0:
                    raise ValueError(
                        "loguniform Δr sampling requires positive meter bounds"
                    )
                log_min = math.log(dr_min)
                log_max = math.log(dr_max)
                delta_r_sample = float(math.exp(rng.uniform(log_min, log_max)))
        elif dr_min is not None:
            delta_r_sample = float(dr_min)
        elif dr_max is not None:
            delta_r_sample = float(dr_max)
        else:
            raise ValueError(
                "dynamics.dr_min_m or dynamics.dr_max_m must be specified in meters "
                "when using e_mode='mars_clearance'"
            )
        e0_sample = 1.0 - (constants.R_MARS + delta_r_sample) / a_m
        e0_clamped = float(np.clip(e0_sample, 0.0, 0.999999))
        if not math.isclose(e0_clamped, e0_sample, rel_tol=0.0, abs_tol=1e-12):
            logger.warning(
                "Sampled eccentricity %.6f clamped to %.6f to stay within [0, 0.999999]",
                e0_sample,
                e0_clamped,
            )
        e0_effective = e0_clamped
        cfg.dynamics.e0 = e0_effective

    i_center_rad = float(np.deg2rad(cfg.dynamics.obs_tilt_deg))
    spread_rad = float(np.deg2rad(cfg.dynamics.i_spread_deg))
    if cfg.dynamics.i_mode == "obs_tilt_spread":
        if spread_rad > 0.0:
            lower = max(i_center_rad - spread_rad, 0.0)
            upper = min(i_center_rad + spread_rad, 0.5 * np.pi)
            if lower >= upper:
                i_sample = lower
            else:
                i_sample = float(rng.uniform(lower, upper))
        else:
            i_sample = i_center_rad
        i_clamped = float(np.clip(i_sample, 0.0, 0.5 * np.pi))
        if not math.isclose(i_clamped, i_sample, rel_tol=0.0, abs_tol=1e-12):
            logger.warning(
                "Sampled inclination %.6f rad clamped to %.6f rad to stay within [0, pi/2]",
                i_sample,
                i_clamped,
            )
        i0_effective = i_clamped
        cfg.dynamics.i0 = i0_effective

    r_source = "geometry.r"
    if cfg.geometry.r is not None:
        r = cfg.geometry.r
    elif getattr(cfg.geometry, "runtime_orbital_radius_rm", None) is not None:
        r = float(cfg.geometry.runtime_orbital_radius_rm) * constants.R_MARS
        r_source = "geometry.runtime_orbital_radius_rm"
        try:
            cfg.geometry.r = r
        except Exception:
            pass
    elif cfg.disk is not None:
        r = (
            0.5
            * (cfg.disk.geometry.r_in_RM + cfg.disk.geometry.r_out_RM)
            * constants.R_MARS
        )
        r_source = "disk.geometry"
    elif cfg.geometry.r_in is not None:
        r = cfg.geometry.r_in
        r_source = "geometry.r_in"
    else:
        raise ValueError("geometry.r must be provided for 0D runs")
    Omega = grid.omega_kepler(r)
    if Omega <= 0.0:
        raise ValueError("Computed Keplerian frequency must be positive")
    t_orb = 2.0 * math.pi / Omega
    r_RM = r / constants.R_MARS

    qpr_override = None
    qpr_table_path_resolved: Optional[Path] = None
    if cfg.radiation:
        qpr_table_path_resolved = cfg.radiation.qpr_table_resolved
        if qpr_table_path_resolved is not None:
            radiation.load_qpr_table(qpr_table_path_resolved)
        if cfg.radiation.Q_pr is not None:
            qpr_override = cfg.radiation.Q_pr
    active_qpr_table = tables.get_qpr_table_path()
    if qpr_table_path_resolved is None and active_qpr_table is not None:
        qpr_table_path_resolved = active_qpr_table
    if qpr_override is None and qpr_table_path_resolved is None:
        raise RuntimeError(
            "⟨Q_pr⟩ lookup table not initialised. Provide radiation.qpr_table_path "
            "or place a table under marsdisk/io/data."
        )
    temp_runtime = tempdriver.resolve_temperature_driver(cfg.temps, cfg.radiation, t_orb=t_orb)
    T_use = temp_runtime.initial_value
    T_M_source = temp_runtime.source
    logger.info(
        "Mars temperature driver resolved: source=%s mode=%s enabled=%s T_init=%.2f K",
        temp_runtime.source,
        temp_runtime.mode,
        temp_runtime.enabled,
        T_use,
    )
    rho_used = cfg.material.rho

    phi_tau_fn = None
    phi_table_path_resolved: Optional[Path] = None
    shielding_mode_resolved = "psitau"
    if cfg.shielding:
        shielding_mode_resolved = cfg.shielding.mode_resolved
        phi_table_path_resolved = cfg.shielding.table_path_resolved
        if phi_table_path_resolved is not None:
            phi_tau_fn = shielding.load_phi_table(phi_table_path_resolved)
        if shielding_mode_resolved == "off":
            phi_tau_fn = None

    # Initial PSD and associated quantities
    sub_params = SublimationParams(**cfg.sinks.sub_params.model_dump())
    setattr(sub_params, "runtime_orbital_radius_m", r)
    setattr(sub_params, "runtime_t_orb_s", t_orb)
    setattr(sub_params, "runtime_Omega", Omega)
    gas_pressure_pa = float(getattr(sub_params, "P_gas", 0.0) or 0.0)

    phase_cfg = getattr(cfg, "phase", None)
    phase_controller = phase_mod.PhaseEvaluator.from_config(phase_cfg, logger=logger)
    hydro_cfg = getattr(cfg.sinks, "hydro_escape", None)
    tau_gate_cfg = getattr(cfg.radiation, "tau_gate", None) if cfg.radiation else None
    tau_gate_enabled = bool(getattr(tau_gate_cfg, "enable", False)) if tau_gate_cfg else False
    tau_gate_threshold = (
        float(getattr(tau_gate_cfg, "tau_max", 1.0)) if tau_gate_enabled else float("inf")
    )

    def _lookup_qpr(size: float) -> float:
        """Return ⟨Q_pr⟩ for the provided grain size using the active source."""

        size_eff = max(float(size), 1.0e-12)
        if qpr_override is not None:
            return float(qpr_override)
        return float(radiation.qpr_lookup(size_eff, T_use))

    def _resolve_blowout(
        size_floor: float,
        initial: Optional[float] = None,
    ) -> tuple[float, float]:
        """Return (⟨Q_pr⟩, s_blow) respecting the supplied minimum size."""

        if qpr_override is not None:
            qpr_val = float(qpr_override)
            s_blow_val = radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_val)
            return qpr_val, float(max(size_floor, s_blow_val))

        s_eval = float(initial if initial is not None else size_floor)
        s_eval = float(max(size_floor, s_eval, 1.0e-12))
        for _ in range(6):
            qpr_val = float(radiation.qpr_lookup(s_eval, T_use))
            s_blow_val = float(radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_val))
            s_eval = float(max(size_floor, s_blow_val, 1.0e-12))
        qpr_final = float(radiation.qpr_lookup(s_eval, T_use))
        s_blow_final = float(radiation.blowout_radius(rho_used, T_use, Q_pr=qpr_final))
        return qpr_final, float(max(size_floor, s_blow_final))

    def _psd_mass_peak() -> float:
        """Return the size corresponding to the peak mass content."""

        try:
            sizes = np.asarray(psd_state.get("sizes"), dtype=float)
            number = np.asarray(psd_state.get("number"), dtype=float)
        except Exception:
            return float("nan")
        if sizes.size == 0 or number.size != sizes.size:
            return float("nan")
        mass_proxy = sizes**3 * number
        if mass_proxy.size == 0:
            return float("nan")
        idx = int(np.argmax(mass_proxy))
        if idx < 0 or idx >= sizes.size:
            return float("nan")
        return float(sizes[idx])

    blowout_cfg = getattr(cfg, "blowout", None)
    blowout_enabled_cfg = bool(getattr(blowout_cfg, "enabled", True)) if blowout_cfg else True
    blowout_target_phase = str(getattr(blowout_cfg, "target_phase", "solid_only")) if blowout_cfg else "solid_only"
    blowout_layer_mode = str(getattr(blowout_cfg, "layer", "surface_tau_le_1")) if blowout_cfg else "surface_tau_le_1"
    blowout_gate_mode = str(getattr(blowout_cfg, "gate_mode", "none")).lower() if blowout_cfg else "none"
    if blowout_gate_mode not in {"none", "sublimation_competition", "collision_competition"}:
        raise ValueError(f"Unknown blowout.gate_mode={blowout_gate_mode!r}")
    blowout_enabled = blowout_enabled_cfg
    rp_blowout_cfg = getattr(cfg.sinks, "rp_blowout", None)
    rp_blowout_enabled = bool(getattr(rp_blowout_cfg, "enable", True)) if rp_blowout_cfg else True
    blowout_enabled = (
        blowout_enabled
        and collisions_active
        and rp_blowout_enabled
        and mars_rp_enabled_cfg
    )
    if radiation_field == "off":
        blowout_enabled = False
    gate_enabled = blowout_gate_mode != "none"
    if blowout_gate_mode == "collision_competition" and not bool(getattr(cfg.surface, "use_tcoll", True)):
        logger.warning(
            "blowout.gate_mode='collision_competition' requested but surface.use_tcoll=False; gate will ignore collisions"
        )
    freeze_kappa = bool(getattr(cfg.radiation, "freeze_kappa", False)) if cfg.radiation else False
    freeze_sigma = bool(getattr(cfg.surface, "freeze_sigma", False))
    shielding_mode = shielding_mode_resolved
    tau_fixed_cfg: Optional[float] = None
    sigma_tau1_fixed_cfg: Optional[float] = None
    if cfg.shielding is not None:
        tau_fixed_cfg = getattr(cfg.shielding, "fixed_tau1_tau", None)
        sigma_tau1_fixed_cfg = getattr(cfg.shielding, "fixed_tau1_sigma", None)
    psd_floor_mode = getattr(getattr(cfg.psd, "floor", None), "mode", "fixed")
    collision_solver_mode = str(getattr(cfg.surface, "collision_solver", "surface_ode") or "surface_ode")
    if collision_solver_mode not in {"surface_ode", "smol"}:
        raise ValueError(f"Unknown surface.collision_solver={collision_solver_mode!r}")

    s_min_config = cfg.sizes.s_min
    qpr_for_blow, a_blow = _resolve_blowout(s_min_config)
    if psd_floor_mode == "none":
        s_min_effective = float(s_min_config)
    else:
        s_min_effective = max(s_min_config, a_blow)
    s_min_floor_dynamic = float(s_min_effective)
    evolve_min_size_enabled = bool(getattr(cfg.sizes, "evolve_min_size", False))
    s_min_evolved_value = s_min_effective
    s_min_components = {
        "config": float(s_min_config),
        "blowout": float(a_blow),
        "effective": float(s_min_effective),
        "floor_mode": str(psd_floor_mode),
        "floor_dynamic": float(s_min_floor_dynamic),
    }
    if s_min_effective > s_min_config:
        logger.info(
            "Effective s_min raised from config value %.3e m to %.3e m",
            s_min_config,
            s_min_effective,
        )
    psd_state = psd.update_psd_state(
        s_min=s_min_effective,
        s_max=cfg.sizes.s_max,
        alpha=cfg.psd.alpha,
        wavy_strength=cfg.psd.wavy_strength,
        n_bins=cfg.sizes.n_bins,
        rho=rho_used,
    )
    kappa_surf = psd.compute_kappa(psd_state)
    kappa_surf_initial = float(kappa_surf)
    qpr_at_smin_config = _lookup_qpr(s_min_config)
    qpr_mean = _lookup_qpr(s_min_effective)
    beta_at_smin_config = radiation.beta(
        s_min_config, rho_used, T_use, Q_pr=qpr_at_smin_config
    )
    beta_at_smin_effective = radiation.beta(
        s_min_effective, rho_used, T_use, Q_pr=qpr_mean
    )
    beta_threshold = radiation.BLOWOUT_BETA_THRESHOLD
    beta_gate_active = beta_at_smin_effective >= beta_threshold
    case_status = "blowout" if beta_at_smin_config >= beta_threshold else "ok"
    if case_status != "blowout":
        logger.info(
            "Blow-out threshold not met at s_min_config=%.3e m (β=%.3f)",
            s_min_config,
            beta_at_smin_config,
        )
    if not blowout_enabled:
        case_status = "no_blowout"

    if cfg.disk is not None and cfg.inner_disk_mass is not None:
        r_in_d = cfg.disk.geometry.r_in_RM * constants.R_MARS
        r_out_d = cfg.disk.geometry.r_out_RM * constants.R_MARS
        if cfg.inner_disk_mass.use_Mmars_ratio:
            M_in = cfg.inner_disk_mass.M_in_ratio * constants.M_MARS
        else:
            M_in = cfg.inner_disk_mass.M_in_ratio
        sigma_func = initfields.sigma_from_Minner(
            M_in,
            r_in_d,
            r_out_d,
            cfg.disk.geometry.p_index,
        )
        sigma_mid = sigma_func(r)
        kappa_for_init = kappa_surf
        if phi_tau_fn is not None:
            tau_mid = kappa_surf * sigma_mid
            kappa_for_init = shielding.effective_kappa(kappa_surf, tau_mid, phi_tau_fn)
        sigma_surf = initfields.surf_sigma_init(
            sigma_mid,
            kappa_for_init,
            cfg.surface.init_policy,
            sigma_override=cfg.surface.sigma_surf_init_override,
        )
    else:
        sigma_surf = 0.0
    sigma_surf_reference = float(sigma_surf)
    tau_initial = float(kappa_surf_initial * sigma_surf_reference)
    tau_fixed_target = (
        float(tau_fixed_cfg) if tau_fixed_cfg is not None else tau_initial
    )
    sigma_tau1_fixed_target = (
        float(sigma_tau1_fixed_cfg)
        if sigma_tau1_fixed_cfg is not None
        else None
    )
    M_loss_cum = 0.0
    M_sink_cum = 0.0
    M_sublimation_cum = 0.0
    M_hydro_cum = 0.0
    if cfg.disk is not None:
        r_in_d = cfg.disk.geometry.r_in_RM * constants.R_MARS
        r_out_d = cfg.disk.geometry.r_out_RM * constants.R_MARS
        area = math.pi * (r_out_d**2 - r_in_d**2)
    else:
        area = math.pi * r**2
    chi_config_raw = getattr(cfg, "chi_blow", 1.0)
    chi_config = chi_config_raw
    chi_config_str = str(chi_config_raw)
    if isinstance(chi_config, str):
        chi_config_lower = chi_config.lower()
        if chi_config_lower == "auto":
            chi_blow_eff = _auto_chi_blow(beta_at_smin_effective, qpr_mean)
        else:
            raise ValueError("chi_blow string value must be 'auto'")
        chi_config_str = "auto"
    else:
        chi_blow_eff = float(chi_config)
        if chi_blow_eff <= 0.0:
            raise ValueError("chi_blow must be positive")
        chi_config_str = f"{chi_config_raw}"
    chi_blow_eff = float(min(max(chi_blow_eff, 0.5), 2.0))
    t_blow = chi_blow_eff / Omega

    sinks_mode_value = getattr(cfg.sinks, "mode", "sublimation")
    sinks_enabled_cfg = sinks_mode_value != "none"
    sublimation_location_raw = getattr(cfg.sinks, "sublimation_location", "surface")
    sublimation_location = str(sublimation_location_raw or "surface").lower()
    if sublimation_location not in {"surface", "smol", "both"}:
        raise ValueError(f"sinks.sublimation_location must be 'surface', 'smol' or 'both' (got {sublimation_location!r})")
    sublimation_to_surface = sublimation_location in {"surface", "both"}
    sublimation_to_smol = sublimation_location in {"smol", "both"}
    sublimation_enabled_cfg = bool(
        sinks_enabled_cfg
        and (
            getattr(cfg.sinks, "enable_sublimation", False)
            or sinks_mode_value == "sublimation"
        )
    )
    gas_drag_enabled_cfg = bool(
        sinks_enabled_cfg and getattr(cfg.sinks, "enable_gas_drag", False)
    )
    sink_opts = sinks.SinkOptions(
        enable_sublimation=sublimation_enabled_cfg,
        sub_params=sub_params,
        enable_gas_drag=gas_drag_enabled_cfg,
        rho_g=cfg.sinks.rho_g if gas_drag_enabled_cfg else 0.0,
    )
    if enforce_collisions_only:
        sink_opts.enable_sublimation = False
        sink_opts.enable_gas_drag = False
    sink_opts_surface = copy.deepcopy(sink_opts)
    sink_opts_surface.enable_sublimation = bool(
        sink_opts.enable_sublimation and sublimation_to_surface and not enforce_collisions_only
    )
    sink_opts_surface.enable_gas_drag = bool(sink_opts.enable_gas_drag and not enforce_collisions_only)
    if enforce_sublimation_only:
        sublimation_active_flag = True
    elif enforce_collisions_only:
        sublimation_active_flag = False
    else:
        sublimation_active_flag = sublimation_enabled_cfg
    sink_timescale_active = bool(
        (sink_opts_surface.enable_sublimation or sink_opts_surface.enable_gas_drag)
        and not enforce_collisions_only
    )
    sinks_active = bool(sublimation_active_flag or sink_timescale_active)

    supply_spec = cfg.supply

    t_end, dt_nominal, dt_initial_step, n_steps, time_grid_info = _resolve_time_grid(
        cfg.numerics,
        Omega,
        t_orb,
    )
    dt = dt_initial_step
    if n_steps > MAX_STEPS:
        n_steps = MAX_STEPS
        dt = t_end / n_steps
        time_grid_info["n_steps"] = n_steps
        time_grid_info["dt_step"] = dt
        time_grid_info["dt_capped_by_max_steps"] = True

    history = ZeroDHistory()
    records = history.records
    psd_hist_records = history.psd_hist_records
    diagnostics = history.diagnostics
    mass_budget = history.mass_budget
    step_diag_records = history.step_diag_records
    step_diag_cfg = getattr(cfg.io, "step_diagnostics", None)
    step_diag_enabled = bool(getattr(step_diag_cfg, "enable", False)) if step_diag_cfg else False
    step_diag_format = str(getattr(step_diag_cfg, "format", "csv") or "csv").lower()
    if step_diag_format not in {"csv", "jsonl"}:
        raise ValueError("io.step_diagnostics.format must be either 'csv' or 'jsonl'")
    step_diag_path_cfg = getattr(step_diag_cfg, "path", None) if step_diag_cfg else None
    debug_sinks_enabled = bool(getattr(cfg.io, "debug_sinks", False))
    correct_fast_blowout = bool(getattr(cfg.io, "correct_fast_blowout", False))
    substep_fast_enabled = bool(getattr(cfg.io, "substep_fast_blowout", False))
    substep_max_ratio = float(getattr(cfg.io, "substep_max_ratio", 1.0))
    if substep_max_ratio <= 0.0:
        raise ValueError("io.substep_max_ratio must be positive")
    debug_records = history.debug_records
    eval_per_step = bool(getattr(cfg.numerics, "eval_per_step", True))
    eval_requires_step = eval_per_step or temp_runtime.enabled
    orbit_rollup_enabled = bool(getattr(cfg.numerics, "orbit_rollup", True))
    dt_over_t_blow_cfg = getattr(cfg.numerics, "dt_over_t_blow_max", None)
    dt_over_t_blow_max = (
        float(dt_over_t_blow_cfg)
        if dt_over_t_blow_cfg is not None
        else float("inf")
    )
    monitor_dt_ratio = math.isfinite(dt_over_t_blow_max) and dt_over_t_blow_max > 0.0

    orbit_time_accum = 0.0
    orbit_loss_blow = 0.0
    orbit_loss_sink = 0.0
    orbits_completed = 0
    orbit_rollup_rows = history.orbit_rollup_rows
    phase_usage = defaultdict(float)
    phase_method_usage = defaultdict(float)
    sink_branch_usage = defaultdict(float)

    Omega_step = Omega
    t_orb_step = t_orb
    a_blow_step = a_blow
    qpr_mean_step = qpr_mean
    qpr_for_blow_step = qpr_for_blow

    temperature_track = history.temperature_track
    beta_track = history.beta_track
    ablow_track = history.ablow_track
    gate_factor_track = history.gate_factor_track
    t_solid_track = history.t_solid_track
    tau_gate_block_time = history.tau_gate_block_time
    total_time_elapsed = history.total_time_elapsed
    phase7_total_rate_track = history.phase7_total_rate_track
    phase7_total_rate_time_track = history.phase7_total_rate_time_track
    phase7_ts_ratio_track = history.phase7_ts_ratio_track
    phase_bulk_state_last: Optional[str] = None
    phase_bulk_f_liquid_last: Optional[float] = None
    phase_bulk_f_solid_last: Optional[float] = None
    phase_bulk_f_vapor_last: Optional[float] = None

    for step_no in range(n_steps):
        time_start = step_no * dt
        time = time_start
        T_use = temp_runtime.evaluate(time)
        temperature_track.append(T_use)
        rad_flux_step = constants.SIGMA_SB * (T_use**4)
        gate_factor = 1.0
        t_solid_step = None
        mass_err_percent_step = None

        if eval_requires_step or step_no == 0:
            Omega_step = grid.omega_kepler(r)
            if Omega_step <= 0.0:
                raise ValueError("Computed Keplerian frequency must be positive")
            t_orb_step = 2.0 * math.pi / Omega_step
            setattr(sub_params, "runtime_t_orb_s", t_orb_step)
            setattr(sub_params, "runtime_Omega", Omega_step)

            qpr_for_blow, a_blow_step = _resolve_blowout(
                s_min_config,
                initial=float(psd_state.get("s_min", s_min_effective)),
            )
            qpr_for_blow_step = qpr_for_blow
            if psd_floor_mode == "none":
                s_min_blow = float(s_min_config)
            else:
                s_min_blow = max(s_min_config, a_blow_step)
            if psd_floor_mode == "none":
                s_min_effective = float(s_min_config)
            elif psd_floor_mode == "evolve_smin":
                s_min_effective = max(s_min_blow, s_min_floor_dynamic)
            else:
                s_min_effective = s_min_blow
                s_min_floor_dynamic = float(max(s_min_floor_dynamic, s_min_effective))
            psd_state["s_min"] = s_min_effective
            s_min_components["blowout"] = float(a_blow_step)
            s_min_components["effective"] = float(s_min_effective)
            s_min_components["floor_dynamic"] = float(s_min_floor_dynamic)
            qpr_mean_step = _lookup_qpr(s_min_effective)
            beta_at_smin_effective = radiation.beta(
                s_min_effective,
                rho_used,
                T_use,
                Q_pr=qpr_mean_step,
            )
            beta_gate_active = beta_at_smin_effective >= beta_threshold
        beta_track.append(beta_at_smin_effective)
        ablow_track.append(a_blow_step)

        t_blow_step = chi_blow_eff / Omega_step if Omega_step > 0.0 else float("inf")

        sigma_for_tau_phase = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_los_phase = kappa_surf * sigma_for_tau_phase
        phase_decision, phase_bulk_step = phase_controller.evaluate_with_bulk(
            T_use,
            pressure_Pa=gas_pressure_pa,
            tau=tau_los_phase,
            radius_m=r,
            time_s=time,
            T0_K=temp_runtime.initial_value,
        )
        phase_state_step = phase_decision.state
        phase_method_step = phase_decision.method
        phase_reason_step = phase_decision.reason
        phase_f_vap_step = phase_decision.f_vap
        phase_payload_step = dict(phase_decision.payload)
        phase_payload_step["tau_input_before_psd"] = tau_los_phase
        phase_payload_step["phase_bulk_state"] = phase_bulk_step.state
        phase_payload_step["phase_bulk_f_liquid"] = phase_bulk_step.f_liquid
        phase_payload_step["phase_bulk_f_solid"] = phase_bulk_step.f_solid
        phase_payload_step["phase_bulk_f_vapor"] = phase_bulk_step.f_vapor
        phase_usage[phase_state_step] += dt
        phase_method_usage[phase_method_step] += dt

        ds_dt_raw = 0.0
        ds_dt_val = 0.0
        T_grain = None
        sublimation_blocked_by_phase = False
        sublimation_active = sublimation_active_flag
        liquid_block_step = sublimation_active and phase_bulk_step.state == "liquid_dominated"
        if sublimation_active:
            T_grain = grain_temperature_graybody(T_use, r)
            try:
                ds_dt_raw = sizes.eval_ds_dt_sublimation(T_grain, rho_used, sub_params)
            except ValueError:
                ds_dt_raw = 0.0
            sublimation_blocked_by_phase = bool(liquid_block_step and ds_dt_raw < 0.0)
            ds_dt_val = 0.0 if liquid_block_step else ds_dt_raw
        sublimation_surface_active_step = bool(
            sublimation_active and sublimation_to_surface and not sublimation_blocked_by_phase
        )
        sublimation_smol_active_step = bool(
            sublimation_active and sublimation_to_smol and not sublimation_blocked_by_phase
        )
        floor_for_step = s_min_effective
        if psd_floor_mode == "none":
            floor_for_step = float(s_min_config)
        elif psd_floor_mode == "evolve_smin":
            delta_floor = abs(ds_dt_val) * dt
            candidate = max(
                s_min_floor_dynamic,
                s_min_effective,
                s_min_floor_dynamic + delta_floor,
                s_min_config,
            )
            if psd_floor_mode != "none":
                candidate = max(candidate, a_blow_step)
            s_min_floor_dynamic = float(candidate)
            floor_for_step = max(s_min_effective, s_min_floor_dynamic)
            s_min_effective = floor_for_step
            s_min_components["floor_dynamic"] = float(s_min_floor_dynamic)
            s_min_components["effective"] = float(s_min_effective)
            psd_state["s_min"] = s_min_effective
        sigma_surf, delta_sigma_sub, erosion_diag = psd.apply_uniform_size_drift(
            psd_state,
            ds_dt=ds_dt_val if sublimation_surface_active_step else 0.0,
            dt=dt,
            floor=floor_for_step,
            sigma_surf=sigma_surf,
        )
        kappa_surf = psd.compute_kappa(psd_state)
        if freeze_kappa:
            kappa_surf = kappa_surf_initial
        dSigma_dt_sublimation = delta_sigma_sub / dt if dt > 0.0 else 0.0
        mass_loss_sublimation_step = delta_sigma_sub * area / constants.M_MARS
        if mass_loss_sublimation_step < 0.0:
            mass_loss_sublimation_step = 0.0
        if mass_loss_sublimation_step > 0.0 and sublimation_surface_active_step:
            M_sink_cum += mass_loss_sublimation_step
            M_sublimation_cum += mass_loss_sublimation_step

        if cfg.sinks.mode == "none" or not sink_timescale_active:
            sink_result = sinks.SinkTimescaleResult(
                t_sink=None,
                components={"sublimation": None, "gas_drag": None},
                dominant_sink=None,
                T_eval=T_use,
                s_ref=SINK_REF_SIZE,
            )
        else:
            sink_result = sinks.total_sink_timescale(
                T_use,
                rho_used,
                Omega_step,
                sink_opts_surface,
                s_ref=SINK_REF_SIZE,
            )
        t_sink_total_value = sink_result.t_sink
        t_sink_surface_only = t_sink_total_value
        if sink_result.components:
            non_sub_times: List[float] = []
            for name, value in sink_result.components.items():
                if name == "sublimation":
                    continue
                val = _safe_float(value)
                if val is not None and val > 0.0:
                    non_sub_times.append(val)
            if non_sub_times:
                t_sink_surface_only = float(min(non_sub_times))
            else:
                t_sink_surface_only = None

        sigma_for_tau_phase = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_los_value = kappa_surf * sigma_for_tau_phase
        tau_los = float(tau_los_value) if math.isfinite(tau_los_value) else 0.0
        phase_payload_step["tau_mars_line_of_sight"] = tau_los
        tau_gate_block_step = bool(
            tau_gate_enabled
            and math.isfinite(tau_los)
            and tau_los >= tau_gate_threshold
        )
        phase_allows_step = not (
            blowout_target_phase == "solid_only" and phase_state_step != "solid"
        )
        enable_blowout_step = bool(
            blowout_enabled
            and beta_gate_active
            and phase_allows_step
            and not tau_gate_block_step
        )
        hydro_timescale_step = None
        sink_selected_step = "rp_blowout" if enable_blowout_step else "none"
        if phase_controller.enabled and phase_state_step == "vapor":
            hydro_timescale_step = phase_mod.hydro_escape_timescale(
                hydro_cfg,
                T_use,
                phase_f_vap_step,
            )
            if hydro_timescale_step is not None:
                sink_selected_step = "hydro_escape"
        if enable_blowout_step and hydro_timescale_step is not None:
            raise RuntimeError(
                "Blow-out and hydrodynamic escape sinks cannot be active simultaneously"
            )
        sink_branch_usage[sink_selected_step] += dt
        phase_state_last = phase_state_step
        phase_method_last = phase_method_step
        phase_reason_last = phase_reason_step
        phase_payload_last = dict(phase_payload_step)
        phase_f_vap_last = phase_f_vap_step
        phase_bulk_state_last = phase_bulk_step.state
        phase_bulk_f_liquid_last = phase_bulk_step.f_liquid
        phase_bulk_f_solid_last = phase_bulk_step.f_solid
        phase_bulk_f_vapor_last = phase_bulk_step.f_vapor
        sink_selected_last = sink_selected_step
        tau_gate_block_last = tau_gate_block_step
        hydro_timescale_last = hydro_timescale_step
        tau_los_last = tau_los
        phase_payload_last["sink_selected"] = sink_selected_step
        phase_payload_last["tau_gate_blocked"] = tau_gate_block_step
        phase_payload_last["sublimation_blocked_by_phase"] = bool(sublimation_blocked_by_phase)
        phase_allows_last = phase_allows_step
        beta_gate_last = beta_gate_active

        if sink_selected_step == "hydro_escape" and hydro_timescale_step is not None:
            t_sink_step_effective = hydro_timescale_step
        elif phase_controller.enabled and phase_state_step == "vapor":
            t_sink_step_effective = None
        else:
            t_sink_step_effective = t_sink_surface_only

        if blowout_enabled and t_blow_step > 0.0:
            fast_blowout_ratio = dt / t_blow_step
            if monitor_dt_ratio and fast_blowout_ratio > dt_over_t_blow_max:
                logger.warning(
                    "dt/t_blow=%.2f exceeds numerics.dt_over_t_blow_max=%.2f",
                    fast_blowout_ratio,
                    dt_over_t_blow_max,
                )
            fast_blowout_factor_calc = (
                _fast_blowout_correction_factor(fast_blowout_ratio)
                if math.isfinite(fast_blowout_ratio)
                else 1.0
            )
            fast_blowout_flag = fast_blowout_ratio > FAST_BLOWOUT_RATIO_THRESHOLD
            fast_blowout_flag_strict = fast_blowout_ratio > FAST_BLOWOUT_RATIO_STRICT
            substep_active = bool(
                substep_fast_enabled and fast_blowout_ratio > substep_max_ratio
            )
            n_substeps = 1
            if substep_active:
                n_substeps = int(math.ceil(dt / (substep_max_ratio * t_blow_step)))
            dt_sub = dt / n_substeps
            ratio_sub = dt_sub / t_blow_step
            fast_blowout_factor_sub = (
                _fast_blowout_correction_factor(ratio_sub)
                if math.isfinite(ratio_sub)
                else 1.0
            )
            apply_correction = fast_blowout_flag and (correct_fast_blowout or substep_active)
        else:
            fast_blowout_ratio = 0.0
            fast_blowout_factor_calc = 0.0
            fast_blowout_flag = False
            fast_blowout_flag_strict = False
            substep_active = False
            n_substeps = 1
            dt_sub = dt
            ratio_sub = 0.0
            fast_blowout_factor_sub = 0.0
            apply_correction = False
        fast_blowout_applied = False

        kappa_eff = kappa_surf
        sigma_tau1_limit = None
        sigma_tau1_active_last = None
        prod_rate_last = 0.0
        outflux_surface = 0.0
        sink_flux_surface = 0.0
        time_sub = time_start
        if freeze_sigma:
            sigma_surf = sigma_surf_reference
        sigma_before_step = sigma_surf
        total_prod_surface = 0.0
        total_sink_surface = 0.0
        fast_factor_numer = 0.0
        fast_factor_denom = 0.0

        tau_last = None
        phi_effective_last = None
        hydro_mass_total = 0.0
        mass_loss_sublimation_smol_step = 0.0
        mass_loss_rate_sublimation_smol = 0.0
        sigma_loss_smol = 0.0
        surface_active = collisions_active or sink_timescale_active
        if collision_solver_mode == "surface_ode":
            if surface_active:
                for _sub_idx in range(n_substeps):
                    if freeze_sigma:
                        sigma_surf = sigma_surf_reference
                    sigma_for_tau = sigma_surf
                    tau = kappa_surf * sigma_for_tau
                    tau_eval = tau
                    phi_value = None
                    if collisions_active:
                        if shielding_mode == "off":
                            kappa_eff = kappa_surf
                            sigma_tau1_limit = float("inf")
                        elif shielding_mode == "fixed_tau1":
                            tau_target = tau_fixed_target
                            if not math.isfinite(tau_target):
                                tau_target = tau_eval
                            if sigma_tau1_fixed_target is not None:
                                sigma_tau1_limit = float(sigma_tau1_fixed_target)
                                if kappa_surf > 0.0 and not math.isfinite(tau_target):
                                    tau_target = kappa_surf * sigma_tau1_limit
                            if phi_tau_fn is not None:
                                kappa_eff = shielding.effective_kappa(kappa_surf, tau_target, phi_tau_fn)
                            else:
                                kappa_eff = kappa_surf
                            if sigma_tau1_fixed_target is None:
                                if kappa_eff <= 0.0:
                                    sigma_tau1_limit = float("inf")
                                else:
                                    sigma_tau1_limit = float(tau_target / max(kappa_eff, 1.0e-30))
                            tau_eval = tau_target
                        else:
                            tau_eval = tau
                            if phi_tau_fn is not None:
                                kappa_eff = shielding.effective_kappa(kappa_surf, tau_eval, phi_tau_fn)
                                sigma_tau1_limit = shielding.sigma_tau1(kappa_eff)
                            else:
                                kappa_eff, sigma_tau1_limit = shielding.apply_shielding(
                                    kappa_surf, tau_eval, 0.0, 0.0
                                )
                    else:
                        kappa_eff = kappa_surf
                        sigma_tau1_limit = None
                    if kappa_surf > 0.0 and kappa_eff is not None:
                        phi_value = kappa_eff / kappa_surf
                    phi_effective_last = phi_value
                    tau_last = tau_eval
                    enable_blowout_sub = enable_blowout_step and collisions_active
                    t_sink_current = t_sink_step_effective if sink_timescale_active else None
                    tau_for_coll = None
                    if collisions_active and cfg.surface.use_tcoll and tau > TAU_MIN:
                        tau_for_coll = tau
                    prod_rate = supply.get_prod_area_rate(time_sub, r, supply_spec)
                    prod_rate_last = prod_rate
                    total_prod_surface += prod_rate * dt_sub
                    sigma_tau1_active = (
                        sigma_tau1_limit
                        if (blowout_layer_mode == "surface_tau_le_1" and collisions_active)
                        else None
                    )
                    sigma_tau1_active_last = sigma_tau1_active
                    res = surface.step_surface(
                        sigma_surf,
                        prod_rate,
                        dt_sub,
                        Omega_step,
                        tau=tau_for_coll,
                        t_sink=t_sink_current,
                        sigma_tau1=sigma_tau1_active,
                        enable_blowout=enable_blowout_sub,
                    )
                    sigma_surf = res.sigma_surf
                    outflux_surface = res.outflux
                    sink_flux_surface = res.sink_flux
                    if sink_selected_step == "hydro_escape" and hydro_timescale_step is not None:
                        hydro_mass_total += sink_flux_surface * dt_sub * area / constants.M_MARS
                    if freeze_sigma:
                        sigma_surf = sigma_surf_reference
                    if apply_correction:
                        outflux_surface *= fast_blowout_factor_sub
                        fast_blowout_applied = True
                    total_sink_surface += sink_flux_surface * dt_sub
                    fast_factor_numer += fast_blowout_factor_sub * dt_sub
                    fast_factor_denom += dt_sub
                    time_sub += dt_sub
            else:
                time_sub = time_start + dt
                tau_last = kappa_surf * sigma_surf
                sigma_tau1_limit = None
                kappa_eff = kappa_surf
                sigma_tau1_active_last = None
        else:
            if surface_active:
                if freeze_sigma:
                    sigma_surf = sigma_surf_reference
                sigma_for_tau = sigma_surf
                tau = kappa_surf * sigma_for_tau
                tau_eval = tau
                phi_value = None
                if collisions_active:
                    if shielding_mode == "off":
                        kappa_eff = kappa_surf
                        sigma_tau1_limit = float("inf")
                    elif shielding_mode == "fixed_tau1":
                        tau_target = tau_fixed_target
                        if not math.isfinite(tau_target):
                            tau_target = tau_eval
                        if sigma_tau1_fixed_target is not None:
                            sigma_tau1_limit = float(sigma_tau1_fixed_target)
                            if kappa_surf > 0.0 and not math.isfinite(tau_target):
                                tau_target = kappa_surf * sigma_tau1_limit
                        if phi_tau_fn is not None:
                            kappa_eff = shielding.effective_kappa(kappa_surf, tau_target, phi_tau_fn)
                        else:
                            kappa_eff = kappa_surf
                        if sigma_tau1_fixed_target is None:
                            if kappa_eff <= 0.0:
                                sigma_tau1_limit = float("inf")
                            else:
                                sigma_tau1_limit = float(tau_target / max(kappa_eff, 1.0e-30))
                        tau_eval = tau_target
                    else:
                        tau_eval = tau
                        if phi_tau_fn is not None:
                            kappa_eff = shielding.effective_kappa(kappa_surf, tau_eval, phi_tau_fn)
                            sigma_tau1_limit = shielding.sigma_tau1(kappa_eff)
                        else:
                            kappa_eff, sigma_tau1_limit = shielding.apply_shielding(
                                kappa_surf, tau_eval, 0.0, 0.0
                            )
                else:
                    kappa_eff = kappa_surf
                    sigma_tau1_limit = None
                if kappa_surf > 0.0 and kappa_eff is not None:
                    phi_value = kappa_eff / kappa_surf
                phi_effective_last = phi_value
                tau_last = tau_eval
                enable_blowout_sub = enable_blowout_step and collisions_active
                t_sink_current = t_sink_step_effective if sink_timescale_active else None
                prod_rate = supply.get_prod_area_rate(time_start, r, supply_spec)
                prod_rate_last = prod_rate
                sigma_tau1_active = (
                    sigma_tau1_limit
                    if (blowout_layer_mode == "surface_tau_le_1" and collisions_active)
                    else None
                )
                sigma_tau1_active_last = sigma_tau1_active
                sigma_before_step = sigma_surf
                smol_res = collisions_smol.step_collisions_smol_0d(
                    psd_state,
                    sigma_surf,
                    dt=dt,
                    prod_subblow_area_rate=prod_rate,
                    r=r,
                    Omega=Omega_step,
                    a_blow=a_blow_step,
                    rho=rho_used,
                    e_value=e0_effective,
                    i_value=i0_effective,
                    sigma_tau1=sigma_tau1_active,
                    enable_blowout=enable_blowout_sub,
                    t_sink=t_sink_current if sink_timescale_active else None,
                    ds_dt_val=ds_dt_val if sublimation_smol_active_step else None,
                    s_min_effective=s_min_effective,
                    dynamics_cfg=cfg.dynamics,
                    tau_eff=tau_eval,
                )
                psd_state = smol_res.psd_state
                sigma_surf = smol_res.sigma_after
                sigma_loss_smol = max(sigma_loss_smol, 0.0) + max(smol_res.sigma_loss, 0.0)
                prod_rate_last = smol_res.prod_mass_rate_effective
                total_prod_surface = smol_res.prod_mass_rate_effective * dt
                outflux_surface = smol_res.dSigma_dt_blowout
                if apply_correction:
                    outflux_surface *= fast_blowout_factor_sub
                    fast_blowout_applied = True
                clip_rate = max(
                    smol_res.dSigma_dt_sinks
                    - smol_res.mass_loss_rate_sinks
                    - smol_res.mass_loss_rate_sublimation,
                    0.0,
                )
                sink_flux_surface = (
                    smol_res.mass_loss_rate_sinks
                    + smol_res.mass_loss_rate_sublimation
                    + clip_rate
                )
                total_sink_surface = smol_res.dSigma_dt_sinks * dt
                mass_loss_rate_sublimation_smol = smol_res.mass_loss_rate_sublimation
                mass_loss_sublimation_smol_step = mass_loss_rate_sublimation_smol * dt * area / constants.M_MARS
                fast_factor_numer = fast_blowout_factor_sub * dt
                fast_factor_denom = dt
                mass_err_percent_step = smol_res.mass_error * 100.0
                time_sub = time_start + dt
            else:
                time_sub = time_start + dt
                tau_last = kappa_surf * sigma_surf
                sigma_tau1_limit = None
                kappa_eff = kappa_surf
                sigma_tau1_active_last = None

        if sink_timescale_active:
            t_sink_step = t_sink_step_effective
        else:
            t_sink_step = None

        time = time_sub
        if sublimation_smol_active_step and collision_solver_mode != "smol":
            # Sublimation-to-Smol path: gated by phase and sigma_surf>0 to avoid
            # changing the existing surface sink semantics.
            sizes_arr, widths_arr, m_k, N_k, scale_to_sigma = smol.psd_state_to_number_density(
                psd_state,
                sigma_surf,
                rho_fallback=rho_used,
            )
            if N_k.size and sigma_surf > 0.0:
                ds_dt_fill = ds_dt_val if ds_dt_val is not None else 0.0
                ds_dt_k = np.full_like(sizes_arr, ds_dt_fill, dtype=float)
                S_sub_k, mass_loss_rate_sub = sublimation_sink_from_dsdt(
                    sizes_arr,
                    N_k,
                    ds_dt_k,
                    m_k,
                )
                mass_loss_rate_sublimation_smol = mass_loss_rate_sub
                if np.any(S_sub_k):
                    n_bins_smol = sizes_arr.size
                    zeros_kernel = np.zeros((n_bins_smol, n_bins_smol))
                    zeros_frag = np.zeros((n_bins_smol, n_bins_smol, n_bins_smol))
                    N_new_smol, _smol_dt_eff, _smol_mass_err = smol.step_imex_bdf1_C3(
                        N_k,
                        zeros_kernel,
                        zeros_frag,
                        np.zeros_like(N_k),
                        m_k,
                        prod_subblow_mass_rate=0.0,
                        dt=dt,
                        S_external_k=None,
                        S_sublimation_k=S_sub_k,
                        extra_mass_loss_rate=mass_loss_rate_sub,
                    )
                    sigma_before_smol = sigma_surf
                    psd_state, sigma_after_smol, sigma_loss_smol = smol.number_density_to_psd_state(
                        N_new_smol,
                        psd_state,
                        sigma_before_smol,
                        widths=widths_arr,
                        m=m_k,
                        scale_to_sigma=scale_to_sigma,
                    )
                    sigma_surf = sigma_after_smol
                    sigma_loss_smol = max(sigma_loss_smol, 0.0)
                    mass_loss_sublimation_smol_step = sigma_loss_smol * area / constants.M_MARS
                    if sigma_loss_smol > 0.0 and dt > 0.0:
                        mass_loss_rate_sublimation_smol = sigma_loss_smol / dt
                    if mass_loss_sublimation_smol_step > 0.0:
                        M_sink_cum += mass_loss_sublimation_smol_step
                        M_sublimation_cum += mass_loss_sublimation_smol_step
        if freeze_sigma:
            sigma_surf = sigma_surf_reference

        if blowout_gate_mode == "sublimation_competition":
            if (
                ds_dt_val < 0.0
                and math.isfinite(ds_dt_val)
                and math.isfinite(s_min_effective)
            ):
                candidate = s_min_effective / abs(ds_dt_val)
                if candidate > 0.0 and math.isfinite(candidate):
                    t_solid_step = candidate
        elif blowout_gate_mode == "collision_competition":
            if tau_last is not None and tau_last > TAU_MIN and Omega_step > 0.0:
                candidate = 1.0 / (Omega_step * max(tau_last, TAU_MIN))
                if candidate > 0.0 and math.isfinite(candidate):
                    t_solid_step = candidate
        if gate_enabled and enable_blowout_step:
            gate_factor = _compute_gate_factor(t_blow_step, t_solid_step)

        if collisions_active:
            loss_total_surface = sigma_before_step + total_prod_surface - sigma_surf
            loss_total_surface = max(loss_total_surface, 0.0)
            sink_surface_total = max(total_sink_surface, 0.0)
            blow_surface_total = max(loss_total_surface - sink_surface_total, 0.0)
            if not enable_blowout_step:
                blow_surface_total = 0.0
        else:
            loss_total_surface = 0.0
            sink_surface_total = 0.0
            blow_surface_total = 0.0

        if enable_blowout_step and gate_enabled:
            blow_surface_total *= gate_factor
            outflux_surface *= gate_factor

        t_solid_track.append(float(t_solid_step) if t_solid_step is not None else float("nan"))
        gate_factor_track.append(float(gate_factor))

        sink_mass_total = sink_surface_total * area / constants.M_MARS
        sink_mass_total_effective = sink_mass_total
        if collision_solver_mode == "smol":
            sink_mass_total_effective = max(
                sink_mass_total - mass_loss_sublimation_smol_step, 0.0
            )
        blow_mass_total = blow_surface_total * area / constants.M_MARS
        mass_loss_surface_solid_step = blow_mass_total
        if collisions_active:
            M_loss_cum += blow_mass_total
        if sink_timescale_active:
            M_sink_cum += sink_mass_total_effective
            if sink_result.sublimation_fraction > 0.0:
                M_sublimation_cum += sink_mass_total * sink_result.sublimation_fraction
        M_hydro_cum += hydro_mass_total
        if collision_solver_mode == "smol" and mass_loss_sublimation_smol_step > 0.0:
            M_sink_cum += mass_loss_sublimation_smol_step
            M_sublimation_cum += mass_loss_sublimation_smol_step

        mass_loss_sublimation_step_total = mass_loss_sublimation_step + mass_loss_sublimation_smol_step
        mass_loss_sinks_step_total = (
            mass_loss_sublimation_step_total + sink_mass_total_effective
        )
        mass_loss_hydro_step = hydro_mass_total
        M_out_dot_avg = blow_mass_total / dt if dt > 0.0 else 0.0
        M_sink_dot_avg = mass_loss_sinks_step_total / dt if dt > 0.0 else 0.0
        dM_dt_surface_total_avg = M_out_dot_avg + M_sink_dot_avg
        fast_blowout_factor_avg = (
            fast_factor_numer / fast_factor_denom
            if fast_factor_denom > 0.0
            else fast_blowout_factor_calc
        )

        outflux_mass_rate_kg = outflux_surface * area
        sink_mass_rate_kg = sink_flux_surface * area
        if collision_solver_mode == "smol":
            sink_mass_rate_kg = max(
                sink_mass_rate_kg - mass_loss_rate_sublimation_smol * area, 0.0
            )
        sink_mass_rate_kg_total = sink_mass_rate_kg
        if dt > 0.0:
            sink_mass_rate_kg_total += mass_loss_sublimation_step * constants.M_MARS / dt
            sink_mass_rate_kg_total += mass_loss_rate_sublimation_smol * area
        M_out_dot = outflux_mass_rate_kg / constants.M_MARS
        M_sink_dot = sink_mass_rate_kg_total / constants.M_MARS
        dM_dt_surface_total = M_out_dot + M_sink_dot
        dSigma_dt_blowout = outflux_surface
        sink_flux_nosub = max(sink_flux_surface - mass_loss_rate_sublimation_smol, 0.0)
        dSigma_dt_sinks = sink_flux_nosub + dSigma_dt_sublimation + mass_loss_rate_sublimation_smol
        dSigma_dt_total = dSigma_dt_blowout + dSigma_dt_sinks
        dt_over_t_blow = fast_blowout_ratio
        fast_blowout_factor_record = (
            fast_blowout_factor_calc if case_status == "blowout" else 0.0
        )
        fast_blowout_ratio_alias = (
            fast_blowout_ratio if case_status == "blowout" else 0.0
        )
        if not blowout_enabled:
            outflux_mass_rate_kg = 0.0
            M_out_dot = 0.0
            dSigma_dt_blowout = 0.0
            dt_over_t_blow = 0.0
            fast_blowout_factor_avg = 0.0
            fast_blowout_factor_record = 0.0
            fast_blowout_ratio_alias = 0.0
        dSigma_dt_sublimation_total = dSigma_dt_sublimation + mass_loss_rate_sublimation_smol
        sigma_loss_total_sub = delta_sigma_sub + sigma_loss_smol
        mass_loss_sublimation_step_diag = mass_loss_sublimation_step_total

        orbit_time_accum += dt
        orbit_loss_blow += blow_mass_total
        orbit_loss_sink += mass_loss_sinks_step_total
        if orbit_rollup_enabled and t_orb_step > 0.0:
            while orbit_time_accum >= t_orb_step and orbit_time_accum > 0.0:
                orbit_time_accum_before = orbit_time_accum
                fraction = t_orb_step / orbit_time_accum_before
                M_orbit_blow = orbit_loss_blow * fraction
                M_orbit_sink = orbit_loss_sink * fraction
                orbits_completed += 1
                mass_loss_frac = float("nan")
                if cfg.initial.mass_total > 0.0:
                    mass_loss_frac = (M_orbit_blow + M_orbit_sink) / cfg.initial.mass_total
                time_s_end = time - max(orbit_time_accum_before - t_orb_step, 0.0)
                orbit_rollup_rows.append(
                    {
                        "orbit_index": orbits_completed,
                        "time_s": time,
                        "time_s_end": time_s_end,
                        "t_orb_s": t_orb_step,
                        "M_out_orbit": M_orbit_blow,
                        "M_sink_orbit": M_orbit_sink,
                        "M_loss_orbit": M_orbit_blow + M_orbit_sink,
                        "M_out_per_orbit": M_orbit_blow / t_orb_step,
                        "M_sink_per_orbit": M_orbit_sink / t_orb_step,
                        "M_loss_per_orbit": (M_orbit_blow + M_orbit_sink) / t_orb_step,
                        "mass_loss_frac_per_orbit": mass_loss_frac,
                        "M_out_cum": M_loss_cum,
                        "M_sink_cum": M_sink_cum,
                        "M_loss_cum": M_loss_cum + M_sink_cum,
                        "r_RM": r_RM,
                        "T_M": T_use,
                        "slope_dlnM_dlnr": None,
                    }
                )
                orbit_time_accum -= t_orb_step
                orbit_loss_blow = max(orbit_loss_blow - M_orbit_blow, 0.0)
                orbit_loss_sink = max(orbit_loss_sink - M_orbit_sink, 0.0)

        if evolve_min_size_enabled:
            s_min_evolved_value = psd.evolve_min_size(
                s_min_evolved_value,
                dt=dt,
                model=getattr(cfg.sizes, "dsdt_model", None),
                params=getattr(cfg.sizes, "dsdt_params", None),
                T=T_use,
                rho=rho_used,
                s_floor=s_min_effective,
                sublimation_params=sub_params,
            )

        if debug_sinks_enabled:
            debug_records.append(
                {
                    "step": int(step_no),
                    "time_s": time,
                    "dt_s": dt,
                    "dt_sub_s": dt_sub,
                    "T_M_K": T_use,
                    "T_d_graybody_K": sink_result.T_eval,
                    "T_source": T_M_source,
                    "r_m": r,
                    "r_RM": r_RM,
                    "t_sink_s": t_sink_step,
                    "dominant_sink": sink_result.dominant_sink,
                    "sublimation_timescale_s": sink_result.components.get("sublimation"),
                    "gas_drag_timescale_s": sink_result.components.get("gas_drag"),
                    "total_sink_dm_dt_kg_s": sink_mass_rate_kg_total,
                    "sublimation_dm_dt_kg_s": (
                        sink_mass_rate_kg_total
                        if sink_result.dominant_sink == "sublimation"
                        else 0.0
                    ),
                    "cum_sink_mass_kg": M_sink_cum * constants.M_MARS,
                    "cum_sublimation_mass_kg": M_sublimation_cum * constants.M_MARS,
                    "blowout_mass_rate_kg_s": outflux_mass_rate_kg,
                    "cum_blowout_mass_kg": M_loss_cum * constants.M_MARS,
                    "ds_dt_sublimation_m_s": ds_dt_val,
                    "ds_dt_sublimation_raw_m_s": ds_dt_raw,
                    "sigma_loss_sublimation_kg_m2": sigma_loss_total_sub,
                    "M_loss_components_Mmars": {
                        "blowout": M_loss_cum,
                        "blowout_surface_solid_marsRP": M_loss_cum,
                        "sinks": M_sink_cum,
                        "total": M_loss_cum + M_sink_cum,
                    },
                    "phase_state": phase_state_last,
                    "phase_method": phase_method_last,
                    "phase_reason": phase_reason_last,
                    "phase_f_vap": phase_f_vap_last,
                    "phase_bulk_state": phase_bulk_state_last,
                    "phase_bulk_f_liquid": phase_bulk_f_liquid_last,
                    "phase_bulk_f_solid": phase_bulk_f_solid_last,
                    "tau_mars_line_of_sight": tau_los_last,
                    "tau_gate_blocked": tau_gate_block_last,
                    "sink_selected": sink_selected_last,
                    "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
                    "hydro_timescale_s": _safe_float(hydro_timescale_last),
                    "mass_loss_hydro_step": mass_loss_hydro_step,
                    "sinks_mode": cfg.sinks.mode,
                    "enable_sublimation": cfg.sinks.enable_sublimation,
                    "enable_gas_drag": cfg.sinks.enable_gas_drag,
                    "rho_particle_kg_m3": rho_used,
                    "rho_gas_kg_m3": cfg.sinks.rho_g,
                    "sink_components_timescale_s": sink_result.components,
                    "T_eval_sink_K": sink_result.T_eval,
                    "dt_over_t_blow": dt_over_t_blow,
                    "fast_blowout_corrected": fast_blowout_applied,
                    "fast_blowout_factor": fast_blowout_factor_record,
                    "fast_blowout_ratio": fast_blowout_ratio_alias,
                    "n_substeps": int(n_substeps),
                    "substep_active": substep_active,
                    "fast_blowout_factor_avg": fast_blowout_factor_avg,
                    "chi_blow_eff": chi_blow_eff,
                    "Q_pr_blow": qpr_for_blow_step,
                    "s_ref_m": sink_result.s_ref,
                }
            )

        tau = kappa_surf * sigma_surf
        sigma_diag = sigma_surf_reference if freeze_sigma else sigma_surf
        tau_eff_diag = None
        if kappa_eff is not None and math.isfinite(kappa_eff):
            tau_eff_diag = kappa_eff * sigma_diag
        t_coll_step = None
        if collisions_active and tau_last is not None and tau_last > TAU_MIN and Omega_step > 0.0:
            try:
                t_coll_candidate = surface.wyatt_tcoll_S1(float(tau_last), Omega_step)
            except Exception:
                t_coll_candidate = None
            else:
                if math.isfinite(t_coll_candidate) and t_coll_candidate > 0.0:
                    t_coll_step = float(t_coll_candidate)
        ts_ratio_value = None
        if (
            t_coll_step is not None
            and t_coll_step > 0.0
            and t_blow_step is not None
            and t_blow_step > 0.0
            and math.isfinite(t_blow_step)
        ):
            ts_ratio_value = float(t_blow_step / t_coll_step)
        record = {
            "time": time,
            "dt": dt,
            "Omega_s": Omega_step,
            "t_orb_s": t_orb_step,
            "t_blow_s": t_blow_step,
            "r_m": r,
            "r_RM": r_RM,
            "r_source": r_source,
            "T_M_used": T_use,
            "T_M_source": T_M_source,
            "rad_flux_Mars": rad_flux_step,
            "dt_over_t_blow": dt_over_t_blow,
            "tau": tau,
            "a_blow_step": a_blow_step,
            "a_blow": a_blow_step,
            "a_blow_at_smin": a_blow_step,
            "s_min": s_min_effective,
            "kappa": kappa_eff,
            "Qpr_mean": qpr_mean_step,
            "Q_pr_at_smin": qpr_mean_step,
            "beta_at_smin_config": beta_at_smin_config,
            "beta_at_smin_effective": beta_at_smin_effective,
            "beta_at_smin": beta_at_smin_effective,
            "beta_threshold": beta_threshold,
            "Sigma_surf": sigma_surf,
            "Sigma_tau1": sigma_tau1_limit,
            "Sigma_tau1_active": sigma_tau1_active_last,
            "outflux_surface": outflux_surface,
            "t_solid_s": t_solid_step,
            "blowout_gate_factor": gate_factor,
            "sink_flux_surface": sink_flux_surface,
            "t_blow": t_blow_step,
            "prod_subblow_area_rate": prod_rate_last,
            "M_out_dot": M_out_dot,
            "M_sink_dot": M_sink_dot,
            "dM_dt_surface_total": dM_dt_surface_total,
            "M_out_dot_avg": M_out_dot_avg,
            "M_sink_dot_avg": M_sink_dot_avg,
            "dM_dt_surface_total_avg": dM_dt_surface_total_avg,
            "fast_blowout_factor_avg": fast_blowout_factor_avg,
            "dSigma_dt_blowout": dSigma_dt_blowout,
            "dSigma_dt_sinks": dSigma_dt_sinks,
            "dSigma_dt_total": dSigma_dt_total,
            "dSigma_dt_sublimation": dSigma_dt_sublimation_total,
            "M_loss_cum": M_loss_cum + M_sink_cum,
            "mass_total_bins": cfg.initial.mass_total - (M_loss_cum + M_sink_cum),
            "mass_lost_by_blowout": M_loss_cum,
            "mass_lost_by_sinks": M_sink_cum,
            "mass_lost_sinks_step": mass_loss_sinks_step_total,
            "mass_lost_sublimation_step": mass_loss_sublimation_step_diag,
            "mass_lost_hydro_step": mass_loss_hydro_step,
            "mass_lost_surface_solid_marsRP_step": mass_loss_surface_solid_step,
            "M_loss_rp_mars": M_loss_cum,
            "M_loss_surface_solid_marsRP": M_loss_cum,
            "M_loss_hydro": M_hydro_cum,
            "fast_blowout_factor": fast_blowout_factor_record,
            "fast_blowout_corrected": fast_blowout_applied,
            "fast_blowout_flag_gt3": fast_blowout_flag,
            "fast_blowout_flag_gt10": fast_blowout_flag_strict,
            "fast_blowout_ratio": fast_blowout_ratio_alias,
            "n_substeps": int(n_substeps),
            "chi_blow_eff": chi_blow_eff,
            "case_status": case_status,
            "s_blow_m": a_blow_step,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean_step,
            "Q_pr_blow": qpr_for_blow_step,
            "s_min_effective": s_min_effective,
            "s_min_config": s_min_config,
            "s_min_effective_gt_config": s_min_effective > s_min_config,
            "T_source": T_M_source,
            "T_M_used": T_use,
            "ds_dt_sublimation": ds_dt_val,
            "ds_dt_sublimation_raw": ds_dt_raw,
            "phase_state": phase_state_last,
            "phase_f_vap": phase_f_vap_last,
            "phase_method": phase_method_last,
            "phase_reason": phase_reason_last,
            "phase_bulk_state": phase_bulk_state_last,
            "phase_bulk_f_liquid": phase_bulk_f_liquid_last,
            "phase_bulk_f_solid": phase_bulk_f_solid_last,
            "phase_bulk_f_vapor": phase_bulk_f_vapor_last,
            "tau_mars_line_of_sight": tau_los_last,
            "tau_gate_blocked": tau_gate_block_last,
            "blowout_beta_gate": beta_gate_last,
            "blowout_phase_allowed": phase_allows_last,
            "blowout_layer_mode": blowout_layer_mode,
            "blowout_target_phase": blowout_target_phase,
            "sink_selected": sink_selected_last,
            "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
        }
        if phase7_enabled:
            record.update(
                {
                    "mloss_blowout_rate": M_out_dot,
                    "mloss_sink_rate": M_sink_dot,
                    "mloss_total_rate": dM_dt_surface_total,
                    "cum_mloss_blowout": M_loss_cum,
                    "cum_mloss_sink": M_sink_cum,
                    "cum_mloss_total": M_loss_cum + M_sink_cum,
                    "t_coll": t_coll_step,
                    "ts_ratio": ts_ratio_value,
                    "beta_eff": beta_at_smin_effective,
                    "kappa_eff": kappa_eff,
                    "tau_eff": tau_eff_diag,
                }
            )
            phase7_total_rate_track.append(dM_dt_surface_total)
            phase7_total_rate_time_track.append(time)
            if ts_ratio_value is not None and math.isfinite(ts_ratio_value):
                phase7_ts_ratio_track.append(ts_ratio_value)
        if evolve_min_size_enabled:
            record["s_min_evolved"] = s_min_evolved_value
        records.append(record)

        try:
            sizes_arr = np.asarray(psd_state.get("sizes"), dtype=float)
            number_arr = np.asarray(psd_state.get("number"), dtype=float)
        except Exception:
            sizes_arr = np.empty(0, dtype=float)
            number_arr = np.empty(0, dtype=float)
        if sizes_arr.size and number_arr.size == sizes_arr.size:
            for idx, (size_val, number_val) in enumerate(zip(sizes_arr, number_arr)):
                psd_hist_records.append(
                    {
                        "time": time,
                        "bin_index": int(idx),
                        "s_bin_center": float(size_val),
                        "N_bin": float(number_val),
                        "Sigma_surf": sigma_surf,
                    }
                )

        F_abs_geom = constants.SIGMA_SB * (T_use**4) * (constants.R_MARS / r) ** 2
        phi_effective_diag = phi_effective_last
        if phi_effective_diag is None and kappa_surf > 0.0:
            phi_effective_diag = kappa_eff / kappa_surf

        s_peak_value = _psd_mass_peak()
        F_abs_qpr = F_abs_geom * qpr_mean_step
        diag_entry = {
            "time": time,
            "dt": dt,
            "dt_over_t_blow": dt_over_t_blow,
            "r_m_used": r,
            "r_RM_used": r_RM,
            "T_M_used": T_use,
            "rad_flux_Mars": rad_flux_step,
            "F_abs_geom": F_abs_geom,
            "F_abs_geom_qpr": F_abs_qpr,
            "F_abs": F_abs_qpr,
            "Omega_s": Omega_step,
            "t_orb_s": t_orb_step,
            "t_blow_s": t_blow_step,
            "t_solid_s": t_solid_step,
            "t_sink_total_s": _safe_float(t_sink_total_value),
            "t_sink_surface_s": float(t_sink_step) if t_sink_step is not None else None,
            "t_sink_sublimation_s": _safe_float(sink_result.components.get("sublimation")),
            "t_sink_gas_drag_s": _safe_float(sink_result.components.get("gas_drag")),
            "mass_loss_sinks_step": mass_loss_sinks_step_total,
            "mass_lost_by_sinks": M_sink_cum,
            "mass_loss_sublimation_step": mass_loss_sublimation_step_diag,
            "sigma_tau1": sigma_tau1_limit,
            "sigma_tau1_active": sigma_tau1_active_last,
            "tau_vertical": tau_last,
            "kappa_eff": kappa_eff,
            "kappa_surf": kappa_surf,
            "phi_effective": phi_effective_diag,
            "psi_shield": phi_effective_diag,
            "sigma_surf": sigma_diag,
            "kappa_Planck": kappa_surf,
            "tau_eff": tau_eff_diag,
            "s_min": s_min_effective,
            "a_blow_at_smin": a_blow_step,
            "beta_at_smin": beta_at_smin_effective,
            "Q_pr_at_smin": qpr_mean_step,
            "s_peak": s_peak_value,
            "area_m2": area,
            "prod_subblow_area_rate": prod_rate_last,
            "s_min_effective": s_min_effective,
            "qpr_mean": qpr_mean_step,
            "chi_blow_eff": chi_blow_eff,
            "ds_step_uniform": erosion_diag.get("ds_step"),
            "mass_ratio_uniform": erosion_diag.get("mass_ratio"),
            "M_out_cum": M_loss_cum,
            "M_sink_cum": M_sink_cum,
            "M_loss_cum": M_loss_cum + M_sink_cum,
            "M_loss_surface_solid_marsRP": M_loss_cum,
            "M_hydro_cum": M_hydro_cum,
            "phase_state": phase_state_last,
            "phase_method": phase_method_last,
            "phase_reason": phase_reason_last,
            "phase_f_vap": phase_f_vap_last,
            "phase_bulk_state": phase_bulk_state_last,
            "phase_bulk_f_liquid": phase_bulk_f_liquid_last,
            "phase_bulk_f_solid": phase_bulk_f_solid_last,
            "phase_bulk_f_vapor": phase_bulk_f_vapor_last,
            "phase_payload": phase_payload_last,
            "ds_dt_sublimation": ds_dt_val,
            "ds_dt_sublimation_raw": ds_dt_raw,
            "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
            "tau_mars_line_of_sight": tau_los_last,
            "tau_gate_blocked": tau_gate_block_last,
            "blowout_beta_gate": beta_gate_last,
            "blowout_phase_allowed": phase_allows_last,
            "blowout_layer_mode": blowout_layer_mode,
            "blowout_target_phase": blowout_target_phase,
            "sink_selected": sink_selected_last,
            "hydro_timescale_s": _safe_float(hydro_timescale_last),
            "mass_loss_surface_solid_step": mass_loss_surface_solid_step,
            "blowout_gate_factor": gate_factor,
        }
        diagnostics.append(diag_entry)

        mass_initial = cfg.initial.mass_total
        mass_remaining = mass_initial - (M_loss_cum + M_sink_cum)
        mass_lost = M_loss_cum + M_sink_cum
        mass_diff = mass_initial - mass_remaining - mass_lost
        mass_diff_percent = 0.0
        if mass_initial != 0.0:
            mass_diff_percent = abs(mass_diff / mass_initial) * 100.0
        error_percent = mass_diff_percent
        if mass_err_percent_step is not None:
            error_percent = max(mass_err_percent_step, mass_diff_percent)
        budget_entry = {
            "time": time,
            "mass_initial": mass_initial,
            "mass_remaining": mass_remaining,
            "mass_lost": mass_lost,
            "mass_diff": mass_diff,
            "error_percent": error_percent,
            "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
            "mass_loss_rp_mars": M_loss_cum,
            "mass_loss_hydro_drag": M_hydro_cum,
            "mass_loss_surface_solid_marsRP": M_loss_cum,
        }
        if phase7_enabled:
            channels_total = M_loss_cum + M_sink_cum
            denom = abs(channels_total) if abs(channels_total) > 0.0 else 1.0
            delta_channels = ((mass_lost - channels_total) / denom) * 100.0
            budget_entry["delta_mloss_vs_channels"] = delta_channels
        mass_budget.append(budget_entry)
        if step_diag_enabled:
            tau_surf_val = tau_last if tau_last is not None else kappa_surf * sigma_diag
            tau_surf_val = _safe_float(tau_surf_val)
            sink_sub_timescale = sink_result.components.get("sublimation")
            sink_drag_timescale = sink_result.components.get("gas_drag")
            dM_sub = mass_loss_sublimation_step_diag
            dM_drag = 0.0
            if sink_result.dominant_sink == "sublimation":
                dM_sub += sink_mass_total
            elif sink_result.dominant_sink == "gas_drag":
                dM_drag = sink_mass_total
            step_diag_records.append(
                {
                    "time": float(time),
                    "sigma_surf": float(sigma_diag),
                    "tau_surf": tau_surf_val,
                    "t_coll": _safe_float(t_coll_step),
                    "t_blow": _safe_float(t_blow_step),
                    "t_sink": _safe_float(t_sink_step),
                    "t_sink_sub": _safe_float(sink_sub_timescale),
                    "t_sink_drag": _safe_float(sink_drag_timescale),
                    "phase_state_step": phase_state_last,
                    "phase_bulk_state": phase_bulk_state_last,
                    "phase_bulk_f_liquid": _safe_float(phase_bulk_f_liquid_last),
                    "phase_bulk_f_solid": _safe_float(phase_bulk_f_solid_last),
                    "phase_bulk_f_vapor": _safe_float(phase_bulk_f_vapor_last),
                    "ds_dt_sublimation": _safe_float(ds_dt_val),
                    "ds_dt_sublimation_raw": _safe_float(ds_dt_raw),
                    "sublimation_blocked_by_phase": bool(sublimation_blocked_by_phase),
                    "dM_blowout_step": float(mass_loss_surface_solid_step),
                    "dM_sinks_step": float(mass_loss_sinks_step_total),
                    "dM_sublimation_step": float(dM_sub),
                    "dM_gas_drag_step": float(dM_drag),
                    "mass_total_bins": float(mass_remaining),
                    "mass_lost_by_blowout": float(M_loss_cum),
                    "mass_lost_by_sinks": float(M_sink_cum),
                }
            )

        total_time_elapsed += dt
        if tau_gate_block_last:
            tau_gate_block_time += dt

        if (
            mass_initial != 0.0
            and error_percent > MASS_BUDGET_TOLERANCE_PERCENT
            and history.mass_budget_violation is None
        ):
            history.mass_budget_violation = {
                "time": time,
                "error_percent": error_percent,
                "tolerance_percent": MASS_BUDGET_TOLERANCE_PERCENT,
                "mass_initial": mass_initial,
                "mass_remaining": mass_remaining,
                "mass_lost": mass_lost,
                "mass_diff": mass_diff,
            }
            logger.error(
                "Mass budget tolerance exceeded at t=%.3e s (err=%.3f%% > %.3f%%)",
                time,
                error_percent,
                MASS_BUDGET_TOLERANCE_PERCENT,
            )
            if enforce_mass_budget:
                history.violation_triggered = True
                break

        logger.info(
            "run: t=%e a_blow=%.3e kappa=%e t_blow=%e M_loss[M_Mars]=%e",
            time,
            a_blow_step,
            kappa_eff,
            t_blow_step,
            M_loss_cum + M_sink_cum,
        )

    if orbit_rollup_enabled and not orbit_rollup_rows:
        # Fallback rollup for short integrations that do not complete a full orbit.
        mass_loss_frac = float("nan")
        if cfg.initial.mass_total > 0.0:
            mass_loss_frac = (orbit_loss_blow + orbit_loss_sink) / cfg.initial.mass_total
        denom = t_orb_step if t_orb_step > 0.0 else float("nan")
        orbit_rollup_rows.append(
            {
                "orbit_index": 1,
                "time_s": time,
                "time_s_end": time,
                "t_orb_s": t_orb_step,
                "M_out_orbit": orbit_loss_blow,
                "M_sink_orbit": orbit_loss_sink,
                "M_loss_orbit": orbit_loss_blow + orbit_loss_sink,
                "M_out_per_orbit": orbit_loss_blow / denom if math.isfinite(denom) else float("nan"),
                "M_sink_per_orbit": orbit_loss_sink / denom if math.isfinite(denom) else float("nan"),
                "M_loss_per_orbit": (orbit_loss_blow + orbit_loss_sink) / denom if math.isfinite(denom) else float("nan"),
                "mass_loss_frac_per_orbit": mass_loss_frac,
                "M_out_cum": M_loss_cum,
                "M_sink_cum": M_sink_cum,
                "M_loss_cum": M_loss_cum + M_sink_cum,
                "r_RM": r_RM,
                "T_M": T_use,
                "slope_dlnM_dlnr": None,
            }
        )
        orbits_completed = max(orbits_completed, 1)

    history.tau_gate_block_time = tau_gate_block_time
    history.total_time_elapsed = total_time_elapsed

    qpr_mean = qpr_mean_step
    a_blow = a_blow_step
    Omega = Omega_step
    t_orb = t_orb_step
    qpr_blow_final = _lookup_qpr(max(s_min_config, a_blow))

    df = pd.DataFrame(records)
    _write_zero_d_history(
        cfg,
        df,
        history,
        step_diag_enabled=step_diag_enabled,
        step_diag_format=step_diag_format,
        step_diag_path_cfg=step_diag_path_cfg,
        orbit_rollup_enabled=orbit_rollup_enabled,
        phase7_enabled=phase7_enabled,
    )
    outdir = Path(cfg.io.outdir)
    mass_budget_max_error = max((entry["error_percent"] for entry in mass_budget), default=0.0)
    dt_over_t_blow_median = float("nan")
    if not df.empty and "dt_over_t_blow" in df.columns:
        dt_over_t_blow_median = float(df["dt_over_t_blow"].median())

    def _series_stats(values: List[float]) -> tuple[float, float, float]:
        if not values:
            nan = float("nan")
            return nan, nan, nan
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            nan = float("nan")
            return nan, nan, nan
        return float(np.min(arr)), float(np.median(arr)), float(np.max(arr))

    T_min, T_median, T_max = _series_stats(temperature_track)
    beta_min, beta_median, beta_max = _series_stats(beta_track)
    ablow_min, ablow_median, ablow_max = _series_stats(ablow_track)
    gate_min, gate_median, gate_max = _series_stats(gate_factor_track)
    tsolid_min, tsolid_median, tsolid_max = _series_stats(t_solid_track)
    phase7_max_rate = float("nan")
    phase7_max_rate_time = None
    phase7_median_ts_ratio = float("nan")
    tau_gate_block_fraction = (
        float(tau_gate_block_time / total_time_elapsed)
        if total_time_elapsed > 0.0
        else float("nan")
    )
    if phase7_enabled:
        for rate_val, time_val in zip(phase7_total_rate_track, phase7_total_rate_time_track):
            if not math.isfinite(rate_val):
                continue
            if not math.isfinite(phase7_max_rate) or rate_val > phase7_max_rate:
                phase7_max_rate = float(rate_val)
                phase7_max_rate_time = float(time_val)
        if phase7_ts_ratio_track:
            ts_arr = np.asarray(phase7_ts_ratio_track, dtype=float)
            ts_arr = ts_arr[np.isfinite(ts_arr)]
            if ts_arr.size:
                phase7_median_ts_ratio = float(np.median(ts_arr))
    process_overview = {
        "primary_process_cfg": primary_process_cfg,
        "primary_process_resolved": primary_process,
        "primary_scenario": primary_scenario,
        "primary_field_explicit": primary_field_explicit,
        "collisions_active": collisions_active,
        "sinks_mode": sinks_mode_value,
        "sinks_enabled_cfg": sinks_enabled_cfg,
        "sinks_active": bool(sublimation_active_flag or sink_timescale_active),
        "sink_timescale_active": sink_timescale_active,
        "sublimation_dsdt_active": sublimation_active_flag,
        "sublimation_sink_active": sink_opts.enable_sublimation and not enforce_collisions_only,
        "gas_drag_sink_active": sink_opts.enable_gas_drag and not enforce_collisions_only,
        "blowout_active": blowout_enabled,
        "rp_blowout_enabled": rp_blowout_enabled,
        "collision_solver": collision_solver_mode,
    }
    wyatt_collisional_timescale_active = bool(
        collisions_active and getattr(cfg.surface, "use_tcoll", True)
    )
    active_sinks_list: List[str] = []
    if sink_opts.enable_sublimation:
        active_sinks_list.append("sublimation")
    if sink_opts.enable_gas_drag:
        active_sinks_list.append("gas_drag")
    if getattr(hydro_cfg, "enable", False) and sink_timescale_active:
        active_sinks_list.append("hydro_escape")
    inner_scope_mode = (
        "optically_thick_surface_only" if blowout_layer_mode == "surface_tau_le_1" else blowout_layer_mode
    )
    tau_gate_mode = "tau_clipped" if tau_gate_enabled else "off"
    time_grid_summary = {
        "t_start_s": 0.0,
        "t_end_s": time_grid_info.get("t_end_seconds"),
        "dt_s": time_grid_info.get("dt_step", dt),
        "dt_nominal_s": time_grid_info.get("dt_nominal"),
        "n_steps": time_grid_info.get("n_steps"),
        "dt_mode": time_grid_info.get("dt_mode"),
    }
    limitations_list = [
        "Inner-disk only; outer or highly eccentric debris is out of scope.",
        "Radiation pressure source is fixed to Mars; solar/other external sources are ignored even when requested.",
        f"Time horizon is short (~{analysis_window_years:.3g} yr); long-term tidal or viscous evolution is not modelled.",
        "Collisional cascade and sublimation are toggled via single-process modes rather than a fully coupled solver.",
        "Assumes an optically thick inner surface with tau<=1 clipping; vertical/outer tenuous structure is not resolved.",
        "PSD uses a three-slope + wavy correction with blow-out/sublimation floors; no self-consistent halo is evolved.",
    ]
    scope_limitations_base = {
        "scope": {
            "region": scope_region,
            "reference_radius_m": r,
            "reference_radius_source": r_source,
            "analysis_window_years": analysis_window_years,
            "radiation_source": radiation_field,
            "solar_radiation_enabled": False,
            "solar_radiation_requested": solar_rp_requested,
            "inner_disk_scope": inner_scope_flag,
            "inner_disk_scope_mode": inner_scope_mode,
            "tau_gate": {
                "enabled": tau_gate_enabled,
                "tau_max": tau_gate_threshold if tau_gate_enabled else None,
                "mode": tau_gate_mode,
            },
            "shielding_mode": shielding_mode,
            "time_grid_summary": time_grid_summary,
        },
        "active_physics": {
            "primary_scenario": primary_scenario,
            "single_process_mode": single_process_mode,
            "collisions_active": collisions_active,
            "sublimation_active": sublimation_active_flag,
            "sinks_active": bool(sublimation_active_flag or sink_timescale_active),
            "rp_blowout_active": blowout_enabled,
            "wyatt_collisional_timescale_active": wyatt_collisional_timescale_active,
            "active_sinks": active_sinks_list,
        },
        "limitations": limitations_list,
    }
    scope_limitations_summary = copy.deepcopy(scope_limitations_base)
    scope_limitations_config = copy.deepcopy(scope_limitations_base)
    scope_limitations_config["scope"].update(
        {
            "analysis_window_basis": time_grid_info.get("t_end_basis"),
            "time_grid_dt_mode": time_grid_info.get("dt_mode"),
            "radiation_use_mars_rp": mars_rp_enabled_cfg,
            "radiation_use_solar_rp": solar_rp_requested,
        }
    )
    scope_limitations_config["active_physics"].update(
        {
            "enforce_sublimation_only": enforce_sublimation_only,
            "enforce_collisions_only": enforce_collisions_only,
            "sinks_mode": sinks_mode_value,
            "sinks_enabled_cfg": sinks_enabled_cfg,
            "sink_timescale_active": sink_timescale_active,
            "blowout_enabled_cfg": blowout_enabled_cfg,
            "rp_blowout_enabled_cfg": rp_blowout_enabled,
            "shielding_mode": shielding_mode,
            "freeze_kappa": freeze_kappa,
            "freeze_sigma": freeze_sigma,
            "tau_gate_enabled": tau_gate_enabled,
        }
    )
    scope_limitations_config["limitation_codes"] = [
        "inner_disk_only",
        "mars_rp_only",
        "short_timescale",
        "mode_switching_not_fully_coupled",
        "optically_thick_surface",
        "simplified_psd_floor",
    ]
    summary = {
        "M_loss": (M_loss_cum + M_sink_cum),
        "M_loss_from_sinks": M_sink_cum,
        "M_loss_from_sublimation": M_sublimation_cum,
        "M_loss_rp_mars": M_loss_cum,
        "M_loss_surface_solid_marsRP": M_loss_cum,
        "M_loss_hydro_escape": M_hydro_cum,
        "M_out_cum": M_loss_cum,
        "M_sink_cum": M_sink_cum,
        "orbits_completed": orbits_completed,
        "case_status": case_status,
        "beta_threshold": beta_threshold,
        "beta_at_smin_config": beta_at_smin_config,
        "beta_at_smin_effective": beta_at_smin_effective,
        "beta_at_smin": beta_at_smin_config if beta_at_smin_config is not None else beta_at_smin_effective,
        "s_blow_m": a_blow,
        "blowout_gate_mode": blowout_gate_mode,
        "chi_blow_input": chi_config_str,
        "chi_blow_eff": chi_blow_eff,
        "rho_used": rho_used,
        "Q_pr_used": qpr_mean,
        "Q_pr_blow": qpr_blow_final,
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "T_M_used": T_use,
        "T_M_used[K]": T_use,
        "T_M_source": T_M_source,
        "T_M_initial": temperature_track[0] if temperature_track else temp_runtime.initial_value,
        "T_M_final": temperature_track[-1] if temperature_track else temp_runtime.initial_value,
        "T_M_min": T_min,
        "T_M_median": T_median,
        "T_M_max": T_max,
        "beta_at_smin_min": beta_min,
        "beta_at_smin_median": beta_median,
        "beta_at_smin_max": beta_max,
        "a_blow_min": ablow_min,
        "a_blow_median": ablow_median,
        "a_blow_max": ablow_max,
        "blowout_gate_factor_min": gate_min,
        "blowout_gate_factor_median": gate_median,
        "blowout_gate_factor_max": gate_max,
        "t_solid_min": tsolid_min,
        "t_solid_median": tsolid_median,
        "t_solid_max": tsolid_max,
        "temperature_driver": temp_runtime.provenance,
        "r_m_used": r,
        "r_RM_used": r_RM,
        "r_source": r_source,
        "phi_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
        "shielding_mode": shielding_mode,
        "mass_budget_max_error_percent": mass_budget_max_error,
        "dt_over_t_blow_median": dt_over_t_blow_median,
        "config_source_path": str(config_source_path) if config_source_path is not None else None,
        "s_min_effective": s_min_effective,
        "s_min_effective[m]": s_min_effective,
        "s_min_config": s_min_config,
        "s_min_effective_gt_config": s_min_effective > s_min_config,
        "s_min_components": s_min_components,
        "enforce_mass_budget": enforce_mass_budget,
        "physics_mode": physics_mode,
        "physics_mode_source": physics_mode_source,
        "collision_solver": collision_solver_mode,
        "single_process_mode": single_process_mode,
        "single_process_mode_source": single_process_mode_source,
        "primary_scenario": primary_scenario,
        "process_overview": process_overview,
        "time_grid": {
            "basis": time_grid_info.get("t_end_basis"),
            "t_end_input": time_grid_info.get("t_end_input"),
            "t_end_s": time_grid_info.get("t_end_seconds"),
            "dt_mode": time_grid_info.get("dt_mode"),
            "dt_input": time_grid_info.get("dt_input"),
            "dt_nominal_s": time_grid_info.get("dt_nominal"),
            "dt_step_s": dt,
            "n_steps": time_grid_info.get("n_steps"),
            "dt_sources_s": time_grid_info.get("dt_sources"),
            "dt_capped_by_max_steps": time_grid_info.get("dt_capped_by_max_steps", False),
        },
    }
    summary["scope_limitations"] = scope_limitations_summary
    if phase7_enabled:
        summary.update(
            {
                "M_loss_blowout_total": M_loss_cum,
                "M_loss_sink_total": M_sink_cum,
                "M_loss_total": M_loss_cum + M_sink_cum,
                "max_mloss_rate": phase7_max_rate,
                "max_mloss_rate_time": phase7_max_rate_time,
                "median_ts_ratio": phase7_median_ts_ratio,
                "median_gate_factor": gate_median,
                "tau_gate_blocked_time_fraction": tau_gate_block_fraction,
                "phase7_diagnostics_version": phase7_schema_version,
            }
        )
    summary["inner_disk_scope"] = inner_scope_flag
    summary["analysis_window_years"] = analysis_window_years
    summary["radiation_field"] = radiation_field
    summary["primary_process"] = primary_process
    summary["primary_scenario"] = primary_scenario
    summary["collisions_active"] = collisions_active
    summary["sinks_active"] = sinks_active
    summary["sublimation_active"] = sublimation_active_flag
    summary["sublimation_location"] = sublimation_location
    summary["blowout_active"] = blowout_enabled
    summary["state_tagging_enabled"] = state_tagging_enabled
    summary["state_phase_tag"] = state_phase_tag
    summary["single_process"] = {
        "mode": single_process_mode,
        "source": single_process_mode_source,
    }
    summary["physics"] = {
        "mode": physics_mode,
        "source": physics_mode_source,
    }
    summary["phase_branching"] = {
        "enabled": phase_controller.enabled,
        "source": phase_controller.source,
        "entrypoint": phase_controller.entrypoint,
        "phase_usage_time_s": {k: float(v) for k, v in phase_usage.items()},
        "phase_method_usage_time_s": {k: float(v) for k, v in phase_method_usage.items()},
        "sink_branch_usage_time_s": {k: float(v) for k, v in sink_branch_usage.items()},
    }
    summary["radiation_tau_gate"] = {
        "enabled": tau_gate_enabled,
        "tau_max": tau_gate_threshold if tau_gate_enabled else None,
    }
    summary["solar_radiation"] = {
        "enabled": False,
        "requested": solar_rp_requested,
        "note": (
            "Solar radiation disabled (Mars-only scope)"
            if radiation_field == "mars"
            else "Radiation disabled via radiation.source='off'"
        ),
    }
    if orbits_completed > 0:
        summary["M_out_mean_per_orbit"] = M_loss_cum / orbits_completed
        summary["M_sink_mean_per_orbit"] = M_sink_cum / orbits_completed
        summary["M_loss_mean_per_orbit"] = (M_loss_cum + M_sink_cum) / orbits_completed
    if history.mass_budget_violation is not None:
        summary["mass_budget_violation"] = history.mass_budget_violation
    writer.write_summary(summary, outdir / "summary.json")
    writer.write_mass_budget(mass_budget, outdir / "checks" / "mass_budget.csv")
    if debug_sinks_enabled and debug_records:
        debug_dir = outdir / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        trace_path = debug_dir / "sinks_trace.jsonl"
        with trace_path.open("w", encoding="utf-8") as fh:
            for row in debug_records:
                fh.write(json.dumps(row) + "\n")
    e0_effective = cfg.dynamics.e0
    i0_effective = cfg.dynamics.i0

    if (
        getattr(sub_params, "_psat_last_selection", None) is None
        and sub_params.mode.lower() in {"hkl", "hkl_timescale"}
    ):
        try:
            p_sat(max(T_use, 1.0), sub_params)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(
                "Unable to resolve psat selection for provenance at T=%.1f K: %s",
                T_use,
                exc,
            )

    run_config = {
        "beta_formula": "beta = 3 σ_SB T_M^4 R_M^2 Q_pr / (4 G M_M c ρ s)",
        "s_blow_formula": "s_blow = 3 σ_SB T_M^4 R_M^2 Q_pr / (2 G M_M c ρ)",
        "defaults": {
            "Q_pr": radiation.DEFAULT_Q_PR,
            "rho": radiation.DEFAULT_RHO,
            "T_M_range_K": list(radiation.T_M_RANGE),
            "beta_threshold": radiation.BLOWOUT_BETA_THRESHOLD,
        },
        "constants": {
            "G": constants.G,
            "C": constants.C,
            "SIGMA_SB": constants.SIGMA_SB,
            "M_MARS": constants.M_MARS,
            "R_MARS": constants.R_MARS,
        },
        "run_inputs": {
            "T_M_used": T_use,
            "T_M_source": T_M_source,
            "T_M_initial": temperature_track[0] if temperature_track else temp_runtime.initial_value,
            "T_M_final": temperature_track[-1] if temperature_track else temp_runtime.initial_value,
            "rho_used": rho_used,
            "Q_pr_used": qpr_mean,
            "Q_pr_blow": qpr_blow_final,
            "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
            "phi_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
            "r_m_used": r,
            "r_RM_used": r_RM,
            "r_source": r_source,
            "rng_seed": int(seed),
            "rng_seed_expr": seed_expr,
            "rng_seed_basis": seed_basis,
            "input_config_path": str(config_source_path) if config_source_path is not None else None,
            "physics_mode": physics_mode,
            "physics_mode_source": physics_mode_source,
        },
        "init_ei": {
            "e_mode": cfg.dynamics.e_mode,
            "dr_min_m": cfg.dynamics.dr_min_m,
            "dr_max_m": cfg.dynamics.dr_max_m,
            "dr_dist": cfg.dynamics.dr_dist,
            "delta_r_sample_m": delta_r_sample,
            "e0_applied": e0_effective,
            "i_mode": cfg.dynamics.i_mode,
            "obs_tilt_deg": cfg.dynamics.obs_tilt_deg,
            "i_spread_deg": cfg.dynamics.i_spread_deg,
            "i0_applied_rad": i0_effective,
            "seed_used": int(seed),
            "e_formula_SI": "e = 1 - (R_MARS + Δr)/a; [Δr, a, R_MARS]: meters",
            "a_m_source": "geometry.r",
        },
        "git": _gather_git_info(),
        "time_grid": {
            "dt_input": time_grid_info.get("dt_input"),
            "dt_mode": time_grid_info.get("dt_mode"),
            "dt_nominal_s": time_grid_info.get("dt_nominal"),
            "dt_step_s": time_grid_info.get("dt_step"),
            "t_end_s": time_grid_info.get("t_end_seconds"),
            "t_end_basis": time_grid_info.get("t_end_basis"),
            "t_end_input": time_grid_info.get("t_end_input"),
            "n_steps": time_grid_info.get("n_steps"),
            "max_steps": MAX_STEPS,
            "dt_sources_s": time_grid_info.get("dt_sources"),
            "t_blow_nominal_s": time_grid_info.get("t_blow_nominal"),
            "dt_capped_by_max_steps": time_grid_info.get("dt_capped_by_max_steps", False),
            "scheme": "fixed-step implicit-Euler (S1)",
        },
        "physics_controls": {
            "blowout_enabled": blowout_enabled,
            "rp_blowout_enabled": rp_blowout_enabled,
            "blowout_target_phase": blowout_target_phase,
            "blowout_layer": blowout_layer_mode,
            "blowout_gate_mode": blowout_gate_mode,
            "freeze_kappa": freeze_kappa,
            "freeze_sigma": freeze_sigma,
            "shielding_mode": shielding_mode,
            "shielding_tau_fixed": tau_fixed_cfg,
            "shielding_sigma_tau1_fixed": sigma_tau1_fixed_cfg,
            "shielding_table_path": str(phi_table_path_resolved) if phi_table_path_resolved is not None else None,
            "psd_floor_mode": psd_floor_mode,
            "phase_enabled": phase_controller.enabled,
            "phase_source": phase_controller.source,
            "phase_entrypoint": phase_controller.entrypoint,
            "tau_gate_enabled": tau_gate_enabled,
            "tau_gate_tau_max": tau_gate_threshold if tau_gate_enabled else None,
            "hydro_escape_strength": getattr(hydro_cfg, "strength", None),
            "hydro_escape_temp_power": getattr(hydro_cfg, "temp_power", None),
            "radiation_use_mars_rp": mars_rp_enabled_cfg,
            "radiation_use_solar_rp": solar_rp_requested,
        },
    }
    run_config["scope_limitations"] = scope_limitations_config
    run_config["physics_mode"] = physics_mode
    run_config["physics_mode_source"] = physics_mode_source
    run_config["scope_controls"] = {
        "region": scope_region,
        "analysis_window_years": analysis_window_years,
        "inner_disk_scope": inner_scope_flag,
    }
    run_config["process_controls"] = {
        "primary_process": primary_process,
        "primary_process_cfg": primary_process_cfg,
        "primary_scenario": primary_scenario,
        "primary_field_explicit": primary_field_explicit,
        "state_tagging_enabled": state_tagging_enabled,
        "state_phase_tag": state_phase_tag,
        "physics_mode": physics_mode,
        "physics_mode_source": physics_mode_source,
        "single_process_mode": single_process_mode,
        "single_process_mode_source": single_process_mode_source,
        "collision_solver": collision_solver_mode,
        "collisions_active": collisions_active,
        "sinks_mode": sinks_mode_value,
        "sinks_enabled_cfg": sinks_enabled_cfg,
        "sinks_active": sinks_active,
        "sublimation_active": sublimation_active_flag,
        "sublimation_location": sublimation_location,
        "sink_timescale_active": sink_timescale_active,
        "blowout_active": blowout_enabled,
        "rp_blowout_enabled": rp_blowout_enabled,
    }
    run_config["single_process_resolution"] = {
        "resolved_mode": single_process_mode,
        "source": single_process_mode_source,
        "inputs": {
            "cli": mode_input_cli,
            "physics": mode_input_cfg,
            "physics_mode_cfg": physics_mode_cfg,
            "single_process_mode_cfg": single_process_mode_cfg,
            "legacy_modes": mode_input_legacy,
        },
    }
    run_config["process_overview"] = process_overview
    run_config["solar_radiation"] = {
        "enabled": False,
        "requested": solar_rp_requested,
        "note": (
            "Solar radiation disabled (Mars-only scope)"
            if radiation_field == "mars"
            else "Radiation disabled via radiation.source='off'"
        ),
    }
    temp_prov = dict(temp_runtime.provenance)
    temp_prov.setdefault("mode", temp_runtime.mode)
    temp_prov.setdefault("enabled", temp_runtime.enabled)
    temp_prov.setdefault("source", temp_runtime.source)
    run_config["temperature_driver"] = temp_prov
    run_config["T_M_used"] = float(T_use)
    run_config["rho_used"] = float(rho_used)
    run_config["Q_pr_used"] = float(qpr_mean)
    qpr_source = "override" if qpr_override is not None else "table"
    run_config["radiation_provenance"] = {
        "qpr_table_path": str(qpr_table_path_resolved) if qpr_table_path_resolved is not None else None,
        "Q_pr_override": qpr_override,
        "Q_pr_source": qpr_source,
        "Q_pr_blow": qpr_blow_final,
        "T_M_source": T_M_source,
        "radiation_field": radiation_field,
        "temperature_source": temp_runtime.source,
        "use_mars_rp": mars_rp_enabled_cfg,
        "use_solar_rp": solar_rp_requested,
    }
    psat_selection = getattr(sub_params, "_psat_last_selection", None) or {}
    psat_model_resolved = (
        psat_selection.get("psat_model_resolved")
        or sub_params.psat_model_resolved
        or sub_params.psat_model
    )
    psat_table_path = psat_selection.get("psat_table_path") or (
        str(sub_params.psat_table_path) if sub_params.psat_table_path else None
    )
    valid_config = (
        list(sub_params.valid_K) if sub_params.valid_K is not None else None
    )
    valid_active = psat_selection.get("valid_K_active")
    if isinstance(valid_active, tuple):
        valid_active = list(valid_active)
    psat_table_range = psat_selection.get("psat_table_range_K")
    if isinstance(psat_table_range, tuple):
        psat_table_range = list(psat_table_range)

    run_config["sublimation_provenance"] = {
        "sublimation_formula": "HKL",
        "mode": sub_params.mode,
        "psat_model": sub_params.psat_model,
        "psat_model_resolved": psat_model_resolved,
        "psat_selection_reason": psat_selection.get("selection_reason"),
        "alpha_evap": sub_params.alpha_evap,
        "mu": sub_params.mu,
        "A": (
            psat_selection["A_active"]
            if psat_selection.get("A_active") is not None
            else sub_params.A
        ),
        "B": (
            psat_selection["B_active"]
            if psat_selection.get("B_active") is not None
            else sub_params.B
        ),
        "P_gas": sub_params.P_gas,
        "valid_K_config": valid_config,
        "valid_K_active": valid_active,
        "psat_table_path": psat_table_path,
        "psat_table_range_K": psat_table_range,
        "psat_table_monotonic": psat_selection.get("monotonic"),
        "psat_table_buffer_K": sub_params.psat_table_buffer_K,
        "local_fit_window_K": sub_params.local_fit_window_K,
        "min_points_local_fit": sub_params.min_points_local_fit,
        "T_req": psat_selection.get("T_req"),
        "P_sat_Pa": psat_selection.get("P_sat_Pa"),
        "log10P": psat_selection.get("log10P"),
        "log10P_tabulated": psat_selection.get("log10P_tabulated"),
        "eta_instant": sub_params.eta_instant,
        "runtime_radius_m": r,
        "runtime_t_orb_s": t_orb,
    }
    writer.write_run_config(run_config, outdir / "run_config.json")

    if history.violation_triggered:
        raise MassBudgetViolationError(
            "Mass budget tolerance exceeded; see summary.json for details"
        )


def _run_phase5_variant(
    base_cfg: Config,
    variant: str,
    mode: str,
    base_outdir: Path,
    duration_years: float,
    *,
    enforce_mass_budget: bool,
) -> _Phase5VariantResult:
    """Execute a single-process variant run and capture its artifacts."""

    variant_cfg = _clone_config(base_cfg)
    if hasattr(variant_cfg, "phase5"):
        variant_cfg.phase5.compare.enable = False
    variant_cfg.single_process_mode = mode
    if hasattr(variant_cfg, "modes"):
        mode_value = "sublimation_only" if mode == "sublimation_only" else "collisional_only"
        try:
            variant_cfg.modes.single_process = mode_value
        except Exception:
            pass
    if duration_years > 0.0:
        variant_cfg.numerics.t_end_years = duration_years
        variant_cfg.numerics.t_end_orbits = None
        if hasattr(variant_cfg, "scope") and variant_cfg.scope is not None:
            variant_cfg.scope.analysis_years = duration_years
    variant_dir = base_outdir / "variants" / f"variant={variant}"
    variant_dir.mkdir(parents=True, exist_ok=True)
    variant_cfg.io.outdir = str(variant_dir)
    logger.info(
        "Phase5 comparison: running variant=%s duration=%.3f yr outdir=%s",
        variant,
        duration_years,
        variant_dir,
    )
    run_zero_d(
        variant_cfg,
        enforce_mass_budget=enforce_mass_budget,
        single_process_override=mode,
        single_process_source="phase5_compare",
    )
    summary_path = variant_dir / "summary.json"
    run_config_path = variant_dir / "run_config.json"
    summary = _read_json(summary_path)
    run_config_payload = _read_json(run_config_path)
    series_paths: Dict[str, Path] = {}
    for name in ("run.parquet", "diagnostics.parquet", "psd_hist.parquet"):
        candidate = variant_dir / "series" / name
        if candidate.exists():
            series_paths[name] = candidate
    mass_budget_path = variant_dir / "checks" / "mass_budget.csv"
    if not mass_budget_path.exists():
        mass_budget_path = None
    orbit_rollup_path = variant_dir / "orbit_rollup.csv"
    if not orbit_rollup_path.exists():
        orbit_rollup_path = None
    return _Phase5VariantResult(
        variant=variant,
        mode=mode,
        outdir=variant_dir,
        summary=summary,
        run_config=run_config_payload,
        series_paths=series_paths,
        mass_budget_path=mass_budget_path,
        orbit_rollup_path=orbit_rollup_path,
    )


def _write_phase5_comparison_products(
    base_outdir: Path,
    duration_years: float,
    results: List[_Phase5VariantResult],
) -> None:
    """Aggregate per-variant artifacts into the comparison outputs."""

    if not results:
        raise RuntimeError("Phase5 comparison runner requires at least one variant result")
    base_outdir.mkdir(parents=True, exist_ok=True)
    series_names = ("run.parquet", "diagnostics.parquet", "psd_hist.parquet")
    run_tables: Dict[str, pd.DataFrame] = {}
    for name in series_names:
        frames: List[pd.DataFrame] = []
        for res in results:
            path = res.series_paths.get(name)
            if path is None or not path.exists():
                continue
            df = pd.read_parquet(path)
            if name == "run.parquet":
                run_tables[res.variant] = df
            frames.append(df.assign(variant=res.variant, single_process_mode=res.mode))
        if frames:
            combined = pd.concat(frames, ignore_index=True)
            writer.write_parquet(combined, base_outdir / "series" / name)

    budget_frames: List[pd.DataFrame] = []
    for res in results:
        path = res.mass_budget_path
        if path is None or not path.exists():
            continue
        df = pd.read_csv(path)
        df["variant"] = res.variant
        df["single_process_mode"] = res.mode
        budget_frames.append(df)
    if budget_frames:
        checks_dir = base_outdir / "checks"
        checks_dir.mkdir(parents=True, exist_ok=True)
        pd.concat(budget_frames, ignore_index=True).to_csv(
            checks_dir / "mass_budget.csv", index=False
        )

    anchor_res = results[0]
    if anchor_res.orbit_rollup_path and anchor_res.orbit_rollup_path.exists():
        destination = base_outdir / "orbit_rollup.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(anchor_res.orbit_rollup_path, destination)

    def _mean_from_df(df: Optional[pd.DataFrame], column: str) -> float:
        if df is None or column not in df or df.empty:
            return float("nan")
        return float(df[column].mean())

    def _final_value(df: Optional[pd.DataFrame], column: str) -> Optional[float]:
        if df is None or column not in df or df.empty:
            return None
        series = df[column].dropna()
        if series.empty:
            return None
        return float(series.iloc[-1])

    comparison_rows: List[Dict[str, Any]] = []
    for res in results:
        df = run_tables.get(res.variant)
        summary = res.summary
        m_loss_sinks = float(summary.get("M_loss_from_sinks", 0.0) or 0.0)
        m_loss_sub = float(summary.get("M_loss_from_sublimation", 0.0) or 0.0)
        comparison_rows.append(
            {
                "variant": res.variant,
                "single_process_mode": res.mode,
                "duration_yr": float(summary.get("analysis_window_years", duration_years)),
                "M_loss_total": float(summary.get("M_loss", float("nan"))),
                "M_loss_blowout": float(summary.get("M_loss_rp_mars", 0.0) or 0.0),
                "M_loss_other_sinks": max(m_loss_sinks - m_loss_sub, 0.0),
                "beta_mean": _mean_from_df(df, "beta_at_smin"),
                "a_blow_mean": _mean_from_df(df, "a_blow"),
                "s_min_final": _final_value(df, "s_min"),
                "tau1_area_final": _final_value(df, "Sigma_tau1"),
                "notes": f"{res.variant} variant",
            }
        )
    if comparison_rows:
        series_dir = base_outdir / "series"
        series_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(comparison_rows).to_csv(
            series_dir / "orbit_rollup_comparison.csv", index=False
        )

    combined_summary = copy.deepcopy(anchor_res.summary)
    phase5_section = combined_summary.setdefault("phase5", {})
    variant_payloads: List[Dict[str, Any]] = []
    for res in results:
        variant_summary = res.summary
        config_hash = _hash_payload(res.run_config)
        s_min_components = variant_summary.get("s_min_components", {})
        variants_entry = {
            "variant": res.variant,
            "single_process_mode": res.mode,
            "outdir": str(res.outdir),
            "summary_path": str(res.outdir / "summary.json"),
            "run_config_path": str(res.outdir / "run_config.json"),
            "config_hash_sha256": config_hash,
            "analysis_years": variant_summary.get("analysis_window_years"),
            "r_m_used": variant_summary.get("r_m_used"),
            "s_min_initial": variant_summary.get("s_min_config", s_min_components.get("config")),
            "M_loss": variant_summary.get("M_loss"),
            "M_loss_blowout": variant_summary.get("M_loss_rp_mars"),
            "M_loss_sinks": variant_summary.get("M_loss_from_sinks"),
            "M_loss_sublimation": variant_summary.get("M_loss_from_sublimation"),
        }
        variant_payloads.append(variants_entry)
    phase5_section["compare"] = {
        "enabled": True,
        "duration_years": duration_years,
        "default_variant": anchor_res.variant,
        "variants": variant_payloads,
        "orbit_rollup_comparison_path": str(base_outdir / "series" / "orbit_rollup_comparison.csv"),
    }
    combined_summary["comparison_mode"] = "phase5_single_process"
    combined_summary["comparison_variants"] = [res.variant for res in results]
    writer.write_summary(combined_summary, base_outdir / "summary.json")

    combined_run_config = copy.deepcopy(anchor_res.run_config)
    combined_run_config["comparison_mode"] = "phase5_single_process"
    combined_run_config["phase5_compare"] = {
        "duration_years": duration_years,
        "variants": [
            {
                "variant": res.variant,
                "single_process_mode": res.mode,
                "outdir": str(res.outdir),
                "summary_path": str(res.outdir / "summary.json"),
                "run_config_path": str(res.outdir / "run_config.json"),
                "config_hash_sha256": _hash_payload(res.run_config),
            }
            for res in results
        ],
    }
    writer.write_run_config(combined_run_config, base_outdir / "run_config.json")


def run_phase5_comparison(
    cfg: Config,
    *,
    enforce_mass_budget: bool = False,
    variants_spec: Optional[List[Dict[str, str]]] = None,
) -> None:
    """Run the Phase 5 dual single-process comparison workflow."""

    compare_cfg = getattr(getattr(cfg, "phase5", None), "compare", None)
    variants = variants_spec or _prepare_phase5_variants(compare_cfg)
    duration_years = float(getattr(compare_cfg, "duration_years", 0.0) or 0.0)
    if duration_years <= 0.0:
        scope_cfg = getattr(cfg, "scope", None)
        duration_years = float(getattr(scope_cfg, "analysis_years", 2.0) or 2.0)
    base_outdir = Path(cfg.io.outdir)
    logger.info(
        "Phase5 comparison enabled: duration=%.3f yr base_outdir=%s",
        duration_years,
        base_outdir,
    )
    results: List[_Phase5VariantResult] = []
    for spec in variants:
        results.append(
            _run_phase5_variant(
                cfg,
                spec["label"],
                spec["mode"],
                base_outdir,
                duration_years,
                enforce_mass_budget=enforce_mass_budget,
            )
        )
    _write_phase5_comparison_products(base_outdir, duration_years, results)


def main(argv: Optional[List[str]] = None) -> None:
    """Command line entry point."""

    parser = argparse.ArgumentParser(description="Run a simple Mars disk model")
    parser.add_argument("--config", type=Path, required=True, help="Path to YAML configuration")
    parser.add_argument(
        "--enforce-mass-budget",
        action="store_true",
        help=(
            "Abort the run when the mass budget tolerance (%.3f%%) is exceeded"
            % MASS_BUDGET_TOLERANCE_PERCENT
        ),
    )
    parser.add_argument(
        "--sinks",
        choices=["none", "sublimation"],
        help="Override sinks.mode from the CLI (defaults to configuration file)",
    )
    parser.add_argument(
        "--single-process-mode",
        choices=["off", "sublimation_only", "collisions_only"],
        help="Override physics.single_process_mode from the CLI",
    )
    parser.add_argument(
        "--compare-single-processes",
        action="store_true",
        help="Run both single-process variants sequentially for comparison output.",
    )
    parser.add_argument(
        "--override",
        action="append",
        nargs="+",
        metavar="PATH=VALUE",
        help=(
            "Apply configuration overrides using dotted paths; e.g. "
            "--override physics.blowout.enabled=false"
        ),
    )
    args = parser.parse_args(argv)

    override_list: List[str] = []
    if args.override:
        for group in args.override:
            override_list.extend(group)
    cfg = load_config(args.config, overrides=override_list)
    if args.sinks is not None:
        cfg.sinks.mode = args.sinks
    if args.single_process_mode is not None:
        cfg.single_process_mode = args.single_process_mode
    compare_block = getattr(getattr(cfg, "phase5", None), "compare", None)
    compare_config_enabled = bool(getattr(compare_block, "enable", False)) if compare_block else False
    compare_requested = bool(args.compare_single_processes or compare_config_enabled)
    if compare_requested:
        if compare_block is None:
            raise ValueError(
                "--compare-single-processes requires phase5.compare to define mode_a/mode_b"
            )
        variants_spec = _prepare_phase5_variants(compare_block)
        if args.compare_single_processes:
            compare_block.enable = True
        run_phase5_comparison(
            cfg,
            enforce_mass_budget=args.enforce_mass_budget,
            variants_spec=variants_spec,
        )
    else:
        run_zero_d(
            cfg,
            enforce_mass_budget=args.enforce_mass_budget,
            single_process_override=args.single_process_mode,
            single_process_source="cli" if args.single_process_mode is not None else None,
        )


    if __name__ == "__main__":  # pragma: no cover - CLI entry point
        logging.basicConfig(level=logging.INFO)
        main()

__all__ = [
    "RunConfig",
    "RunState",
    "step",
    "run_n_steps",
    "load_config",
    "run_zero_d",
    "run_phase5_comparison",
    "main",
    "MassBudgetViolationError",
]
