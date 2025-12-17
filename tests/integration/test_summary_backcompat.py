import json
from pathlib import Path

import pytest

from scripts import sweep_heatmaps


def _write_summary(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_parse_summary_backwards_compatibility(tmp_path: Path) -> None:
    old_summary = {
        "case_status": "blowout",
        "beta_at_smin": 0.4,
    }
    new_summary = {
        "case_status": "ok",
        "beta_at_smin_config": 0.4,
        "beta_at_smin_effective": 0.2,
        "beta_at_smin": 0.4,
        "M_loss": 1.0e-8,
        "M_loss_from_sinks": 2.0e-9,
        "M_loss_from_sublimation": 1.0e-9,
        "s_blow_m": 9.5e-7,
        "s_min_effective": 9.9e-7,
        "s_min_effective[m]": 9.9e-7,
        "s_min_components": {
            "config": 1.0e-6,
            "blowout": 9.9e-7,
            "effective": 9.9e-7,
        },
        "T_M_source": "radiation.TM_K",
        "T_M_used": 2500.0,
        "T_M_used[K]": 2500.0,
    }

    old_path = tmp_path / "old_summary.json"
    new_path = tmp_path / "new_summary.json"
    _write_summary(old_path, old_summary)
    _write_summary(new_path, new_summary)

    _, _, parsed_old = sweep_heatmaps.parse_summary(old_path)
    assert isinstance(parsed_old, dict)
    assert parsed_old["beta_at_smin_config"] == pytest.approx(old_summary["beta_at_smin"])
    assert parsed_old["beta_at_smin_effective"] is None
    assert sweep_heatmaps._get_beta_for_checks(parsed_old) == pytest.approx(0.4)

    _, _, parsed_new = sweep_heatmaps.parse_summary(new_path)
    assert isinstance(parsed_new, dict)
    assert parsed_new["beta_at_smin_config"] == pytest.approx(0.4)
    assert parsed_new["beta_at_smin_effective"] == pytest.approx(0.2)
    assert parsed_new["s_min_components"]["config"] == pytest.approx(1.0e-6)
    assert "sublimation" not in parsed_new["s_min_components"]
    assert parsed_new["T_M_source"] == "radiation.TM_K"
    assert parsed_new["beta_at_smin"] == pytest.approx(0.4)
    assert parsed_new["M_loss"] == pytest.approx(1.0e-8)
    assert parsed_new["M_loss_from_sinks"] == pytest.approx(2.0e-9)
    assert parsed_new["M_loss_from_sublimation"] == pytest.approx(1.0e-9)
    assert parsed_new["T_M_used"] == pytest.approx(2500.0)
    assert parsed_new["T_M_used[K]"] == pytest.approx(2500.0)
    assert parsed_new["s_min_effective"] == pytest.approx(9.9e-7)
    assert parsed_new["s_min_effective[m]"] == pytest.approx(9.9e-7)
    assert sweep_heatmaps._get_beta_for_checks(parsed_new) == pytest.approx(0.4)
