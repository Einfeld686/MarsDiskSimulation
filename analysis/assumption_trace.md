> **文書種別**: 解説（Diátaxis: Explanation）

## 0. はじめに
現行の火星ロッシュ円盤モデルに含まれる「前提→式」のひも付けを集約するハブとして、このファイルを設ける。フェーズ1は**手動メモのみ**で、`analysis/equations.md` に定義済みの式番号を参照しつつ、`out/plan/assumption_trace_gap_list.md`・`out/plan/assumption_trace_schema.md`・`out/plan/assumption_trace_data_sources.md` に列挙された曖昧な仮定をスケルトン化する。式 (E.xxx) の定義は引き続き `analysis/equations.md` が唯一のソースであり、出典管理は `analysis/UNKNOWN_REF_REQUESTS.*` と `analysis/references.registry.json` に従う。フェーズ2以降で `assumption_trace_schema.md` と `assumption_trace_data_sources.md` に沿った自動スキャナを追加する前提で、ここではクラスタ別のラベルと参照位置だけを固定する。

## 1. フェーズ1の範囲（docs-only）
- eq_id は未確定のまま `TODO(REF:slug)` で立て、式本文や自動抽出ロジックは導入しない。
- 各クラスタに対して slug・仮称ラベル・主要な config トグルを記し、将来の自動ツールが `code_path` や `run_stage` を補完できる「置き場」を準備する。
- 未解決参照は必ず `TODO(REF:<slug>)` を使い、`analysis/UNKNOWN_REF_REQUESTS.jsonl` の運用（AI_USAGE.md に記載）で扱う。場当たり的な TODO コメントは書かない。

## 2. 曖昧な仮定クラスタのメモ
各節は `out/plan/assumption_trace_gap_list.md` の粒度に対応し、`assumption_trace_schema.md` のフィールドを YAML 例で示す（未完フィールドは TODO のまま保持）。

