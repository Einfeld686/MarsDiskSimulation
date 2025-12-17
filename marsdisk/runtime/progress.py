"""Lightweight terminal progress reporting."""

from __future__ import annotations

import math
import sys
import time

# Keep a local constant to avoid depending on the orchestrator module.
SECONDS_PER_YEAR = 365.25 * 24 * 3600.0


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

    def emit_header(self) -> None:
        """Print a one-line header (e.g., memory estimate) before the bar."""

        if not self.enabled or self._header_emitted:
            return
        if self.memory_header:
            sys.stdout.write(f"{self.memory_header}\n")
            sys.stdout.flush()
        self._header_emitted = True

    def update(self, step_no: int, sim_time_s: float, *, force: bool = False) -> None:
        """Render the progress bar if enabled and refresh interval elapsed."""

        if not self.enabled or self._finished:
            return
        now = time.monotonic()
        is_last = (step_no + 1) >= self.total_steps
        if not force and not is_last and (now - self.last) < self.refresh_seconds:
            return
        self.last = now
        frac = min(max((step_no + 1) / self.total_steps, 0.0), 1.0)
        elapsed = now - self.start
        bar_width = 28
        filled = int(bar_width * frac)
        bar = "#" * filled + "-" * (bar_width - filled)
        sim_years = sim_time_s / SECONDS_PER_YEAR if math.isfinite(sim_time_s) else float("nan")
        remaining_s = float("nan")
        if math.isfinite(self.total_time_s) and math.isfinite(sim_time_s):
            remaining_s = max(self.total_time_s - sim_time_s, 0.0)
        remaining_years = remaining_s / SECONDS_PER_YEAR if math.isfinite(remaining_s) else float("nan")
        rem_text = f"rem~{remaining_years:.3g} yr" if math.isfinite(remaining_years) else "rem~?"
        eta_seconds = (elapsed / frac - elapsed) if frac > 0.0 else float("nan")

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
            # Update every 0.1% (tenths of percent)
            percent_tenth = int(frac * 1000)
            if percent_tenth == self._last_percent_int and not is_last:
                return
            self._last_percent_int = percent_tenth
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
