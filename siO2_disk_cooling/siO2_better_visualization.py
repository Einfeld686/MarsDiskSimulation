"""Generate higher-visibility plots for the SiO2 cooling toy model.

This script is intentionally self-contained so you can copy/paste it into your
repo or adapt it to your own compute_arrival_times outputs.

Assumptions (chosen to reproduce the *slab, T0=4000 K* example map):
- Mars slab cooling: T_Mars(t) = (T0^{-3} + k t)^{-1/3}
  where k is calibrated so 4000 K -> 1000 K takes ~55 years.
- Particle temperature: T_par(t,r) = T_Mars(t) / sqrt(2 r)
  with r in units of R_Mars.
- Thresholds: T_liquidus = 1986 K, T_g = 1475 K.

Outputs (PNG) are written next to this script.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main() -> None:
    # --- Parameters (match the example map) ---
    T0 = 4000.0
    T_liquidus = 1986.0
    T_g = 1475.0

    # Calibrate slab cooling so that 4000 -> 1000 K takes ~55 years.
    T_stop = 1000.0
    t_stop_years = 55.0
    k = (T_stop**-3 - T0**-3) / t_stop_years  # K^{-3} per year

    # Radius grid
    r_min, r_max, n_r = 1.0, 2.4, 300
    r = np.linspace(r_min, r_max, n_r)

    # --- Helper functions ---
    def T_mars(t_years: np.ndarray) -> np.ndarray:
        return (T0**-3 + k * t_years) ** (-1.0 / 3.0)

    def arrival_time_years(rvals: np.ndarray, T_threshold: float) -> np.ndarray:
        """Time when T_par(t,r) first drops below T_threshold."""
        T_target = T_threshold * np.sqrt(2.0 * rvals)
        t = (T_target**-3 - T0**-3) / k
        t = np.where(T_target >= T0, 0.0, t)  # already below threshold at t=0
        return np.maximum(t, 0.0)

    # Arrival curves
    t_liq = arrival_time_years(r, T_liquidus)
    t_g = arrival_time_years(r, T_g)

    # Choose a zoom window that contains all transitions.
    t_max_plot = float(np.max(t_g) + 0.7)

    # --- (1) Temperature map with threshold isotherms ---
    t = np.linspace(0.0, t_max_plot, 600)
    Tpar = T_mars(t)[:, None] / np.sqrt(2.0 * r[None, :])

    fig1 = plt.figure(figsize=(10, 6), dpi=160)
    ax1 = fig1.add_subplot(111)
    mesh = ax1.pcolormesh(t, r, Tpar.T, shading="auto")
    cb = fig1.colorbar(mesh, ax=ax1)
    cb.set_label("Particle temperature [K]")

    levels = [T_g, T_liquidus]  # must be increasing
    cs = ax1.contour(t, r, Tpar.T, levels=levels, linewidths=2.0)
    ax1.clabel(cs, fmt={T_g: f"Tg = {T_g:.0f} K", T_liquidus: f"Liquidus = {T_liquidus:.0f} K"}, inline=True)

    ax1.set_title(f"SiO2 temperature map (slab, T0={int(T0)} K)")
    ax1.set_xlabel("Time since impact [years]")
    ax1.set_ylabel("r / R_Mars")
    fig1.tight_layout()

    outdir = Path(__file__).resolve().parent
    p1 = outdir / f"siO2_temperature_map_T0{int(T0):04d}K_zoom.png"
    fig1.savefig(p1)
    plt.close(fig1)

    # --- (2) Phase-boundary curves (time-radius plane) ---
    fig2 = plt.figure(figsize=(10, 6), dpi=160)
    ax2 = fig2.add_subplot(111)

    ax2.plot(t_liq, r, linewidth=2.2, label=f"T drops below liquidus ({int(T_liquidus)} K)")
    ax2.plot(t_g, r, linewidth=2.2, label=f"T drops below Tg ({int(T_g)} K)")

    ax2.text(0.15, 1.35, f"T > {int(T_liquidus)} K")
    ax2.text(2.05, 1.2, f"{int(T_g)} K < T < {int(T_liquidus)} K")
    ax2.text(3.7, 1.05, f"T < {int(T_g)} K")

    ax2.set_xlim(0.0, t_max_plot)
    ax2.set_ylim(r_min, r_max)
    ax2.grid(True, alpha=0.3)

    ax2.set_title(f"SiO2 phase boundaries (slab, T0={int(T0)} K)")
    ax2.set_xlabel("Time since impact [years]")
    ax2.set_ylabel("r / R_Mars")
    ax2.legend(loc="upper right")

    fig2.tight_layout()
    p2 = outdir / f"siO2_phase_boundaries_T0{int(T0):04d}K_zoom.png"
    fig2.savefig(p2)
    plt.close(fig2)

    # --- (3) Arrival times vs radius (1D) ---
    fig3 = plt.figure(figsize=(10, 6), dpi=160)
    ax3 = fig3.add_subplot(111)

    ax3.plot(r, t_liq, linewidth=2.2, label=f"below liquidus ({int(T_liquidus)} K)")
    ax3.plot(r, t_g, linewidth=2.2, label=f"below Tg ({int(T_g)} K)")

    ax3.set_title(f"SiO2 arrival times vs radius (slab, T0={int(T0)} K)")
    ax3.set_xlabel("r / R_Mars")
    ax3.set_ylabel("Arrival time [years]")
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc="upper right")

    fig3.tight_layout()
    p3 = outdir / f"siO2_arrival_times_vs_radius_T0{int(T0):04d}K.png"
    fig3.savefig(p3)
    plt.close(fig3)

    print("Wrote:")
    for p in (p1, p2, p3):
        print(" -", p)


if __name__ == "__main__":
    main()