### 2.1 ブローアウト関連（β, a_blow, t_blow） — assumption cluster "blowout_core_v1"
gas-poor かつ火星放射のみを前提に β・ブローアウト境界・`t_blow=1/Ω` を評価するが、Q_pr テーブルの出典と `fast_blowout` 補正の適用条件が式レベルで未整理。`radiation.source="mars"` 固定や `io.correct_fast_blowout` のオン/オフが挙動を変えるため、設定依存の揺らぎを明示する必要がある。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `blowout_core_eid_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: E.007/E.013/E.014
source_doc: analysis/equations.md
paper_ref: Hyodo2018_ApJ860_150
assumption_tags:
  - gas-poor
  - 0D
  - rp_mars_only
  - t_blow_eq_1_over_Omega
config_keys:
  - blowout.enabled
  - radiation.source
  - radiation.TM_K
  - radiation.qpr_table_path
  - io.correct_fast_blowout
  - numerics.dt_init
code_path:
  - [marsdisk/physics/radiation.py:179–288]
  - [marsdisk/grid.py:17–49]
run_stage:
  - surface loop
inputs:
  - Omega [1/s]  # from [marsdisk/grid.py:17–49]
  - Q_pr         # from tables via [marsdisk/io/tables.py:259–295]
outputs:
  - series.a_blow
  - series.t_blow
  - summary.beta_at_smin_config
tests:
  - tests/test_scalings.py
  - tests/test_fast_blowout.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 出典がある要素: β と a_blow の閾値判定および軌道時間スケールでの除去は [@Burns1979_Icarus40_1; @Wyatt2008]、火星放射で「一軌道以内に吹き飛ぶ」近似は [@Hyodo2018_ApJ860_150] で裏付けられる。
- 先行研究が見当たらない要素: `io.correct_fast_blowout` の補正式や `use_solar_rp` / `radiation.source` のスイッチ設計はコード固有（モデル設計扱い）。
- 欠落情報: β と a_blow の参照式 (E.xxx)、`fast_blowout` 補正式の根拠、`use_solar_rp` 無効時の取り扱い。
- 次に確認する資料: `assumption_trace_data_sources.md` のテーブル出典、`analysis/equations.md` の R1–R3 節、`analysis/UNKNOWN_REF_REQUESTS.jsonl`（未登録なら追加）。
- 先行研究メモ: β>0.5 で非束縛となる基準とブローアウト径の決定は [@Burns1979_Icarus40_1] に拠り、軌道時間オーダーで除去される近似は [@StrubbeChiang2006_ApJ648_652] やレビュー [@Wyatt2008] と整合する。一方、`t_blow=1/Ω` を固定する実装方針や `io.correct_fast_blowout` の補正式に直接対応する文献は見当たらない。

### 2.2 遮蔽・ゲート（Φ(τ, ω0, g), τ=1 クリップ, gate_mode） — assumption cluster "shielding_gate_order_v1"
Φテーブルの補間と τ=1 クリップの適用順が `shielding.mode` と `blowout.gate_mode` の組み合わせに依存し、τゲート（`radiation.tau_gate.enable`）との重ねがけ順序がコード依存のまま。ゲート係数 `f_gate` が衝突・昇華どちらと競合するかも明文化が不足している。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `shielding_gate_order_v1`

- LOS/鉛直の使い分け: 衝突寿命や質量輸送は鉛直光学的厚さ τ_vert を、遮蔽・τ=1 クリップ・tau_gate・ブローアウト判定は火星視線方向 τ_los を用いる。Σ_tau1 は τ_los 基準の Σ_tau1_los を意味する。

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: E.015/E.016/E.017/E.031
source_doc: analysis/equations.md
paper_ref: TODO(REF:shielding_gate_order_v1)
assumption_tags:
  - gas-poor
  - tau_gate_optional
  - surface_tau_le_1
config_keys:
  - shielding.mode
  - shielding.table_path
  - shielding.fixed_tau1_tau
  - shielding.fixed_tau1_sigma
  - radiation.tau_gate.enable
  - blowout.gate_mode
  - surface.freeze_sigma
code_path:
  - [marsdisk/physics/shielding.py:81–216]
  - [marsdisk/run.py:968–1116]
  - [marsdisk/run.py:1475–1518]
run_stage:
  - shielding application
  - surface loop (gate evaluation)
inputs:
  - tau  # from PSD κ and Σ_surf
  - Phi(τ, w0, g) table  # from [marsdisk/io/tables.py:273–340]
outputs:
  - series.kappa_eff
  - series.sigma_tau1
  - diagnostics.tau_gate_blocked
  - summary.radiation_tau_gate
tests:
  - tests/test_radiation_shielding_logging.py
  - tests/test_blowout_gate.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 出典がある要素: 光学的に厚い表層のみが放射圧を受けるという遮蔽の描像は [@TakeuchiLin2003_ApJ593_524] に代表される。
- 先行研究が見当たらない要素: Φテーブルの出典特定、Φ→τ=1クリップ→tau_gate/gate_mode の順序、`tau_gate_block_time` のようなゲート持続時間の式はコード固有。
- 欠落情報: Φテーブル出典の正式引用、ゲート適用順序の図式化、`tau_gate_block_time` の式番号。
- 次に確認する資料: `assumption_trace_data_sources.md` のテーブル節、`analysis/equations.md` の遮蔽式、`analysis/overview.md` Provenance セクション。
- 先行研究メモ: デブリ円盤は光学的に薄いという前提は [@Krivov2006_AA455_509] などで共有され、gas-rich の自己遮蔽を扱う例として [@TakeuchiLin2003_ApJ593_524] がある。ただし、Φテーブル→τ=1クリップ→gate/tau_gate の順序を明示した手順に合致する文献は確認できていない。

### 2.3 PSD と wavy 補正（s_min_effective, psd.floor.mode） — assumption cluster "psd_wavy_floor_scope_v1"
`wavy_strength` と最小粒径のクリップ（ブローアウト／設定／動的床）が混在しており、どの PSD 式 (P1) と結び付けるかが未指定。`psd.floor.mode` 切替と `sizes.evolve_min_size` の同時使用時の優先順位も曖昧なままである。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `psd_wavy_floor_scope_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: E.008
source_doc: analysis/equations.md
assumption_tags:
  - gas-poor
  - wavy_optional
  - smin_clipped_by_blowout
