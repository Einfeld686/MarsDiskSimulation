"""Lightweight terminal progress reporting."""

from __future__ import annotations

import math
import sys
import time

# Keep a local constant to avoid depending on the orchestrator module.
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0
ETA_EWMA_ALPHA = 0.1
ETA_MIN_SAMPLES = 3


class ProgressReporter:
    """Lightweight terminal progress bar with ETA feedback."""

    def __init__(
        self,
        total_steps: int,
        total_time_s: float,
        *,
        refresh_seconds: float = 1.0,
        enabled: bool = False,
        memory_hint: str | None = None,
        memory_header: str | None = None,
    ) -> None:
        self.enabled = bool(enabled and total_steps > 0)
        self.total_steps = max(int(total_steps), 1)
        self.total_time_s = max(float(total_time_s), 0.0)
        self.refresh_seconds = max(float(refresh_seconds), 0.1)
        self.start = time.monotonic()
        self.last = self.start
        self._finished = False
        self.memory_hint = memory_hint
        self.memory_header = memory_header
        self._header_emitted = False
        self._isatty = sys.stdout.isatty()
        self._last_percent_int: int = -1
        self._eta_ewma_s: float | None = None
        self._eta_samples: int = 0
        self._last_step_wall: float | None = None
        self._last_step_no: int | None = None

    def emit_header(self) -> None:
        """Print a one-line header (e.g., memory estimate) before the bar."""

        if not self.enabled or self._header_emitted:
            return
        if self.memory_header:
            sys.stdout.write(f"{self.memory_header}\n")
            sys.stdout.flush()
        self._header_emitted = True

    def update(self, step_no: int, sim_time_s: float, *, force: bool = False) -> None:
        """Render the progress bar when the percent changes by 0.1% or forced."""

        if not self.enabled or self._finished:
            return
        now = time.monotonic()
        self._update_eta(step_no, now)
        is_last = (step_no + 1) >= self.total_steps
        frac = min(max((step_no + 1) / self.total_steps, 0.0), 1.0)
        percent_tenth = int(frac * 1000)
        if not force and not is_last and percent_tenth == self._last_percent_int:
            return
        self._last_percent_int = percent_tenth
        self.last = now
        bar_width = 28
        filled = int(bar_width * frac)
        bar = "#" * filled + "-" * (bar_width - filled)
        sim_years = sim_time_s / SECONDS_PER_YEAR if math.isfinite(sim_time_s) else float("nan")
        remaining_s = float("nan")
        if math.isfinite(self.total_time_s) and math.isfinite(sim_time_s):
            remaining_s = max(self.total_time_s - sim_time_s, 0.0)
        remaining_years = remaining_s / SECONDS_PER_YEAR if math.isfinite(remaining_s) else float("nan")
        rem_text = f"rem~{remaining_years:.3g} yr" if math.isfinite(remaining_years) else "rem~?"
        remaining_steps = max(self.total_steps - (step_no + 1), 0)
        eta_seconds = float("nan")
        if (
            self._eta_ewma_s is not None
            and math.isfinite(self._eta_ewma_s)
            and self._eta_samples >= ETA_MIN_SAMPLES
        ):
            eta_seconds = self._eta_ewma_s * remaining_steps

        def _format_eta(seconds: float) -> str:
            if not math.isfinite(seconds) or seconds < 0.0:
                return "ETA ?"
            if seconds >= 3600.0:
                return f"ETA {seconds/3600.0:.1f}h"
            if seconds >= 60.0:
                return f"ETA {seconds/60.0:.1f}m"
            return f"ETA {seconds:.0f}s"

        eta_text = _format_eta(eta_seconds)
        memory_text = f" mem~{self.memory_hint}" if self.memory_hint else ""
        line = (
            f"[{bar}] {frac * 100:5.1f}% step {step_no + 1}/{self.total_steps} "
            f"t={sim_years:.3g} yr {rem_text} {eta_text}{memory_text}"
        )
        if self._isatty:
            sys.stdout.write(f"\r\033[2K{line}")
            if is_last:
                sys.stdout.write("\n")
        else:
            sys.stdout.write(f"{line}\n")
        if is_last:
            self._finished = True
        sys.stdout.flush()

    def finish(self, step_no: int, sim_time_s: float) -> None:
        """Force a final render to end the line cleanly."""

        if not self.enabled:
            return
        self.update(step_no, sim_time_s, force=True)

    def _print(self, message: str) -> None:
        """Lightweight compatibility shim for legacy run.py logging."""

        sys.stdout.write(f"{message}\n")
        sys.stdout.flush()

    def snapshot_state(self) -> dict[str, float | int | None] | None:
        """Return a serialisable snapshot of ETA state for checkpoints."""

        if not self.enabled:
            return None
        return {
            "eta_ewma_s": float(self._eta_ewma_s) if self._eta_ewma_s is not None else None,
            "eta_samples": int(self._eta_samples),
        }

    def restore_state(self, state: dict[str, float | int | None] | None) -> None:
        """Restore ETA state from a checkpoint payload."""

        if not state:
            return
        ewma_raw = state.get("eta_ewma_s")
        samples_raw = state.get("eta_samples")
        if ewma_raw is not None:
            ewma_val = float(ewma_raw)
            if math.isfinite(ewma_val) and ewma_val > 0.0:
                self._eta_ewma_s = ewma_val
        if samples_raw is not None:
            try:
                samples_val = int(samples_raw)
            except (TypeError, ValueError):
                samples_val = 0
            self._eta_samples = max(samples_val, 0)

    def _update_eta(self, step_no: int, now: float) -> None:
        """Update the ETA EWMA using the latest step wall time."""

        if self._last_step_wall is not None and self._last_step_no is not None:
            step_delta = step_no - self._last_step_no
            if step_delta > 0:
                step_seconds = (now - self._last_step_wall) / step_delta
                if math.isfinite(step_seconds) and step_seconds > 0.0:
                    if self._eta_ewma_s is None:
                        self._eta_ewma_s = step_seconds
                    else:
                        self._eta_ewma_s = (
                            ETA_EWMA_ALPHA * step_seconds + (1.0 - ETA_EWMA_ALPHA) * self._eta_ewma_s
                        )
                    self._eta_samples += 1
        self._last_step_wall = now
        self._last_step_no = step_no
