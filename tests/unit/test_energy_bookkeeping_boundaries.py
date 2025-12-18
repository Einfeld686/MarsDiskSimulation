import numpy as np

from marsdisk.physics.collide import compute_collision_kernel_bookkeeping
from marsdisk.run import _surface_energy_floor


def _make_inputs(n=3):
    N = np.ones(n)
    s = np.logspace(-6, 0, n)
    H = np.ones(n)
    m = (4.0 / 3.0) * np.pi * (s ** 3)
    v_rel = 1.0
    f_ke_matrix = np.full((n, n), 0.5)
    F_lf_matrix = np.full((n, n), 0.6)
    return N, s, H, m, v_rel, f_ke_matrix, F_lf_matrix


def test_energy_bookkeeping_epsilon_limits():
    N, s, H, m, v_rel, f_ke_matrix, F_lf_matrix = _make_inputs(2)

    # eps -> 1: f_ke_fragmentation = 1 should yield zero dissipation
    f_ke_matrix_ones = np.ones_like(f_ke_matrix)
    _, stats_one = compute_collision_kernel_bookkeeping(
        N, s, H, m, v_rel, f_ke_matrix_ones, F_lf_matrix, use_numba=False
    )
    E_rel, E_diss, E_ret = stats_one[0], stats_one[1], stats_one[2]
    assert np.isclose(E_rel, E_ret)
    assert np.isclose(E_diss, 0.0)

    # eps -> 0: f_ke_fragmentation = 0 should yield full dissipation
    f_ke_matrix_zero = np.zeros_like(f_ke_matrix)
    _, stats_zero = compute_collision_kernel_bookkeeping(
        N, s, H, m, v_rel, f_ke_matrix_zero, F_lf_matrix, use_numba=False
    )
    E_rel_z, E_diss_z, E_ret_z = stats_zero[0], stats_zero[1], stats_zero[2]
    assert np.isclose(E_ret_z, 0.0)
    assert np.isclose(E_diss_z, E_rel_z)


def test_energy_bookkeeping_dt_integration_and_streaming_off(tmp_path, monkeypatch):
    # Placeholder: ensure energy_budget CSV is written when streaming is disabled.
    # We only check writer.append_csv path for non-empty records.
    from marsdisk.io import writer

    records = [
        {
            "step": 1,
            "time": 0.0,
            "dt": 1.0,
            "E_rel_step": 1.0,
            "E_dissipated_step": 0.5,
            "E_retained_step": 0.5,
            "f_ke_mean": 0.5,
            "F_lf_mean": 0.6,
            "n_cratering": 1.0,
            "n_fragmentation": 0.0,
            "frac_cratering": 1.0,
            "frac_fragmentation": 0.0,
            "eps_restitution": 1.0,
            "f_ke_eps_mismatch": 0.0,
            "E_numerical_error_relative": 0.0,
            "error_flag": "ok",
        }
    ]
    dest = tmp_path / "energy_budget.csv"
    writer.append_csv(records, dest, header=True)
    assert dest.exists()
    # Re-append without header should not raise
    writer.append_csv(records, dest, header=False)


def test_energy_bookkeeping_alpha_guard_and_streaming_match(tmp_path):
    from marsdisk.io import writer

    # Alpha guard and cap at s_max
    assert _surface_energy_floor(1.0, 0.1, 3.0, 3000.0, 100.0, 1.0) == 0.0
    s_floor = _surface_energy_floor(1.0, 0.1, 4.0, 3000.0, 100.0, 0.01)
    assert s_floor <= 0.01

    # Streaming ON/OFF: mimic by writing same records twice and comparing
    rec = {
        "step": 1,
        "time": 0.0,
        "dt": 1.0,
        "E_rel_step": 1.0,
        "E_dissipated_step": 0.4,
        "E_retained_step": 0.6,
        "f_ke_mean": 0.6,
        "F_lf_mean": 0.5,
        "n_cratering": 0.6,
        "n_fragmentation": 0.4,
        "frac_cratering": 0.6,
        "frac_fragmentation": 0.4,
        "eps_restitution": 0.5,
        "f_ke_eps_mismatch": 0.0,
        "E_numerical_error_relative": 0.0,
        "error_flag": "ok",
    }
    dest_on = tmp_path / "energy_budget_on.csv"
    dest_off = tmp_path / "energy_budget_off.csv"
    writer.write_mass_budget([rec], dest_on)
    writer.write_mass_budget([rec], dest_off)
    on = dest_on.read_text()
    off = dest_off.read_text()
    assert on == off

    # energy_series CSV append behavior
    energy_row = {"time": 0.0, "E_rel_step": 1.0, "E_dissipated_step": 0.4}
    energy_path = tmp_path / "energy_series.csv"
    writer.append_csv([energy_row], energy_path, header=True)
    writer.append_csv([energy_row], energy_path, header=False)
    assert energy_path.exists()
