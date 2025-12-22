# Mars Dust Disk Simulation Summary (run_temp_supply_sweep.sh)

**Purpose**: This document provides a self-contained summary for sharing with external AI tools (ChatGPT, Claude, etc.) to research visualization best practices.

**Target Audience**: This summary is intended to be pasted into an LLM prompt to provide context for generating visualization code (Python/Matplotlib) or suggesting design improvements.

---

## 1. Research Context

### What is this simulation?
A numerical simulation of a **dust disk around Mars**, formed after a giant impact. The disk is believed to be the source material for Mars's moons **Phobos and Deimos**.

### Scientific Goal
Quantify **mass loss** from the disk as Mars cools from high temperature (3000-5000 K) down to ~2000 K, via:
1. **Radiation pressure blow-out**: Small particles (< μm) ejected by thermal radiation
2. **Sublimation**: Evaporation at high temperatures
3. **Collision cascade**: Large particles fragmenting into smaller ones (Smoluchowski equation)

### Key Physics
- **0D model** (radially averaged at ~2.4 Mars radii, Roche limit)
- **Gas-poor assumption**: No gas drag, radiation pressure dominates
- **τ~1 maintenance**: Optical depth feedback keeps disk optically thick
- **Slab cooling**: T(t) ∝ t^(-1/3) Stefan-Boltzmann cooling

---

## 2. Parameter Sweep Configuration

**Script**: `scripts/research/run_temp_supply_sweep.sh`

### Swept Parameters (27 combinations)
| Parameter | Symbol | Values | Physical Meaning |
|-----------|--------|--------|------------------|
| Initial Mars Temperature | T_M | **5000, 4000, 3000** K | Drives radiation pressure & sublimation |
| Mixing Efficiency | μ (epsilon_mix) | **1.0, 0.5, 0.1** | Fraction of supply reaching surface |
| Shielding Coefficient | Φ | **0.20, 0.37, 0.60** | Self-shielding in optically thick disk |

### Fixed Parameters
- **Stop condition**: Mars temperature reaches 2000 K
- **Cooling model**: Slab (T^{-3} analytic)
- **Transport mode**: `deep_mixing` (buffered supply via deep reservoir)
- **τ feedback**: Enabled (target τ = 0.9, gain = 1.2)
- **Base supply rate**: 5×10⁻³ kg/m²/s (before mixing)
- **Initial τ scaling**: Enabled (start at τ = 1.0)

---

## 3. Key Physical Quantities

| Symbol | Name | Description | Unit |
|--------|------|-------------|------|
| `τ` (tau) | Optical depth | Disk opacity (τ~1 = optically thick boundary) | dimensionless |
| `β` (beta) | Radiation pressure ratio | Radiation/gravity (β > 0.5 → particle escapes) | dimensionless |
| `a_blow` | Blow-out size | Size threshold for escape (~μm scale) | m |
| `Σ_surf` | Surface density | Mass per unit area in surface layer | kg/m² |
| `Σ_τ=1` | τ=1 cap | Maximum surface density before clipping | kg/m² |
| `T_M` | Mars surface temperature | Time-varying (cooling from initial T) | K |
| `Ṁ_out` | Mass loss rate | Instantaneous mass outflow rate | M_Mars/s |
| `M_loss` | Cumulative mass loss | Total mass lost over simulation | M_Mars |
| `t_coll` | Collision time | 1/(Ω τ), Wyatt scaling | s |
| `t_blow` | Blow-out time | χ/Ω, ~1 orbital period | s |

---

## 4. Output Data Structure

### Directory Structure
```
temp_supply_sweep/<timestamp>__<git_sha>__seed<N>/
├── T5000_mu1p0_phi20/
│   ├── series/run.parquet      # Time series data
│   ├── summary.json            # Run summary
│   ├── checks/                 # Mass budget logs
│   └── plots/
│       ├── overview.png        # 3-panel summary
│       ├── supply_surface.png  # 5-panel supply diagnostics
│       └── optical_depth.png   # τ evolution
├── T5000_mu1p0_phi37/
│   └── ...
└── ... (27 directories total)
```

### Time Series Columns (`run.parquet`)

**Core quantities:**
- `time`, `dt` — Time and timestep [s]
- `tau`, `tau_los_mars` — Optical depths
- `M_out_dot`, `M_sink_dot` — Mass loss rates [M_Mars/s]
- `M_loss_cum`, `mass_lost_by_blowout`, `mass_lost_by_sinks` — Cumulative losses [M_Mars]
- `s_min`, `a_blow` — Size limits [m]

