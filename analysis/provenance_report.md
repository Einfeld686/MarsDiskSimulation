# Provenance Report

- **Equation coverage**: 7 / 43 headings in `analysis/equations.md` carry `[@Key]` tags (≈16.3%). The remainder are marked with `TODO(REF:...)` slugs to avoid false positives.
- **Code mappings**: 7 unique modules/functions/constants are linked in `analysis/source_map.json`. All refer to normalized keys from `analysis/references.registry.json`.
- **Unknown packets**: 1 medium-priority slug (`tl2003_surface_flow_scope_v1`) remains in `analysis/UNKNOWN_REF_REQUESTS.{jsonl,md}`; it documents why TL2003 stays opt-in under gas-rich assumptions.

## Coverage Summary

| Category | Count |
| --- | --- |
| Total equations (E.xxx) | 43 |
| Equations with `[@Key]` | 7 |
| Equations with `TODO(REF:...)` | 36 |
| Code anchors in `source_map.json` | 7 |
| Registry entries | 11 |

Known tags presently include `Hyodo2018_ApJ860_150`, `StrubbeChiang2006_ApJ648_652`, `Pignatale2018_ApJ853_118`, `Ronnet2016_ApJ828_109`, `CridaCharnoz2012_Science338_1196`, and `CanupSalmon2018_SciAdv4_eaar6887`. These anchor the thermal history, β/blow-out relations, sublimation chemistry, condensation sinks, viscous spreading regimes, and disk-mass/tidal survival constraints.

## Top Unknown Items

1. **`tl2003_surface_flow_scope_v1`** — Applicability of TL2003 gas-rich surface ODE under gas-poor defaults remains unresolved; requires literature check before enabling by default.

## Known Reference Notes

- `Takeuchi & Lin (2003)` (`TakeuchiLin2003_ApJ593_524`) is tracked in the registry but intentionally **not** linked to code because the specification forbids auto-adoption under gas-poor assumptions.
- Gas-poor enforcement pulls on `CanupSalmon2018_SciAdv4_eaar6887` and `Hyodo2018_ApJ860_150`; future work should extend coverage so that configuration schema and sink logic reference those keys explicitly.
