from __future__ import annotations

import pytest

from marsdisk import constants
from marsdisk.physics import phase
from marsdisk.schema import PhaseConfig


@pytest.fixture()
def siO2_evaluator() -> phase.PhaseEvaluator:
    cfg = PhaseConfig(enabled=True, source="map")
    return phase.PhaseEvaluator.from_config(cfg)


def test_siO2_map_solid_branch(siO2_evaluator: phase.PhaseEvaluator) -> None:
    decision, bulk = siO2_evaluator.evaluate_with_bulk(
        temperature_K=1400.0,
        pressure_Pa=0.0,
        tau=0.0,
        radius_m=2.0 * constants.R_MARS,
        time_s=0.0,
        T0_K=2000.0,
    )
    assert decision.used_map and bulk.used_map
    assert bulk.state == "solid_dominated"
    total = bulk.f_solid + bulk.f_liquid + bulk.f_vapor
    assert total == pytest.approx(1.0, abs=1e-6)
    assert bulk.f_solid >= bulk.f_liquid