**Supply diagnostics (key for this sweep):**
- `supply_rate_nominal` — Raw rate × mixing efficiency
- `supply_rate_scaled` — After temperature/feedback/reservoir scaling
- `supply_rate_applied` — After headroom clipping
- `prod_rate_applied_to_surf` — Actually injected to surface
- `prod_rate_diverted_to_deep` — Diverted to deep reservoir
- `deep_to_surf_flux` — Transfer from deep to surface
- `supply_feedback_scale` — τ-feedback multiplier
- `supply_clip_factor` — Headroom clipping factor

**Surface state:**
- `Sigma_surf`, `sigma_surf` — Surface density [kg/m²]
- `Sigma_tau1`, `sigma_tau1` — τ=1 cap [kg/m²]
- `headroom` — Available capacity (Σ_τ=1 - Σ_surf)
- `sigma_deep` — Deep reservoir density

**Timescales:**
- `t_coll` — Collision time [s]
- `t_blow_s` — Blow-out time [s]
- `dt_over_t_blow` — Timestep ratio

---

## 5. Visualization Questions for ChatGPT

**Specific to this simulation:**

1. **"For a parameter sweep with 27 runs (3 temperatures × 3 supply rates × 3 shielding coefficients), what is the best way to visualize the sensitivity of mass loss M_loss to each parameter? Examples from debris disk or protoplanetary disk papers?"**

2. **"In simulations of collision cascades (Smoluchowski equation), how do researchers visualize the time evolution of particle size distribution (PSD)? I have log-spaced size bins from 10^-6 to 3 m."**

3. **"For optical depth τ that is maintained near τ~1 via feedback control, what visualization techniques are used in astrophysical disk simulations to show τ stability and supply clipping events?"**

4. **"What are standard visualization methods for comparing runs with different initial temperatures (3000-5000 K) in cooling disk simulations? Time axis normalization, overlays, or separate panels?"**

5. **"For supply-limited vs loss-limited regimes in debris disks, how do papers visualize the transition between these regimes? I have supply_rate_applied and outflux_surface time series."**

6. **"How do researchers visualize the 'blow-out' size a_blow and its relationship to the minimum particle size s_min over time as the disk cools?"**

7. **"For a sweep summary visualization, what are best practices for 3×3×3 heatmaps showing M_loss(T, μ, Φ)? Slices, 3D plots, or corner plots?"**

---

## 6. Visualization Challenges (Pain Points)

Current visualization struggles that need AI advice:

1.  **Metric Overload**: With 27 runs and ~50 columns per timestep, it is hard to spot "interesting" failures (e.g., unexpectedly high mass loss or reservoir depletion).
2.  **Clip Diagnosis**: The `headroom` clipping mechanism (keeping $\Sigma \le \Sigma_{\tau=1}$) is critical but invisible in standard M_loss plots. Need a way to visualize *how much* supply was rejected.
3.  **Physical Intuition**: The model is 0D (radially averaged). Plots are just lines. We need ways to make the results feel more "physical" (e.g., relating $\Sigma$ to actual optical thickness or brightness).
4.  **Deep Reservoir**: The buffering effect of `deep_mixing` is complex. We need to visualize the flow: `External -> Deep Reservoir -> Surface -> Blowout`.

---

## 7. Data Samples (for Context)

### `summary.json` Example
```json
{
  "M_loss": 1.2e-4,
  "M_loss_tau_clip_spill": 0.0,
  "T_M_initial": 4000.0,
  "T_M_final": 2000.0,
  "analysis_window_years": 2.0,
  "supply_clipping": {
    "clip_time_fraction": 0.15,
    "blocked_fraction": 0.05
  },
  "supply_feedback_scale_median": 0.85,
  "process_overview": {
    "supply_transport_mode": "deep_mixing",
    "supply_headroom_policy": "clip"
  }
}
```

### `run.parquet` Schema (dtypes)
```python
time: float64
M_out_dot: float64          # Mass loss rate
Sigma_surf: float64         # Current surface density
Sigma_tau1: float64         # Max surface density capacity
supply_rate_applied: float64 # Rate actually entering surface
headroom: float64           # Remaining capacity
```

---

## 8. Related Literature Keywords

**English**: debris disk, particle size distribution, collision cascade, radiation pressure blow-out, optical depth, mass loss rate, parameter sweep, dust dynamics, Smoluchowski equation, protoplanetary disk, circumplanetary disk, Mars moon formation, sensitivity analysis, heatmap visualization

**日本語**: デブリディスク, 粒径分布, 衝突カスケード, 放射圧ブローアウト, 光学深度, 質量損失率, パラメータスイープ, 火星衛星形成, 感度解析
