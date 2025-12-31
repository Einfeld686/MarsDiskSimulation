from __future__ import annotations

from pathlib import Path
import copy
import json
import math

import numpy as np
import pandas as pd
import pytest

from marsdisk import constants, grid, run as run_module, schema
from marsdisk.physics import (
    collisions_smol,
    psd,
    radiation,
    sinks,
    smol,
    sublimation,
    supply,
    surface,
)


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


def test_surface_ode_respects_t_blow() -> None:
    sigma = 1.0
    prod = 0.0
    Omega = 2.0
    dt = 0.1

    chi_blow = 2.0
    t_blow_expected = chi_blow / Omega
    res = surface.step_surface_density_S1(sigma, prod, dt, Omega, t_blow=t_blow_expected)
    sigma_expected = (sigma + dt * prod) / (1.0 + dt / t_blow_expected)
    outflux_expected = sigma_expected / t_blow_expected

    assert res.outflux == pytest.approx(outflux_expected, rel=1.0e-6)


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
        e_profile=schema.DynamicsEccentricityProfile(mode="off"),
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


def _blowout_record_config(outdir: Path, *, s_min: float) -> schema.Config:
    t_end_s = 200.0
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
    sizes = schema.Sizes(s_min=s_min, s_max=1.0e-3, n_bins=16)
    initial = schema.Initial(mass_total=1.0e-12, s0_mode="upper")
    dynamics = schema.Dynamics(
        e0=0.01,
        i0=0.01,
        t_damp_orbits=100.0,
        f_wake=1.0,
        e_mode="fixed",
        i_mode="fixed",
        e_profile=schema.DynamicsEccentricityProfile(mode="off"),
    )
    psd_cfg = schema.PSD(alpha=3.5, wavy_strength=0.0)
    qstar_cfg = schema.QStar(Qs=1e3, a_s=1.0, B=1.0, b_g=1.0, v_ref_kms=[1.0])
    numerics = schema.Numerics(
        t_end_years=t_end_s / run_module.SECONDS_PER_YEAR,
        dt_init=t_end_s / 2.0,
    )
    io = schema.IO(outdir=outdir)
    sinks_cfg = schema.Sinks(mode="none", enable_sublimation=False)
    shielding = schema.Shielding(mode="off")
    surface_cfg = schema.Surface(collision_solver="surface_ode", use_tcoll=False)

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
        sinks=sinks_cfg,
        shielding=shielding,
        surface=surface_cfg,
    )


def test_tcoll_uses_vertical_tau(tmp_path: Path) -> None:
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

    tau_vert = tau_los / los_factor
    t_coll_los = 1.0 / (Omega * tau_los)
    t_coll_vert = 1.0 / (Omega * tau_vert)

    assert math.isfinite(t_coll) and t_coll > 0.0
    assert math.isfinite(tau_los) and tau_los > 0.0
    assert math.isclose(t_coll, t_coll_vert, rel_tol=1.0e-3)
    assert math.isclose(t_coll / t_coll_los, los_factor, rel_tol=1.0e-3)


def test_fragment_tensor_largest_remnant_bin_matches_size(monkeypatch: pytest.MonkeyPatch) -> None:
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
    weights = bin_integrals[: k_expected + 1]
    weights /= np.sum(weights)
    expected_y = f_lr_val + (1.0 - f_lr_val) * weights[k_expected]

    assert np.isclose(Y[k_expected, i, j], expected_y, rtol=1.0e-6, atol=0.0)
    assert Y[k_lr, i, j] == pytest.approx(0.0, abs=1.0e-12)


def test_blowout_recorded_matches_physical_radius(tmp_path: Path) -> None:
    s_min_config = 1.0e-5
    outdir = tmp_path / "blowout_record"
    cfg = _blowout_record_config(outdir, s_min=s_min_config)

    run_module.run_zero_d(cfg)

    summary = json.loads((outdir / "summary.json").read_text())
    s_blow_recorded = float(summary["s_blow_m"])
    s_blow_effective = float(summary["s_blow_m_effective"])
    s_blow_physical = radiation.blowout_radius(
        cfg.material.rho,
        cfg.radiation.TM_K,
        Q_pr=cfg.radiation.Q_pr,
    )

    assert s_blow_physical < s_min_config
    assert s_blow_recorded == pytest.approx(s_blow_physical, rel=1.0e-3, abs=0.0)
    assert s_blow_effective == pytest.approx(s_min_config, rel=1.0e-12, abs=0.0)