config_keys:
  - psd.wavy_strength
  - psd.floor.mode
  - sizes.s_min
  - sizes.evolve_min_size
  - sizes.dsdt_model
  - sizes.apply_evolved_min_size
code_path:
  - [marsdisk/physics/psd.py:30–146]
  - [marsdisk/physics/psd.py:149–219]
  - [marsdisk/run.py:1075–1109]
run_stage:
  - PSD initialisation
  - PSD evolution hooks
inputs:
  - s_min_config [m]
  - wavy_strength [-]
  - ds/dt model  # if evolve_min_size enabled
outputs:
  - series.kappa
  - series.s_min_effective
  - series.s_min_floor_dynamic
  - diagnostics.wavy_params
tests:
  - tests/test_psd_kappa.py
  - tests/test_surface_outflux_wavy.py
  - tests/test_min_size_evolution_hook.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 出典がある要素: ブローアウト近傍で PSD が波打つという現象は [@Krivov2006_AA455_509; @ThebaultAugereau2007_AA472_169] で示されている。
- 先行研究が見当たらない要素: `wavy_strength` で振幅をパラメータ化する設計、複数の s_min 床（ブローアウト/設定/動的）の優先順位、`apply_evolved_min_size` の適用条件は文献に直接の類例がない。
- 欠落情報: wavy 振幅とフェーズの式番号、`s_min_effective` 算定の優先順位、`apply_evolved_min_size` の適用条件。
- 次に確認する資料: `assumption_trace_data_sources.md` の PSD ソース一覧、`analysis/equations.md` の P1 節。
- 先行研究メモ: ブローアウト近傍で波打つ PSD は [@Krivov2006_AA455_509; @ThebaultAugereau2007_AA472_169] で示され、最小粒径をどうクリップするかが光学的厚さやSEDに効くことも報告されている。`wavy_strength` のような振幅パラメータ化や s_min クリップ優先順位を明示する実装は既存論文に見当たらない。

### 2.4 衝突時間スケール（Wyatt / Ohtsuki regime） — assumption cluster "tcoll_regime_switch_v1"
表層 ODE の `t_coll` は Wyatt スケーリング（Ωτ⁻¹）を既定にする一方、Smol カーネルや `surface.use_tcoll` フラグで無効化される経路が混在する。`f_wake` や e/i ダンピングの仮定により τ 推定が揺れるため、どの regime でどの式を使うかが明確でない。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `tcoll_regime_switch_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: E.006/E.007
source_doc: analysis/equations.md
assumption_tags:
  - wyatt_scaling
  - optional_collisions
  - 0D
config_keys:
  - surface.use_tcoll
  - dynamics.f_wake
  - dynamics.e0
  - dynamics.i0
  - numerics.dt_init
code_path:
  - [marsdisk/physics/surface.py:46–219]
  - [marsdisk/run.py:1036–1109]
run_stage:
  - surface loop
inputs:
  - tau  # from PSD/Σ_surf
  - Omega [1/s]
outputs:
  - series.t_coll
  - diagnostics.ts_ratio
  - summary.phase_branching.t_coll_stats
tests:
  - tests/test_scalings.py
  - tests/test_phase3_surface_blowout.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 出典がある要素: t_coll ∝ (Ω τ)^-1 のスケーリングや高τで t_coll ≃ Ω^-1 となる描像は [@Wyatt2008; @Ohtsuki2002_Icarus155_436] で整理される。
- 先行研究が見当たらない要素: Wyatt/Ohtsuki の regime 切替条件、Smol カーネルと表層 t_coll を併用する設計、`f_wake` 係数の形はコード固有。
- 欠落情報: Ohtsuki regime への切替条件、`f_wake` の式番号、Smol カーネルと表層 t_coll の整合性。
- 次に確認する資料: `assumption_trace_data_sources.md` のコード走査ターゲット、`analysis/equations.md` の C1–C4 節。
- 先行研究メモ: τ_eff から t_coll≈t_per/(4π τ) を与える簡易式はレビュー [@Wyatt2008] で整理され、内在衝突確率ベースの計算法は [@Ohtsuki2002_Icarus155_436] に代表される。これらを条件分岐でスイッチし、Smoluchowski 解と突き合わせる具体手順を示す文献は見つかっていない。

### 2.5 昇華・ガス抗力（sinks.mode, rp_blowout.enable, TL2003） — assumption cluster "sublimation_gasdrag_scope_v1"
gas-poor 既定で昇華のみを有効にし、TL2003（gas-rich 前提）は `ALLOW_TL2003=false` で無効化する運用だが、設定 YAML とドキュメントの整合が未確認。`sinks.mode` や `rp_blowout.enable`、`sinks.enable_gas_drag` の組み合わせが式参照なしに切り替わる点が曖昧。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `sublimation_gasdrag_scope_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: E.018/E.019/E.036/E.037/E.038
source_doc: analysis/equations.md
assumption_tags:
  - gas-poor
  - TL2003_disabled
  - sublimation_default
