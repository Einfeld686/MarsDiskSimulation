"""Runtime auto-tuning helpers (stdlib-first, psutil optional)."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import os
import platform
import subprocess
from typing import Any, Dict, Optional

try:  # optional dependency
    import psutil  # type: ignore
    _PSUTIL_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False


_PROFILE_CHOICES = ("auto", "light", "balanced", "throughput")


@dataclass
class MachineState:
    """Lightweight snapshot of runtime machine state."""

    cpu_logical: int
    cpu_physical: Optional[int]
    cpu_perf_cores: Optional[int]
    cpu_eff_cores: Optional[int]
    cpu_perf_logical: Optional[int]
    cpu_eff_logical: Optional[int]
    load_avg_1m: Optional[float]
    mem_total_gb: Optional[float]
    mem_available_gb: Optional[float]
    platform_system: str
    platform_machine: str
    psutil_available: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AutoTuneDecision:
    """Auto-tune result for thread settings."""

    profile_requested: str
    profile_resolved: str
    numba_threads: int
    numba_thread_source: str
    suggested_sweep_jobs: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _safe_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _sysctl_int(name: str) -> Optional[int]:
    try:
        out = subprocess.check_output(["sysctl", "-n", name], text=True).strip()
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    try:
        parsed = int(out)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _mac_core_score(state: MachineState) -> Optional[float]:
    perf = state.cpu_perf_cores or state.cpu_perf_logical
    eff = state.cpu_eff_cores or state.cpu_eff_logical
    if perf is None and eff is None:
        return None
    perf = perf or 0
    eff = eff or 0
    return float(perf) + 0.5 * float(eff)


def _thread_core_budget(state: MachineState) -> int:
    if state.platform_system == "Darwin":
        perf = state.cpu_perf_cores or state.cpu_perf_logical
        if perf is not None and perf > 0:
            return perf
    return state.cpu_physical or state.cpu_logical


def _job_core_budget(state: MachineState, cores: int) -> int:
    if state.platform_system == "Darwin":
        score = _mac_core_score(state)
        if score is not None:
            return max(1, int(round(score)))
    return cores


def detect_machine_state() -> MachineState:
    """Collect a minimal machine state snapshot using stdlib first."""

    cpu_logical = _safe_int(os.cpu_count(), 1)
    cpu_physical = None
    mem_total_gb = None
    mem_available_gb = None
    cpu_perf_cores = None
    cpu_eff_cores = None
    cpu_perf_logical = None
    cpu_eff_logical = None
    if _PSUTIL_AVAILABLE and psutil is not None:
        try:
            cpu_physical = psutil.cpu_count(logical=False)
        except Exception:
            cpu_physical = None
        try:
            vm = psutil.virtual_memory()
            mem_total_gb = float(vm.total) / (1024.0**3)
            mem_available_gb = float(vm.available) / (1024.0**3)
        except Exception:
            mem_total_gb = None
            mem_available_gb = None

    load_avg_1m = None
    try:
        load_avg_1m = float(os.getloadavg()[0])
    except (AttributeError, OSError):
        load_avg_1m = None

    platform_system = platform.system()
    if platform_system == "Darwin":
        cpu_perf_cores = _sysctl_int("hw.perflevel0.physicalcpu")
        cpu_eff_cores = _sysctl_int("hw.perflevel1.physicalcpu")
        cpu_perf_logical = _sysctl_int("hw.perflevel0.logicalcpu")
        cpu_eff_logical = _sysctl_int("hw.perflevel1.logicalcpu")

    return MachineState(
        cpu_logical=cpu_logical,
        cpu_physical=cpu_physical,
        cpu_perf_cores=cpu_perf_cores,
        cpu_eff_cores=cpu_eff_cores,
        cpu_perf_logical=cpu_perf_logical,
        cpu_eff_logical=cpu_eff_logical,
        load_avg_1m=load_avg_1m,
        mem_total_gb=mem_total_gb,
        mem_available_gb=mem_available_gb,
        platform_system=platform_system,
        platform_machine=platform.machine(),
        psutil_available=_PSUTIL_AVAILABLE,
    )


def _resolve_profile(state: MachineState, requested: str) -> str:
    if requested not in _PROFILE_CHOICES:
        requested = "auto"
    if requested != "auto":
        return requested

    # Auto profile selection (conservative on macOS, light under load).
    if state.platform_system == "Darwin":
        cores = state.cpu_physical or state.cpu_logical
        if state.load_avg_1m is not None and state.cpu_logical > 0:
            if state.load_avg_1m / float(state.cpu_logical) >= 0.5:
                return "light"
        if state.mem_available_gb is not None and state.mem_available_gb < 8.0:
            return "light"
        score = _mac_core_score(state)
        if score is not None:
            return "balanced" if score >= 6.0 else "light"
        return "balanced" if cores >= 10 else "light"
    if state.load_avg_1m is not None and state.cpu_logical > 0:
        if state.load_avg_1m / float(state.cpu_logical) >= 0.5:
            return "light"
    if state.mem_available_gb is not None and state.mem_available_gb < 8.0:
        return "light"

    cores = state.cpu_physical or state.cpu_logical
    if state.platform_system == "Windows":
        logical = state.cpu_logical
        if cores >= 24 or logical >= 32:
            return "throughput"
        if cores >= 12 or logical >= 16:
            return "balanced"
        return "light"
    if cores >= 24:
        return "throughput"
    if cores >= 12:
        return "balanced"
    return "light"


def _profile_threads(profile: str, cores: int, platform_system: str) -> int:
    if profile == "light":
        return 1
    if profile == "balanced":
        if platform_system == "Windows":
            return 2 if cores >= 8 else 1
        return 2 if cores >= 12 else 1
    if profile == "throughput":
        if platform_system == "Windows":
            if cores >= 48:
                return 12
            if cores >= 32:
                return 8
            if cores >= 24:
                return 6
            if cores >= 16:
                return 4
            return 2
        return min(4, max(2, cores // 8))
    return 1


def _suggest_sweep_jobs(cores: int, numba_threads: int) -> int:
    if numba_threads <= 0:
        return max(1, cores)
    return max(1, cores // numba_threads)


def _apply_numba_threads(numba_threads: int) -> Dict[str, Any]:
    """Attempt to apply Numba thread count at runtime."""

    result: Dict[str, Any] = {"requested": numba_threads, "applied": None, "status": "skipped"}
    try:
        import numba  # type: ignore

        numba.set_num_threads(int(numba_threads))
        result["applied"] = int(numba.get_num_threads())
        result["status"] = "ok"
    except Exception as exc:  # pragma: no cover - optional dependency
        result["status"] = f"error: {exc!s}"
    return result


def apply_auto_tune(
    *,
    profile: str = "auto",
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Apply auto-tuning decisions and return a structured report."""

    state = detect_machine_state()
    resolved_profile = _resolve_profile(state, profile)
    cores = state.cpu_physical or state.cpu_logical
    thread_cores = _thread_core_budget(state)
    numba_threads = _profile_threads(resolved_profile, thread_cores, state.platform_system)

    env = env if env is not None else os.environ
    env_numba = env.get("NUMBA_NUM_THREADS")
    if env_numba is not None:
        numba_threads = _safe_int(env_numba, numba_threads)
        numba_source = "env"
    else:
        env["NUMBA_NUM_THREADS"] = str(numba_threads)
        numba_source = "auto"

    decision = AutoTuneDecision(
        profile_requested=profile,
        profile_resolved=resolved_profile,
        numba_threads=numba_threads,
        numba_thread_source=numba_source,
        suggested_sweep_jobs=_suggest_sweep_jobs(_job_core_budget(state, cores), numba_threads),
    )

    numba_apply = _apply_numba_threads(numba_threads)
    return {
        "enabled": True,
        "machine": state.to_dict(),
        "decision": decision.to_dict(),
        "numba": numba_apply,
    }