def test_blowout_components_expose_raw_and_effective(tmp_path: Path) -> None:
    s_min_config = 1.0e-5
    outdir = tmp_path / "blowout_components"
    cfg = _blowout_record_config(outdir, s_min=s_min_config)

    run_module.run_zero_d(cfg)

    summary = json.loads((outdir / "summary.json").read_text())
    components = summary["s_min_components"]

    assert components["blowout"] == pytest.approx(components["blowout_raw"])
    assert components["blowout_effective"] == pytest.approx(s_min_config, rel=1.0e-12, abs=0.0)


def test_sublimation_sink_reference_timescale_uses_inverse_omega(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, float] = {}

    def _fake_s_sink(T: float, rho: float, t_ref: float, params: object) -> float:
        seen["t_ref"] = float(t_ref)
        return 1.0

    monkeypatch.setattr(sinks, "s_sink_from_timescale", _fake_s_sink)
    opts = sinks.SinkOptions(enable_sublimation=True)
    Omega = 2.5

    sinks.total_sink_timescale(1500.0, 3000.0, Omega, opts, s_ref=1.0e-6)

    assert "t_ref" in seen
    expected = 1.0 / Omega
    assert math.isclose(seen["t_ref"], expected, rel_tol=1.0e-12, abs_tol=0.0)


def test_powerlaw_injection_matches_exact_log_edges_within_tolerance() -> None:
    s_min = 1.0e-6
    s_max = 3.0
    n_bins = 40
    psd_state = psd.update_psd_state(
        s_min=s_min,
        s_max=s_max,
        alpha=1.5,
        wavy_strength=0.0,
        n_bins=n_bins,
        rho=3000.0,
    )

    sizes = np.asarray(psd_state["sizes"], dtype=float)
    widths = np.asarray(psd_state["widths"], dtype=float)
    edges = np.asarray(psd_state["edges"], dtype=float)
    rho = 3000.0
    m_k = (4.0 / 3.0) * np.pi * rho * sizes**3
    prod_rate = 1.0e-9
    q = 3.5

    F_code = collisions_smol.supply_mass_rate_to_number_source(
        prod_rate,
        sizes,
        m_k,
        s_min_eff=s_min,
        widths=widths,
        mode="powerlaw_bins",
        q=q,
    )

    left_edges = np.maximum(edges[:-1], s_min)
    right_edges = np.minimum(edges[1:], float(np.max(sizes)))
    mask = right_edges > left_edges
    weights = np.zeros_like(sizes, dtype=float)
    power = 1.0 - q
    if np.any(mask):
        weights[mask] = (right_edges[mask] ** power - left_edges[mask] ** power) / power
    weights = np.where(np.isfinite(weights) & (weights > 0.0), weights, 0.0)
    mass_sum = float(np.sum(weights * m_k))
    F_exact = np.zeros_like(sizes, dtype=float)
    positive = (weights > 0.0) & (m_k > 0.0)
    if mass_sum > 0.0 and np.any(positive):
        F_exact[positive] = weights[positive] * prod_rate / mass_sum

    assert np.isclose(np.sum(m_k * F_code), prod_rate, rtol=1.0e-6, atol=0.0)
    rel = np.abs((F_code[F_exact > 0.0] - F_exact[F_exact > 0.0]) / F_exact[F_exact > 0.0])
    assert float(np.max(rel)) <= 0.1


def test_sublimation_timescale_includes_eta_factor() -> None:
    params = sublimation.SublimationParams(
        mode="logistic",
        eta_instant=0.1,
        T_sub=1200.0,
        dT=100.0,
    )
    opts = sinks.SinkOptions(enable_sublimation=True, sub_params=params)
    T_use = 1500.0
    rho = 3000.0
    Omega = 2.0
    s_ref = 1.0e-6

    result = sinks.total_sink_timescale(T_use, rho, Omega, opts, s_ref=s_ref)
    assert result.t_sink is not None

    t_ref = 1.0 / Omega
    s_sink = sublimation.s_sink_from_timescale(T_use, rho, t_ref, params)
    expected_with_eta = params.eta_instant * t_ref * s_ref / s_sink

    assert math.isclose(result.t_sink, expected_with_eta, rel_tol=1.0e-12, abs_tol=0.0)


def test_wavy_decay_modulates_wavy_pattern() -> None:
    base_kwargs = dict(
        s_min=1.0e-6,
        s_max=1.0e-4,
        alpha=1.5,
        wavy_strength=0.2,
        n_bins=16,
        rho=3000.0,
    )
    state_no_decay = psd.update_psd_state(**base_kwargs, wavy_decay=0.0)
    state_decay = psd.update_psd_state(**base_kwargs, wavy_decay=2.0)

    number_no = np.asarray(state_no_decay["number"], dtype=float)
    number_decay = np.asarray(state_decay["number"], dtype=float)
    assert not np.allclose(number_no, number_decay, rtol=0.0, atol=0.0)


