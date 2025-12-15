import inspect

import pytest

from marsdisk import run


def test_compute_phase_tau_fields_switches_between_vertical_and_los() -> None:
    tau_used_vert, tau_vertical, tau_los = run.compute_phase_tau_fields(
        kappa_surf=2.0,
        sigma_for_tau=0.5,
        los_factor=3.0,
        phase_tau_field="vertical",
    )
    assert tau_vertical == pytest.approx(1.0)
    assert tau_los == pytest.approx(3.0)
    assert tau_used_vert == pytest.approx(tau_vertical)

    tau_used_los, tau_vertical_los, tau_los_los = run.compute_phase_tau_fields(
        kappa_surf=2.0,
        sigma_for_tau=0.5,
        los_factor=3.0,
        phase_tau_field="los",
    )
    assert tau_vertical_los == pytest.approx(tau_vertical)
    assert tau_los_los == pytest.approx(tau_los)
    assert tau_used_los == pytest.approx(tau_los_los)


def test_log_stage_extra_is_keyword_only() -> None:
    sig = inspect.signature(run._log_stage)
    params = list(sig.parameters.values())
    assert len(params) == 2
    assert params[1].name == "extra"
    assert params[1].kind is inspect.Parameter.KEYWORD_ONLY