config_keys:
  - sinks.mode
  - sinks.enable_sublimation
  - sinks.enable_gas_drag
  - sinks.rho_g
  - sinks.rp_blowout.enable
  - radiation.use_mars_rp
code_path:
  - [marsdisk/physics/sinks.py:34–160]
  - [marsdisk/physics/sublimation.py:386–496]
  - [marsdisk/run.py:986–1109]
run_stage:
  - sink selection
  - surface loop
inputs:
  - T_use [K]
  - rho_p [kg/m^3]
  - Omega [1/s]
outputs:
  - series.t_sink
  - diagnostics.sink_selected
  - summary.sublimation_provenance
tests:
  - tests/test_sinks_none.py
  - tests/test_sublimation_phase_gate.py
  - tests/test_phase_branching_run.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 出典がある要素: gas-rich 円盤での放射圧＋ガス抗力流は [@TakeuchiLin2002_ApJ581_1344; @TakeuchiLin2003_ApJ593_524]、昇華支配ダストの寿命スケールは蒸気圧起源の ds/dt モデル（例: [@PollackBurnsTauber1979_Icarus37_587; @Olofsson2022_MNRAS513_713]）で与えられる。
- 先行研究が見当たらない要素: gas-poor を既定にして TL2003 を無効化する運用、gas-rich 感度試験時のフラグ切替や `sinks.mode` の優先順位はコード固有。
- 欠落情報: 昇華式の (E.xxx) ひも付け、TL2003 無効の根拠引用位置、gas-rich 感度試験時の手順。
- 次に確認する資料: `assumption_trace_data_sources.md` の設定パース手順、`analysis/equations.md` の昇華式、`analysis/UNKNOWN_REF_REQUESTS.jsonl` での TL2003 slug 登録。
- 先行研究メモ: gas-poor を前提に放射圧と衝突・昇華を扱う枠組みはレビュー [@Krivov2006_AA455_509] で整理され、gas-drag を含む遷移円盤の解析は [@TakeuchiLin2002_ApJ581_1344; @TakeuchiLin2003_ApJ593_524]、drag が支配的になる密度域の例は [@PollackBurnsTauber1979_Icarus37_587; @Olofsson2022_MNRAS513_713] にみられる。TL2003/gas_drag フラグのオン/オフ条件を定量規定する文献は見当たらない。

### 2.6 半径・幾何の固定（0D vs disk.geometry） — assumption cluster "radius_fix_0d_scope_v1"
0D 実行では `disk.geometry`（r_in_RM, r_out_RM）が必須入力で、legacy `geometry.r` / `runtime_orbital_radius_rm` は無効化済み。半径固定のまま 1D 拡張へ式を持ち越す際に、どの E.xxx が 0D 前提かをタグ付けできていない。

このクラスターに対応する UNKNOWN_REF_REQUESTS slug: `radius_fix_0d_scope_v1`