def test_blowout_rate_uses_pre_step_number_density() -> None:
    psd_state = psd.update_psd_state(
        s_min=1.0e-6,
        s_max=1.0e-5,
        alpha=3.5,
        wavy_strength=0.0,
        n_bins=4,
        rho=3000.0,
    )
    psd_state_before = copy.deepcopy(psd_state)
    sigma_surf = 1.0
    t_blow = 10.0
    dt = 5.0
    a_blow = 1.0e-3

    res = collisions_smol.step_collisions_smol_0d(
        psd_state,
        sigma_surf,
        dt=dt,
        prod_subblow_area_rate=0.0,
        r=1.0,
        Omega=1.0,
        t_blow=t_blow,
        a_blow=a_blow,
        rho=3000.0,
        e_value=0.0,
        i_value=0.0,
        sigma_tau1=None,
        enable_blowout=True,
        t_sink=None,
        ds_dt_val=None,
        s_min_effective=float(psd_state_before["s_min"]),
        collisions_enabled=False,
    )

    sizes_old, _, m_old, N_old, _ = smol.psd_state_to_number_density(
        psd_state_before, sigma_surf, rho_fallback=3000.0
    )
    sizes_new, _, m_new, N_new, _ = smol.psd_state_to_number_density(
        res.psd_state, res.sigma_after, rho_fallback=3000.0
    )
    np.testing.assert_allclose(sizes_old, sizes_new, rtol=0.0, atol=0.0)
    np.testing.assert_allclose(m_old, m_new, rtol=0.0, atol=0.0)

    S_blow = np.where(sizes_old <= a_blow, 1.0 / t_blow, 0.0)
    mass_loss_pre = float(np.sum(m_old * S_blow * N_old))
    mass_loss_post = float(np.sum(m_old * S_blow * N_new))

    assert res.mass_loss_rate_blowout == pytest.approx(mass_loss_pre, rel=1.0e-12, abs=0.0)
    expected_ratio = 1.0 - dt / t_blow
    assert mass_loss_post == pytest.approx(mass_loss_pre * expected_ratio, rel=1.0e-6, abs=0.0)
    assert mass_loss_post < mass_loss_pre


def test_supply_table_time_axis_is_raw_seconds(tmp_path: Path) -> None:
    csv_text = "t,rate\n0,1\n1,2\n2,3\n"
    path = tmp_path / "supply_table.csv"
    path.write_text(csv_text)
    table = supply._TableData.load(path)
    value_year = table.interp(1.0, 0.0)
    value_seconds = table.interp(run_module.SECONDS_PER_YEAR, 0.0)

    assert value_year == pytest.approx(2.0, rel=0.0, abs=0.0)
    assert value_seconds == pytest.approx(3.0, rel=0.0, abs=0.0)


def test_supply_table_time_axis_year_unit_converts(tmp_path: Path) -> None:
    csv_text = "t,rate\n0,1\n1,2\n2,3\n"
    path = tmp_path / "supply_table_year.csv"
    path.write_text(csv_text)
    table_cfg = schema.SupplyTable(path=path, time_unit="year")
    spec = schema.Supply(mode="table", table=table_cfg)

    value_seconds = supply._rate_basic(run_module.SECONDS_PER_YEAR, 0.0, spec)

    assert value_seconds == pytest.approx(2.0, rel=0.0, abs=0.0)


def test_kernel_scale_height_uses_i0_directly() -> None:
    dynamics_cfg = schema.Dynamics(
        e0=0.01,
        i0=30.0,
        i0_unit="deg",
        t_damp_orbits=10.0,
        f_wake=1.0,
        e_mode="fixed",
        i_mode="fixed",
        e_profile=schema.DynamicsEccentricityProfile(mode="off"),
    )
    sizes = np.array([1.0e-6, 2.0e-6], dtype=float)
    a_orbit_m = 1.0e7
    state = collisions_smol.compute_kernel_ei_state(
        dynamics_cfg,
        tau_eff=0.0,
        a_orbit_m=a_orbit_m,
        v_k=1.0e3,
        sizes=sizes,
    )
    H_over_a = float(state.H_k[0] / a_orbit_m)
    expected = math.radians(30.0)

    assert H_over_a == pytest.approx(expected, rel=1.0e-12, abs=0.0)
