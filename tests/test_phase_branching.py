from __future__ import annotations

import math

import pytest

from marsdisk.physics import phase
from marsdisk import schema
from marsdisk.schema import PhaseConfig, PhaseThresholds, PhaseMapConfig, HydroEscapeConfig


def test_phase_threshold_fallback_handles_tau_and_pressure() -> None:
    cfg = PhaseConfig(
        enabled=True,
        source="threshold",
        thresholds=PhaseThresholds(T_condense_K=1600.0, T_vaporize_K=2000.0, P_ref_bar=1.0, tau_ref=1.0),
    )
    evaluator = phase.PhaseEvaluator(cfg)

    decision_solid = evaluator.evaluate(temperature_K=1500.0, pressure_Pa=5.0e4, tau=5.0)
    assert decision_solid.state == "solid"
    assert decision_solid.f_vap == 0.0
    decision_vapor = evaluator.evaluate(temperature_K=2100.0, pressure_Pa=1.0e3, tau=0.01)
    assert decision_vapor.state == "vapor"
    assert math.isclose(decision_vapor.f_vap, 1.0)


def test_phase_map_entrypoint_and_hydro_timescale() -> None:
    cfg = PhaseConfig(
        enabled=True,
        source="map",
        map=PhaseMapConfig(entrypoint="tests.phase_map_stub:lookup_phase_state"),
    )
    evaluator = phase.PhaseEvaluator(cfg)
    decision = evaluator.evaluate(temperature_K=1850.0, pressure_Pa=0.0, tau=0.1)
    assert decision.state == "vapor"
    assert decision.used_map

    hydro_cfg = HydroEscapeConfig(enable=True, strength=1.0e-5, temp_power=2.0, T_ref_K=2000.0)
    timescale = phase.hydro_escape_timescale(hydro_cfg, temperature_K=2000.0, f_vap=decision.f_vap)
    assert timescale is not None
    assert math.isclose(timescale, 1.0 / (hydro_cfg.strength * decision.f_vap))
    assert phase.hydro_escape_timescale(hydro_cfg, temperature_K=1500.0, f_vap=0.0) is None


def test_phase_boundary_values_are_unique() -> None:
    cfg = PhaseConfig(
        enabled=True,
        source="threshold",
        thresholds=PhaseThresholds(T_condense_K=1400.0, T_vaporize_K=1700.0, tau_ref=2.0),
    )
    evaluator = phase.PhaseEvaluator(cfg)
    solid = evaluator.evaluate(temperature_K=1400.0, pressure_Pa=5.0e4, tau=10.0)
    assert solid.state == "solid"
    assert solid.f_vap == 0.0
    vapor = evaluator.evaluate(temperature_K=1700.0, pressure_Pa=0.0, tau=0.0)
    assert vapor.state == "vapor"
    assert vapor.f_vap == 1.0
    mid = evaluator.evaluate(temperature_K=1520.0, pressure_Pa=-1.0, tau=-5.0)
    assert 0.0 < mid.f_vap < 0.5
    assert mid.payload["tau_clamped"] == 0.0
    boundary = evaluator.evaluate(temperature_K=1550.0, pressure_Pa=0.0, tau=0.0)
    assert boundary.state == "vapor"
    assert boundary.f_vap == 0.5


def test_phase_map_fraction_clamped_to_physical_range() -> None:
    cfg = PhaseConfig(
        enabled=True,
        source="map",
        map=PhaseMapConfig(entrypoint="tests.phase_map_stub:lookup_unphysical_fraction"),
    )
    evaluator = phase.PhaseEvaluator(cfg)
    decision = evaluator.evaluate(temperature_K=2000.0)
    assert decision.state == "vapor"
    assert decision.f_vap == pytest.approx(1.0)


def test_radiation_source_accepts_only_mars_or_off() -> None:
    rad = schema.Radiation(source="off")
    assert rad.source == "off"
    rad_none = schema.Radiation(source="none")
    assert rad_none.source == "off"
    with pytest.raises(ValueError):
        schema.Radiation(source="sun")
