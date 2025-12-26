from __future__ import annotations

from pathlib import Path
import math

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, grid, run as run_module, schema
from marsdisk.physics import collisions_smol, psd, radiation, surface


def _reference_rebin_dnds(
    psd_state: dict[str, np.ndarray | float],
    *,
    ds_dt: float,
    dt: float,
    floor: float,
) -> tuple[np.ndarray, np.ndarray]:
    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    edges = np.asarray(psd_state["edges"], dtype=float)
    number = np.asarray(psd_state["number"], dtype=float)

    counts = number * widths
    ds_step = float(ds_dt * dt)
    new_counts = np.zeros_like(counts)
    accum_sizes = np.zeros_like(counts)
    for idx, count in enumerate(counts):
        if count <= 0.0 or not np.isfinite(count):
            continue
        s_new = sizes[idx] + ds_step
        if not np.isfinite(s_new):
            continue
        if s_new < floor:
            s_new = floor
        target = int(np.searchsorted(edges, s_new, side="right") - 1)
        target = max(0, min(target, new_counts.size - 1))
        new_counts[target] += count
        accum_sizes[target] += count * s_new

    new_sizes = sizes.copy()
    mask = new_counts > 0.0
    new_sizes[mask] = accum_sizes[mask] / new_counts[mask]
    new_sizes = np.maximum(new_sizes, float(floor))
    new_number = np.zeros_like(number)
    new_number[mask] = new_counts[mask] / widths[mask]

    tmp_state = {"sizes": new_sizes, "widths": widths, "number": new_number}
    psd.sanitize_and_normalize_number(tmp_state)
    return np.asarray(tmp_state["number"], dtype=float), np.asarray(tmp_state["sizes"], dtype=float)


def test_apply_uniform_size_drift_dnds_rebin_matches_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    sizes = np.array([1.0e-6, 2.0e-6, 4.0e-6])
    widths = np.array([0.5e-6, 1.0e-6, 2.0e-6])
    edges = np.array([0.75e-6, 1.25e-6, 2.5e-6, 5.0e-6])
    number = np.array([1.0, 0.2, 0.1])
    psd_state = {
        "sizes": sizes,
        "widths": widths,
        "edges": edges,
        "number": number,
        "rho": 3000.0,
    }

    ds_dt = 3.0e-7
    dt = 1.0
    floor = 1.0e-7

    monkeypatch.setattr(psd, "_USE_NUMBA", False)
    psd._NUMBA_FAILED = False

    expected_number, _ = _reference_rebin_dnds(psd_state, ds_dt=ds_dt, dt=dt, floor=floor)

    working = {k: np.array(v, copy=True) if isinstance(v, np.ndarray) else v for k, v in psd_state.items()}
    psd.apply_uniform_size_drift(working, ds_dt=ds_dt, dt=dt, floor=floor, sigma_surf=1.0)

    np.testing.assert_allclose(working["number"], expected_number, rtol=1.0e-6, atol=0.0)


def _self_consistent_blowout(
    rho: float,
    T_M: float,
    qpr_func: callable,
    *,
    n_iter: int = 20,
) -> float:
    kappa = radiation.blowout_radius(rho, T_M, Q_pr=1.0)
    s_val = float(kappa)
    for _ in range(n_iter):
        s_val = float(kappa) * float(qpr_func(s_val, T_M))
    return s_val


def test_blowout_radius_size_dependent_qpr_consistent() -> None:
    def qpr_func(s: float, _T: float) -> float:
        s0 = 1.0e-3
        return 0.05 + 0.95 * (s / (s + s0))

    rho = 3000.0
    T_M = 2000.0
    s_direct = radiation.blowout_radius(rho, T_M, interp=qpr_func)
    s_self = _self_consistent_blowout(rho, T_M, qpr_func)
    assert s_direct == pytest.approx(s_self, rel=1.0e-3)


def test_surface_ode_chi_blow_ignored() -> None:
    sigma = 1.0
    prod = 0.0
    Omega = 2.0
    dt = 0.1

    res = surface.step_surface_density_S1(sigma, prod, dt, Omega)

    chi_blow = 2.0
    t_blow_expected = chi_blow / Omega
    sigma_expected = (sigma + dt * prod) / (1.0 + dt / t_blow_expected)
    outflux_expected = sigma_expected / t_blow_expected

    assert abs(res.outflux - outflux_expected) / outflux_expected > 0.2


