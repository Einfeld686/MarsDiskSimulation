# Provenance Report

- **Equation coverage**: 7 / 44 headings in `analysis/equations.md` carry confirmed tags (≈15.9%). Key anchors include (E.006) for the Strubbe–Chiang surface lifetime and (E.042)/(E.043) for the Hyodo et al. cooling/greybody laws. [@StrubbeChiang2006_ApJ648_652; @Hyodo2018_ApJ860_150]
- **Code mappings**: 23 anchors in `analysis/source_map.json` link the registry keys across radiation, surface, sublimation, siO₂ cooling, and the gas-poor guidance in `analysis/overview.md` / `analysis/run-recipes.md`. All entries reference normalized keys from `analysis/references.registry.json`.
- **Unknown packets**: 0（`tl2003_surface_flow_scope_v1`, `tmars_cooling_solution_v1`, `tp_radiative_equilibrium_v1`, `siO2_thresholds_v1` は文献登録済み: TL2002/2003/ Shadmehri gas-rich範囲、Hyodo17/18 + Lesher&Spera/Robertsonで冷却層物性、Bohren&Huffman/Blanco/Draine/Hocukで⟨Q_abs⟩、Bruning/Ojovan/Meloshで SiO₂ 閾値）。

## Coverage Summary

| Category | Count |
| --- | --- |
| Total equations (E.xxx) | 44 |
| Equations with `[@Key]` | 7 |
| Equations with `TODO(REF:...)` | 37 |
| Code anchors in `source_map.json` | 23 |
| Registry entries | 31 |

Known tags presently include `Hyodo2018_ApJ860_150`, `StrubbeChiang2006_ApJ648_652`, `Pignatale2018_ApJ853_118`, `Ronnet2016_ApJ828_109`, `CridaCharnoz2012_Science338_1196`, `CanupSalmon2018_SciAdv4_eaar6887`, and `Kuramoto2024`. These anchor the thermal history, β/blow-out relations, sublimation chemistry, condensation sinks, viscous spreading regimes, disk-mass/tidal constraints, and the MMX-era review baseline.

## Resolved items (recent)

1. **`tl2003_surface_flow_scope_v1`** — Scope tied to gas-rich, optically厚 TL2002/2003 surfaces, documented with Shadmehri (2008); defaultは gas-poor opt-out。[@TakeuchiLin2003_ApJ593_524; @TakeuchiLin2002_ApJ581_1344; @Shadmehri2008_ApSS314_217]
2. **`tmars_cooling_solution_v1`** — Slab冷却に使う $D,\rho,c_p$ を Hyodo17/18 の衝突後温度と Lesher & Spera / Robertson の溶融物・岩石物性で裏付け。[@Hyodo2018_ApJ860_150; @Hyodo2017a_ApJ845_125; @LesherSpera2015_EncyclopediaVolcanoes; @Robertson1988_USGS_OFR88_441]
3. **`tp_radiative_equilibrium_v1`** — ⟨Q_abs⟩ テーブルの根拠として Burns/Bohren&Huffman の理論と Blanco/Draine/Hocuk のプランク平均実例を採用、`q_abs_mean` 既定が近似であることを明示。[@Burns1979_Icarus40_1; @BohrenHuffman1983_Wiley; @Blanco1976_ApSS41_447; @Draine2003_SaasFee32; @Hocuk2017_AA604_A58]
4. **`siO2_thresholds_v1`** — SiO₂ ガラス転移と液相線を Bruning (DTA), Ojovan (レビュー), Melosh (EOS) で正当化し、低圧純物質の代表値として 1475/1986 K を採用。[@Bruning2003_JNCS330_13; @Ojovan2021_Materials14_5235; @Melosh2007_MPS42_2079]

## Known Reference Notes

- `Takeuchi & Lin (2003)` (`TakeuchiLin2003_ApJ593_524`) は gas-rich オプションとして registry に残しつつ、コード側は `ALLOW_TL2003=false` を既定として docstring に引用を明示した。
- Wyatt (2008) remains a contextual review, while Strubbe & Chiang (2006) provides the normative gas-poor collisional and β scalings implemented in `marsdisk/physics/surface.py` and `marsdisk/physics/radiation.py`.
- `Kuramoto (2024)` (`Kuramoto2024`) is tracked as the MMX/mission-focused cross-check to ensure the overall impact narrative remains consistent with current review articles.
