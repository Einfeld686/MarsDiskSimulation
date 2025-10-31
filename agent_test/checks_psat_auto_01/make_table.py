"""Generate a deterministic SiO saturation pressure table using the project
Clausius–Clapeyron backend.

The table spans 1200–5000 K in 50 K increments and records ``log10 P`` in Pascals.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

from marsdisk.physics.sublimation import SublimationParams, p_sat


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    out_path = base_dir / "inputs" / "psat_sio_table.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    params = SublimationParams(
        mode="hkl",
        psat_model="clausius",
        alpha_evap=0.007,
        mu=0.0440849,
        A=13.613,
        B=17850.0,
        P_gas=0.0,
    )

    grid = np.arange(1200.0, 5000.0 + 1e-6, 50.0)
    rows = []
    for T in grid:
        P_sat = p_sat(float(T), params)
        if not math.isfinite(P_sat) or P_sat <= 0.0:
            raise RuntimeError(f"Non-positive saturation pressure at T={T} K: {P_sat}")
        log10P = math.log10(P_sat)
        rows.append(
            (
                f"{T:.0f}",
                f"{log10P:.8f}",
                f"{T:.0f}",
                f"{log10P:.8f}",
            )
        )

    with out_path.open("w", newline="", encoding="ascii") as f:
        writer = csv.writer(f)
        writer.writerow(["T_K", "log10P_Pa", "T", "log10P"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} samples to {out_path}")


if __name__ == "__main__":
    main()
