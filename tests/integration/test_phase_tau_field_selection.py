import inspect

import pytest

from marsdisk import run


def test_compute_phase_tau_fields_returns_los_only() -> None:
    tau_used, tau_los = run.compute_phase_tau_fields(
        kappa_surf=2.0,
        sigma_for_tau=0.5,
        los_factor=3.0,
        phase_tau_field="los",
    )
    assert tau_los == pytest.approx(3.0)
    assert tau_used == pytest.approx(tau_los)


def test_log_stage_extra_is_keyword_only() -> None:
    sig = inspect.signature(run._log_stage)
    params = list(sig.parameters.values())
    assert len(params) == 2
    assert params[1].name == "extra"
    assert params[1].kind is inspect.Parameter.KEYWORD_ONLY