def _surface_ode_config(
    outdir: Path,
    dt_init: float,
    n_steps: int,
    *,
    h_over_r: float,
) -> schema.Config:
    t_end_s = dt_init * n_steps
    geometry = schema.Geometry(mode="0D")
    material = schema.Material(rho=3000.0)
    disk = schema.Disk(
        geometry=schema.DiskGeometry(
            r_in_RM=4.13,
            r_out_RM=4.13,
            r_profile="uniform",
            p_index=0.0,
        )
    )
    radiation_cfg = schema.Radiation(TM_K=2000.0, Q_pr=1.0)
    sizes = schema.Sizes(s_min=1.0e-6, s_max=1.0e-2, n_bins=24)
    initial = schema.Initial(mass_total=1.0e-12, s0_mode="upper")
    dynamics = schema.Dynamics(
        e0=0.01,
        i0=0.01,
        t_damp_orbits=100.0,
        f_wake=1.0,
        e_mode="fixed",
        i_mode="fixed",
    )
    psd_cfg = schema.PSD(alpha=3.5, wavy_strength=0.0)
    qstar_cfg = schema.QStar(Qs=1e3, a_s=1.0, B=1.0, b_g=1.0, v_ref_kms=[1.0])
    numerics = schema.Numerics(
        t_end_years=t_end_s / run_module.SECONDS_PER_YEAR,
        dt_init=dt_init,
    )
    io = schema.IO(outdir=outdir)
    sinks = schema.Sinks(mode="none", enable_sublimation=False)
    shielding = schema.Shielding(
        mode="off",
        los_geometry=schema.Shielding.LOSGeometry(
            h_over_r=h_over_r,
            path_multiplier=1.0,
        ),
    )
    surface_cfg = schema.Surface(collision_solver="surface_ode", use_tcoll=True)

    return schema.Config(
        geometry=geometry,
        disk=disk,
        material=material,
        radiation=radiation_cfg,
        sizes=sizes,
        initial=initial,
        dynamics=dynamics,
        psd=psd_cfg,
        qstar=qstar_cfg,
        numerics=numerics,
        io=io,
        sinks=sinks,
        shielding=shielding,
        surface=surface_cfg,
    )


def test_tcoll_uses_tau_los_factor(tmp_path: Path) -> None:
    outdir = tmp_path / "surface_ode"
    dt_init = 200.0
    cfg = _surface_ode_config(outdir, dt_init, n_steps=2, h_over_r=0.1)

    run_module.run_zero_d(cfg)

    series = pd.read_parquet(outdir / "series" / "run.parquet")
    row = series.iloc[-1]
    t_coll = float(row["t_coll"])
    tau_los = row.get("tau_los_mars", row.get("tau"))
    tau_los = float(tau_los)

    r = cfg.disk.geometry.r_in_RM * constants.R_MARS
    Omega = grid.omega_kepler(r)
    los_geom = cfg.shielding.los_geometry
    los_factor = los_geom.path_multiplier / los_geom.h_over_r
    if los_factor < 1.0:
        los_factor = 1.0

    t_coll_los = 1.0 / (Omega * tau_los)
    t_coll_vert = 1.0 / (Omega * (tau_los / los_factor))

    assert math.isfinite(t_coll) and t_coll > 0.0
    assert math.isfinite(tau_los) and tau_los > 0.0
    assert math.isclose(t_coll, t_coll_los, rel_tol=1.0e-3)
    assert math.isclose(t_coll_vert / t_coll, los_factor, rel_tol=1.0e-3)


def test_fragment_tensor_largest_remnant_bin_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    sizes = np.array([1.0, 10.0, 100.0], dtype=float)
    widths = np.array([1.0, 10.0, 100.0], dtype=float)
    edges = np.array([0.5, 5.5, 55.0, 155.0], dtype=float)
    rho = 3000.0
    masses = (4.0 / 3.0) * np.pi * rho * sizes**3

    f_lr_val = 0.05

    def _const_f_lr(q_r: np.ndarray, q_star: np.ndarray) -> np.ndarray:
        return np.full_like(q_r, f_lr_val, dtype=float)

    monkeypatch.setattr(collisions_smol, "_USE_NUMBA", False)
    monkeypatch.setattr(collisions_smol, "largest_remnant_fraction_array", _const_f_lr)

    Y = collisions_smol._fragment_tensor(
        sizes, masses, edges, v_rel=1.0, rho=rho, alpha_frag=3.5, use_numba=False
    )

    i = j = 2
    k_lr = max(i, j)
    m_tot = masses[i] + masses[j]
    s_lr = (3.0 * f_lr_val * m_tot / (4.0 * np.pi * rho)) ** (1.0 / 3.0)
    k_expected = int(np.searchsorted(edges, s_lr, side="right") - 1)
    k_expected = max(0, min(k_expected, sizes.size - 1))
    assert k_expected < k_lr

    left_edges = np.maximum(edges[:-1], 1.0e-30)
    right_edges = np.maximum(edges[1:], left_edges)
    power = 1.0 - 3.5
    bin_integrals = (right_edges**power - left_edges**power) / power
    weights = bin_integrals[: k_lr + 1]
    weights /= np.sum(weights)
    expected_y = f_lr_val + (1.0 - f_lr_val) * weights[k_lr]

    assert np.isclose(Y[k_lr, i, j], expected_y, rtol=1.0e-6, atol=0.0)
