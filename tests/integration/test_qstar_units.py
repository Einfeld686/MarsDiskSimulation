import numpy as np
import pytest

from marsdisk.physics import qstar


@pytest.fixture(autouse=True)
def _reset_qstar_state():
    """Restore the qstar unit system and clamp counters after each test."""

    original_units = qstar.get_coeff_unit_system()
    original_mu = qstar.get_gravity_velocity_mu()
    qstar.reset_velocity_clamp_stats()
    yield
    qstar.set_coeff_unit_system(original_units)
    qstar.set_gravity_velocity_mu(original_mu)
    qstar.reset_velocity_clamp_stats()


def test_ba99_cgs_conversion_matches_expected_values():
    qstar.set_coeff_unit_system("ba99_cgs")
    val_3 = qstar.compute_q_d_star_F1(1.0, 3000.0, 3.0)
    val_5 = qstar.compute_q_d_star_F1(1.0, 3000.0, 5.0)
    val_4 = qstar.compute_q_d_star_F1(1.0, 3000.0, 4.0)

    assert val_3 == pytest.approx(608.2775227337039)
    assert val_5 == pytest.approx(1216.5393012436002)
    assert val_4 == pytest.approx(912.408411988652)


def test_si_mode_preserves_legacy_magnitude_and_array_agrees():
    qstar.set_coeff_unit_system("si")
    scalar_val = qstar.compute_q_d_star_F1(1.0, 3000.0, 3.0)
    array_val = qstar.compute_q_d_star_array(
        np.array([1.0, 1.0]), 3000.0, np.array([3.0, 3.0])
    )

    assert scalar_val == pytest.approx(35000900.0)
    assert np.allclose(array_val, scalar_val)


def test_velocity_clamping_counts_and_outputs():
    qstar.set_coeff_unit_system("ba99_cgs")
    qstar.set_gravity_velocity_mu(0.45)
    expected = np.array(
        [
            qstar.compute_q_d_star_F1(1.0, 3000.0, 1.0),
            qstar.compute_q_d_star_F1(1.0, 3000.0, 10.0),
        ]
    )
    qstar.reset_velocity_clamp_stats()
    res = qstar.compute_q_d_star_array(
        np.array([1.0, 1.0]),
        3000.0,
        np.array([1.0, 10.0]),
    )

    assert np.allclose(res, expected)
    stats = qstar.get_velocity_clamp_stats()
    assert stats["below"] == 1
    assert stats["above"] == 1
    assert res[0] < qstar.compute_q_d_star_F1(1.0, 3000.0, 3.0)
    assert res[1] > qstar.compute_q_d_star_F1(1.0, 3000.0, 5.0)