```yaml
# NOTE: Phase 1 skeleton example, not yet complete.
eq_id: E.001/E.002
source_doc: analysis/equations.md
assumption_tags:
  - 0D
  - fixed_radius
  - inner_disk_scope
config_keys:
  - disk.geometry.r_in_RM
  - disk.geometry.r_out_RM
  - geometry.mode
  - geometry.r  # legacy (disallowed)
  - geometry.runtime_orbital_radius_rm  # legacy (disallowed)
run_stage:
  - config loading
  - orbital grid initialisation
code_path:
  - [marsdisk/schema.py:22–75]
  - [marsdisk/grid.py:17–49]
  - [marsdisk/run.py:966–1016]
inputs:
  - r_in_RM / r_out_RM  # runtime radius is derived from disk.geometry
outputs:
  - summary.runtime_orbital_radius_m
  - run_config.runtime_orbital_radius_rm
tests:
  - tests/test_scope_limitations_metadata.py
  - tests/test_run_regressions.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 出典がある要素: one-zone / annulus 近似の使用や狭いリングを代表半径で扱う手法は [@Wyatt2008; @CridaCharnoz2012_Science338_1196] などで一般的。
- 先行研究が見当たらない要素: `disk.geometry` を 0D 必須入力とし、1D 拡張時に 0D 前提の式をタグ管理する運用はコード固有。
- 欠落情報: 半径解像度を持たない式の一覧、1D 拡張時に再確認すべき E.xxx、`scope.region` との整合。
- 次に確認する資料: `assumption_trace_data_sources.md` の設定ファミリ、`analysis/overview.md` の geometry 記述。
- 先行研究メモ: single-annulus 的に代表半径で衝突カスケードを解く枠組みはレビュー [@Wyatt2008] で整理されるが、火星ロッシュ円盤のような高光学的厚さリングを 0D 固定で扱い、後段で 1D に拡張する手順を明文化した文献は未確認。

## 3. 先行研究の有無まとめ
- blowout_core_eid_v1 (E.007/E.013/E.014): β・a_blow・t_blow≃Ω^-1 は [@Burns1979_Icarus40_1; @Wyatt2008; @Hyodo2018_ApJ860_150] に依拠、一方で `fast_blowout` 補正や `use_solar_rp` は文献なしの設計。
- shielding_gate_order_v1 (E.015/E.016/E.017/E.031): Φ(τ, ω0, g) で遮蔽する考え方は [@TakeuchiLin2003_ApJ593_524] で妥当、ゲート順序や τ=1 クリップのロジックは先行研究なし。
- psd_wavy_floor_scope_v1 (E.008): wavy PSD の存在は [@Krivov2006_AA455_509; @ThebaultAugereau2007_AA472_169] が裏付け、`wavy_strength` や s_min 床の優先順位は設計判断。
- tcoll_regime_switch_v1 (E.006/E.007): t_coll∝(Ωτ)^-1 のスケーリングは [@Wyatt2008; @Ohtsuki2002_Icarus155_436] に合致、Wyatt/Ohtsuki 切替や Smol 併用ルールは設計判断。
- sublimation_gasdrag_scope_v1 (E.018/E.019/E.036/E.037/E.038): 昇華・gas-drag の基礎式は [@TakeuchiLin2002_ApJ581_1344; @TakeuchiLin2003_ApJ593_524; @PollackBurnsTauber1979_Icarus37_587] などで定義済み、gas-poor 既定で TL2003 無効とする運用はコード固有。
- radius_fix_0d_scope_v1 (E.001/E.002): 0D one-zone/annulus 近似は [@Wyatt2008; @CridaCharnoz2012_Science338_1196] で一般的だが、`disk.geometry` 固定を前提とするタグ管理は文献なし。

<!-- @-- BEGIN:ASSUMPTION_REGISTRY -- -->
### 自動生成セクション（assumption_registry.jsonl 由来）
| id | scope | eq_ids | tags | config_keys | run_stage | provenance | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| blowout_core_eid_v1 | toggle | E.007, E.013, E.014 | gas-poor, 0D, rp_mars_only, t_blow_eq_1_over_Omega | blowout.enabled, radiation.source, radiation.TM_K, radiation.qpr_table_path, io.correct_fast_blowout, numerics.dt_init | surface loop | Burns1979_Icarus40_1 | draft |
| shielding_gate_order_v1 | toggle | E.015, E.016, E.017, E.031 | gas-poor, tau_gate_optional, surface_tau_le_1 | shielding.mode, shielding.table_path, shielding.fixed_tau1_tau, shielding.fixed_tau1_sigma, radiation.tau_gate.enable, blowout.gate_mode, surface.freeze_sigma | shielding application, surface loop (gate evaluation) | TakeuchiLin2003_ApJ593_524 | draft |
| psd_wavy_floor_scope_v1 | module_default | E.008 | gas-poor, wavy_optional, smin_clipped_by_blowout | psd.wavy_strength, psd.floor.mode, sizes.s_min, sizes.evolve_min_size, sizes.dsdt_model, sizes.apply_evolved_min_size | PSD initialisation, PSD evolution hooks | Krivov2006_AA455_509 | draft |
| tcoll_regime_switch_v1 | module_default | E.006, E.007 | wyatt_scaling, optional_collisions, 0D | surface.use_tcoll, dynamics.f_wake, dynamics.e0, dynamics.i0, numerics.dt_init | surface loop | Wyatt2008 | draft |
| sublimation_gasdrag_scope_v1 | toggle | E.018, E.019, E.036, E.037, E.038 | gas-poor, TL2003_disabled, sublimation_default | sinks.mode, sinks.enable_sublimation, sinks.enable_gas_drag, sinks.rho_g, sinks.rp_blowout.enable, radiation.use_mars_rp | sink selection, surface loop | TakeuchiLin2002_ApJ581_1344 | draft |
| radius_fix_0d_scope_v1 | module_default | E.001, E.002 | 0D, fixed_radius, inner_disk_scope | geometry.mode, disk.geometry.r_in_RM, disk.geometry.r_out_RM | config loading, orbital grid initialisation | Wyatt2008 | draft |
| ops:gas_poor_default | project_default | - | ops:gas_poor_default, geometry:thin_disk | radiation.ALLOW_TL2003, radiation.use_mars_rp, sinks.enable_gas_drag | physics_controls | Hyodo2018_ApJ860_150 | draft |
| radiative_cooling_tmars | module_default | E.042, E.043 | radiation:tmars_graybody, ops:gas_poor_default | radiation.TM_K, mars_temperature_driver.constant | physics_controls | Hyodo2018_ApJ860_150 | draft |
| viscosity_c5_optional | toggle | - | diffusion_optional, C5 | viscosity.enabled | smol_kernel | CridaCharnoz2012_Science338_1196 | draft |
| ops:qpr_table_generation | module_default | - | ops:qpr_table | radiation.qpr_table_path | prep | config | draft |
| equations_unmapped_stub | module_default | E.003, E.004, E.005, E.009, E.010, E.011, E.012, E.020, E.021, E.022, E.023, E.024, E.025, E.026, E.027, E.028, E.032, E.033, E.035, E.039 | placeholder | - | - | assumption:eq_unmapped_placeholder | needs_ref |
| ops:gas_poor_default | project_default | - | ops:gas_poor_default, geometry:thin_disk | radiation.ALLOW_TL2003, radiation.use_mars_rp, sinks.enable_gas_drag | physics_controls | Hyodo2018_ApJ860_150 | draft |
| radiative_cooling_tmars | module_default | E.042, E.043 | radiation:tmars_graybody, ops:gas_poor_default | radiation.TM_K, mars_temperature_driver.constant | physics_controls | Hyodo2018_ApJ860_150 | draft |
| viscosity_c5_optional | toggle | - | diffusion_optional, C5 | viscosity.enabled | smol_kernel | CridaCharnoz2012_Science338_1196 | draft |
| ops:qpr_table_generation | module_default | - | ops:qpr_table | radiation.qpr_table_path | prep | config | draft |
<!-- @-- END:ASSUMPTION_REGISTRY -- -->
