## 未解決出典（自動問い合わせ）

| Slug | 種別 | 所在 | 優先度 | 概要 |
| --- | --- | --- | --- | --- |
| `tl2003_surface_flow_scope_v1` | assumption | `marsdisk/physics/surface.py:96-163` | medium | Takeuchi & Lin (2003) は光学的に厚い **gas-rich** 表層でのみ放射圧＋ガスドラッグ外流を導くため、`ALLOW_TL2003=false` が既定であり、用途限定で opt-in する必要がある。 |
| `tmars_cooling_solution_v1` | parameter | `siO2_disk_cooling/siO2_cooling_map.py:76-199` | high | Hyodo18 の解析形を流用しているが、$D,\rho,c_p$ の代表値が一次文献で裏付けられていない。冷却層の厚さ・物性の根拠を特定する必要がある。 |
| `tp_radiative_equilibrium_v1` | parameter | `siO2_disk_cooling/siO2_cooling_map.py:142-210` | medium | $⟨Q_{\mathrm{abs}}⟩$ を `q_abs_mean=1.0` で固定しているが、材質・粒径ごとの Planck 平均吸収効率データが未収集。 |
| `siO2_thresholds_v1` | parameter | `siO2_disk_cooling/siO2_cooling_map.py:88-105` | medium | $T_{\mathrm{glass}}=1475$ K と $T_{\mathrm{liquidus}}=1986$ K を純 SiO₂ の代表値として用いているが、圧力・混合比依存の一次ソースが不明。 |

> **指示**: JSONL 形式は `analysis/UNKNOWN_REF_REQUESTS.jsonl` を参照。GPT-5 Pro はスラッグ単位で外部探索を行い、引用候補を registry に追加してから `[@Key]` で再注釈する。
