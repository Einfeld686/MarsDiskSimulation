import copy
import random
from pathlib import Path

import numpy as np

from marsdisk.io import checkpoint


def _sample_state() -> checkpoint.CheckpointState:
    rng = np.random.default_rng(123)
    return checkpoint.CheckpointState(
        version=1,
        step_no=5,
        time_s=12.0,
        dt_s=2.0,
        sigma_surf=1.23,
        sigma_deep=0.0,
        s_min_effective=1.0e-3,
        s_min_floor_dynamic=1.0e-3,
        s_min_evolved_value=1.0e-3,
        M_loss_cum=1.0e-6,
        M_sink_cum=2.0e-6,
        M_spill_cum=0.0,
        M_sublimation_cum=0.0,
        M_hydro_cum=0.0,
        psd_state={
            "sizes": np.array([1.0, 2.0]),
            "number": np.array([1.0, 1.0]),
        },
        supply_state={
            "reservoir_enabled": True,
            "reservoir_mass_remaining_kg": 1.0,
        },
        rng_state_numpy=np.random.get_state(),
        rng_state_generator=copy.deepcopy(rng.bit_generator.state),
        rng_state_python=random.getstate(),
    )


def test_checkpoint_pickle_roundtrip(tmp_path: Path) -> None:
    state = _sample_state()
    path = tmp_path / "ckpt_step_000000005.pkl"
    checkpoint.save_checkpoint(path, state, fmt="pickle")
    loaded = checkpoint.load_checkpoint(path)
    assert np.allclose(loaded.psd_state["sizes"], state.psd_state["sizes"])
    assert loaded.sigma_surf == state.sigma_surf
    assert loaded.step_no == state.step_no


def test_checkpoint_json_roundtrip(tmp_path: Path) -> None:
    state = _sample_state()
    path = tmp_path / "ckpt_step_000000005.json"
    checkpoint.save_checkpoint(path, state, fmt="json")
    loaded = checkpoint.load_checkpoint(path)
    assert np.allclose(loaded.psd_state["sizes"], state.psd_state["sizes"])
    assert loaded.time_s == state.time_s
    assert loaded.supply_state["reservoir_enabled"] is True
