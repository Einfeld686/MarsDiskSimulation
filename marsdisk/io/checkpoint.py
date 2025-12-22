from __future__ import annotations

import base64
import json
import pickle
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

from ..physics import supply


CheckpointFormat = Union[str, None]


def _b64_pack(payload: Any) -> str:
    return base64.b64encode(pickle.dumps(payload)).decode("ascii")


def _b64_unpack(payload: str) -> Any:
    return pickle.loads(base64.b64decode(payload.encode("ascii")))


@dataclass
class CheckpointState:
    """Minimal state bundle required to resume a 0D run."""

    version: int
    step_no: int
    time_s: float
    dt_s: float
    sigma_surf: float
    sigma_deep: float
    s_min_effective: float
    s_min_floor_dynamic: float
    s_min_evolved_value: float
    M_loss_cum: float
    M_sink_cum: float
    M_spill_cum: float
    M_sublimation_cum: float
    M_hydro_cum: float
    psd_state: Dict[str, Any]
    supply_state: Dict[str, Any]
    rng_state_numpy: Any
    rng_state_generator: Any
    rng_state_python: Any
    progress_state: Optional[Dict[str, Any]] = None

    def supply_state_as_runtime(self) -> Optional[supply.SupplyRuntimeState]:
        if not self.supply_state:
            return None
        state = supply.SupplyRuntimeState()
        for key, value in self.supply_state.items():
            if key == "temperature_table":
                continue
            if hasattr(state, key):
                setattr(state, key, value)
        return state


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def save_checkpoint(path: Path, state: CheckpointState, fmt: CheckpointFormat = "pickle") -> Path:
    """Serialise a checkpoint to disk."""

    fmt_normalized = "pickle" if fmt in (None, "") else str(fmt).lower()
    _ensure_parent(path)
    if fmt_normalized == "pickle":
        with path.open("wb") as fh:
            pickle.dump(state, fh)
        return path

    if fmt_normalized != "json":
        raise ValueError(f"Unsupported checkpoint format: {fmt}")

    payload = asdict(state)
    payload["psd_state"] = _b64_pack(state.psd_state)
    payload["rng_state_numpy"] = _b64_pack(state.rng_state_numpy)
    payload["rng_state_generator"] = _b64_pack(state.rng_state_generator)
    payload["rng_state_python"] = _b64_pack(state.rng_state_python)
    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return path


def load_checkpoint(path: Path, fmt: CheckpointFormat = None) -> CheckpointState:
    """Load a checkpoint from disk."""

    fmt_normalized = fmt
    if fmt_normalized is None:
        suffix = path.suffix.lower()
        if suffix in {".pkl", ".pickle"}:
            fmt_normalized = "pickle"
        elif suffix == ".json":
            fmt_normalized = "json"
        else:
            fmt_normalized = "pickle"
    fmt_normalized = str(fmt_normalized).lower()

    if fmt_normalized == "pickle":
        with path.open("rb") as fh:
            return pickle.load(fh)

    if fmt_normalized != "json":
        raise ValueError(f"Unsupported checkpoint format: {fmt_normalized}")

    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    payload["psd_state"] = _b64_unpack(payload["psd_state"])
    payload["rng_state_numpy"] = _b64_unpack(payload["rng_state_numpy"])
    payload["rng_state_generator"] = _b64_unpack(payload["rng_state_generator"])
    payload["rng_state_python"] = _b64_unpack(payload["rng_state_python"])
    return CheckpointState(**payload)


def find_latest_checkpoint(dir_path: Path) -> Optional[Path]:
    """Return the latest checkpoint path in a directory if any."""

    if not dir_path.exists() or not dir_path.is_dir():
        return None
    candidates = sorted(dir_path.glob("ckpt_step_*"))
    if not candidates:
        return None
    return candidates[-1]


def prune_checkpoints(dir_path: Path, keep_last_n: int) -> None:
    """Remove older checkpoints, keeping only the most recent N."""

    if keep_last_n <= 0:
        return
    if not dir_path.exists() or not dir_path.is_dir():
        return
    candidates = sorted(dir_path.glob("ckpt_step_*"))
    if len(candidates) <= keep_last_n:
        return
    for old_path in candidates[:-keep_last_n]:
        try:
            old_path.unlink()
        except OSError:
            pass
