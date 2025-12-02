# Literature Map for Mars Impact Disk Studies
This file is a machine- and human-readable map of papers relevant to Mars giant impacts, Borealis-scale events, and the origin and evolution of Phobos/Deimos debris disks. Equations stay in `analysis/equations.md`; use this table to decide what to cite for composition, dynamics, or volatile assumptions when drafting slides or code.

## Schema
- **key**: Stable identifier (all caps, no spaces).
- **short_cite**: Minimal label with authors/year.
- **topic**: One-line statement of how the paper is used here.
- **origin**: `global_review` | `impact_sph_dynamics` | `disk_thermodynamics` | `composition_observations` | `volatile_evolution` | `other`.
- **status**: `core` (shapes model) | `supporting` (parameters/background) | `reference` (not yet wired).
- **priority**: `must_read` | `high` | `medium` | `low` for this project.
- **audience**: `self` | `ai_assistant` | `both`.
- **math_level**: `low` | `medium` | `high`.
- **notes**: 1–3 sentences on what to remember for slides and assumptions; do not restate equations (see `equations.md` for formulas).

## Literature table
| key | short_cite | topic | origin | status | priority | audience | math_level | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LIT_PIGNATALE2018_COMP | Pignatale+2018 (impact origin III) | Composition outcomes of Mars moon-forming impacts for different impactors/materials. | disk_thermodynamics | supporting | high | both | medium | Provides volatile/silicate partitioning after impact; useful for setting initial composition and comparing to MMX targets; cite when arguing for impactor diversity effects. |
| LIT_RONNET2016_DISK | Ronnet+2016 (reconciling moons) | Orbits and physical properties of Phobos/Deimos under impact disk and condensation scenarios. | impact_sph_dynamics | core | must_read | both | medium | Frames gas-poor disk plus condensation pathways; constraints on optical depth/texture consistent with MMX spectra; good anchor for background slides. |
| LIT_HYODO2018_VOLATILES | Hyodo+2018 (impact origin IV) | Volatile depletion and loss pathways in post-impact Mars disks. | volatile_evolution | core | must_read | both | medium | Gives volatile escape timescales and depletion factors; informs whether gas-rich TL2003-like layers are plausible; cite when justifying gas-poor default. |
| LIT_KURAMOTO2024_REVIEW | Kuramoto 2024 (AR-EPS review) | High-level review of Phobos/Deimos origin scenarios and observational constraints. | global_review | supporting | high | both | low | Broad synthesis for slide framing; use to contrast capture vs impact vs co-accretion without new equations. |
| LIT_CANUP2018_GASPOOR | Canup & Salmon 2018 (impact sims) | SPH/N-body constraints on low-mass, gas-poor disks that leave small moons. | impact_sph_dynamics | core | high | both | medium | Supports low-gas, low-mass disk assumption; handy for arguing against long-lived dense gas layers; informs initial Σ and vapor fractions. |
| LIT_MMX2021_OVERVIEW | Usui+2021 (MMX mission) | Mission goals and expected measurements relevant to composition/volatiles of Phobos/Deimos. | composition_observations | reference | medium | both | low | Useful for slide context and for mapping model outputs to MMX observables; does not provide equations but sets observational targets. |

## Maintenance
This file is manually curated; keep the column set and value vocabularies unchanged when adding entries. Do not move it out of `analysis/` because tooling and AI agents expect it here. Append new rows with stable `key` values, avoid auto-generation, and keep detailed formulas in `analysis/equations.md`.
