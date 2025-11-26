# Provenance Report

- **Equation coverage**: 7 / 38 headings in `analysis/equations.md` now carry confirmed tags (≈18.4%). Key anchors include (E.006) for the Strubbe–Chiang surface lifetime and (E.042)/(E.043) for the Hyodo et al. cooling/greybody laws. [@StrubbeChiang2006_ApJ648_652; @Hyodo2018_ApJ860_150]
- **Code mappings**: 23 anchors in `analysis/source_map.json` link the registry keys across radiation, surface, sublimation, siO₂ cooling, and the gas-poor guidance in `analysis/overview.md` / `analysis/run-recipes.md`. All entries reference normalized keys from `analysis/references.registry.json`.
- **Unknown packets**: 4 open slugs remain in `analysis/UNKNOWN_REF_REQUESTS.{jsonl,md}` — `tmars_cooling_solution_v1` (cooling-layer properties), `tp_radiative_equilibrium_v1` (⟨Q_abs⟩ tables), `siO2_thresholds_v1` (glass/liquidus inputs), and `tl2003_surface_flow_scope_v1` (gas-rich TL2003 scope).

## Coverage Summary

| Category | Count |
| --- | --- |
| Total equations (E.xxx) | 38 |
| Equations with `[@Key]` | 7 |
| Equations with `TODO(REF:...)` | 31 |
| Code anchors in `source_map.json` | 23 |
| Registry entries | 11 |

Known tags presently include `Hyodo2018_ApJ860_150`, `StrubbeChiang2006_ApJ648_652`, `Pignatale2018_ApJ853_118`, `Ronnet2016_ApJ828_109`, `CridaCharnoz2012_Science338_1196`, `CanupSalmon2018_SciAdv4_eaar6887`, and `Kuramoto2024`. These anchor the thermal history, β/blow-out relations, sublimation chemistry, condensation sinks, viscous spreading regimes, disk-mass/tidal constraints, and the MMX-era review baseline.

## Top Unknown Items

1. **`tmars_cooling_solution_v1`** — Needs primary sources for the chosen $D,\rho,c_p$ representing the radiative cooling layer in (E.042).
2. **`tp_radiative_equilibrium_v1`** — Requires Planck-mean $⟨Q_{\mathrm{abs}}⟩(s,T)$ tables for SiO₂ grains instead of the constant placeholder.
3. **`siO2_thresholds_v1`** — Requests petrology/lab references for the $1475/1986$ K glass/liquidus temperatures under low-pressure conditions.
4. **`tl2003_surface_flow_scope_v1`** — Documents why the TL2003 gas-rich surface ODE remains opt-in and disabled by default for gas-poor disks.

## Known Reference Notes

- `Takeuchi & Lin (2003)` (`TakeuchiLin2003_ApJ593_524`) stays registry-only; it is linked via TODO packets but not enforced in code because gas-poor runs keep `ALLOW_TL2003=false`.
- Wyatt (2008) remains a contextual review, while Strubbe & Chiang (2006) provides the normative gas-poor collisional and β scalings implemented in `marsdisk/physics/surface.py` and `marsdisk/physics/radiation.py`.
- `Kuramoto (2024)` (`Kuramoto2024`) is tracked as the MMX/mission-focused cross-check to ensure the overall impact narrative remains consistent with current review articles.
