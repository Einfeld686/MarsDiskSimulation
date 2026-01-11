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
gas-poor かつ火星放射のみを前提に β・ブローアウト境界・`t_blow=1/Ω` を評価する。β=0.5 を吹き飛び境界とする運用はデブリ円盤文献で一般的だが、Q_pr テーブル（屈折率・粒子形状・波長グリッド）の来歴と `fast_blowout` 補正の適用条件は式レベルで未整理。`radiation.source="mars"` 固定や `io.correct_fast_blowout` のオン/オフが挙動を変えるため、設定依存の揺らぎを明示する必要がある。

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
  - [marsdisk/physics/radiation.py#qpr_lookup [L275–L337]]
  - [marsdisk/grid.py#omega_kepler [L17–L33]]
run_stage:
  - surface loop
inputs:
  - Omega [1/s]  # from [marsdisk/grid.py#omega_kepler [L17–L33]]
  - Q_pr         # from tables via [marsdisk/io/tables.py#load_qpr_table [L390–L402]]
outputs:
  - series.a_blow
  - series.t_blow
  - summary.beta_at_smin_config
tests:
  - tests/integration/test_scalings.py
  - tests/integration/test_fast_blowout.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 文献で支えられる部分:
  - β 定義と Q_pr を含む放射圧/重力比の式は古典整理 [@Burns1979_Icarus40_1] に従う。
  - β=0.5 をブローアウト境界とし、粒径・密度・Q_pr に依存する式を明示する例として [@PawellekKrivov2015_MNRAS454_3207]（Burns 式の写経）が使える。
  - β>0.5 粒が公転時間オーダーで失われる近似は Wyatt の講義・レビュー [@Wyatt2008] と整合し、`t_blow=1/Ω` はその実装代表。
  - 火星放射を吹き飛び源とみなす前提は [@Hyodo2018_ApJ860_150] が揮発散逸の議論で採用している。
- 文献で見つからなかった部分: `io.correct_fast_blowout` の補正式や適用条件、`use_solar_rp`/`radiation.source` の分岐仕様は先行研究に同型がなく、数値安定化の設計として明記する必要がある。
- 文献で見つからなかった部分: Q_pr テーブルの作成条件（屈折率ソース、粒子形状、波長分割、ミー計算コード）を文献に一致する形で固定した例は確認できず、実装選択として来歴を埋める必要がある。`io.correct_fast_blowout` の補正式や適用条件、`use_solar_rp`/`radiation.source` の分岐仕様も先行研究に同型がない。
- 欠落情報: β と a_blow の参照式 (E.xxx)、`fast_blowout` 補正式の根拠、`use_solar_rp` 無効時の取り扱い、Q_pr テーブルのデータ出典（屈折率・粒子形状・波長グリッド・Mie solver）。
- 次に確認する資料: `assumption_trace_data_sources.md` のテーブル出典、`analysis/equations.md` の R1–R3 節、`analysis/UNKNOWN_REF_REQUESTS.jsonl`（未登録なら追加）。
- 先行研究メモ: β>0.5 で非束縛となる基準とブローアウト径の決定は [@Burns1979_Icarus40_1] に拠り、軌道時間オーダーで除去される近似は [@StrubbeChiang2006_ApJ648_652; @Wyatt2008] と整合する。[@PawellekKrivov2015_MNRAS454_3207] は β=0.5 境界の使い方をデブリ円盤で明示しており、ここを文献根拠とする。一方、`t_blow=1/Ω` を固定する実装方針や `io.correct_fast_blowout` の補正式、Q_pr テーブル生成条件に直接対応する文献は見当たらない。

### 2.2 遮蔽・ゲート（Φ(τ, ω0, g), τ=1 クリップ, gate_mode） — assumption cluster "shielding_gate_order_v1"
Φテーブルの補間と τ=1 クリップの適用順が `shielding.mode` と `blowout.gate_mode` の組み合わせに依存し、τゲート（`radiation.tau_gate.enable`）との重ねがけ順序がコード依存のまま。Φテーブル自体も two-stream / delta-Eddington など近似名を明示せずに置いており、ゲート係数 `f_gate` が衝突・昇華どちらと競合するかも明文化が不足している。

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
  - [marsdisk/physics/shielding.py#apply_shielding [L134–L217]]
  - [marsdisk/io/diagnostics.py#write_zero_d_history [L28–L142]]
  - [marsdisk/run_zero_d.py#run_zero_d [L1392–L5977]]
run_stage:
  - shielding application
  - surface loop (gate evaluation)
inputs:
  - tau  # from PSD κ and Σ_surf
  - Phi(τ, w0, g) table  # from [marsdisk/io/tables.py#load_phi_table [L405–L482]]
outputs:
  - series.kappa_eff
  - series.sigma_tau1
  - diagnostics.tau_gate_blocked
  - summary.radiation_tau_gate
tests:
  - tests/integration/test_radiation_shielding_logging.py
  - tests/integration/test_blowout_gate.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 文献で支えられる部分:
  - 光学的に厚いダスト円盤の表層を放射圧が外向きに動かす描像は [@TakeuchiLin2003_ApJ593_524] が直接扱う。
  - ガス抗力との競合を含む枠組みは [@TakeuchiLin2002_ApJ581_1344] がデブリ円盤で整理している。
  - Φ(τ, ω0, g) の引数である光学的厚さ・単一散乱アルベド・非対称因子の組は、大気放射輸送（例: libRadtran 解説）でも標準的に用語が定義されている。
- 文献で見つからなかった部分: Φテーブル自体の出典や two-stream / delta-Eddington などの近似名、そして「Φ→τ=1クリップ→tau_gate/gate_mode」の適用順序や `tau_gate_block_time` の扱いを手続きとして明記した論文は見当たらず、実装規約として固定する必要がある。
- 欠落情報: Φテーブル出典の正式引用、使用する近似名（two-stream/delta-Eddington など）の固定、ゲート適用順序の図式化、`tau_gate_block_time` の式番号。
- 次に確認する資料: `assumption_trace_data_sources.md` のテーブル節、`analysis/equations.md` の遮蔽式、`analysis/overview.md` Provenance セクション。
- 先行研究メモ: デブリ円盤は光学的に薄いという前提は [@Krivov2006_AA455_509] などで共有され、gas-rich の自己遮蔽を扱う例として [@TakeuchiLin2003_ApJ593_524] がある。ただし、Φテーブル→τ=1クリップ→gate/tau_gate の順序を明示した手順や、two-stream / delta-Eddington 近似に基づく Φ テーブルをどう差し替えるかまで規定した文献は確認できていない。

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
  - [marsdisk/physics/psd.py#update_psd_state [L78–L170]]
  - [marsdisk/physics/psd.py#apply_uniform_size_drift [L419–L560]]
  - [marsdisk/run_zero_d.py#run_zero_d [L1392–L5977]]
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
  - tests/integration/test_psd_kappa.py
  - tests/integration/test_surface_outflux_wavy.py
  - tests/integration/test_min_size_evolution_hook.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 文献で支えられる部分:
  - 放射圧と衝突を組み合わせて PSD や空間分布を解き、ブローアウト端での歪みを示す例として [@Krivov2006_AA455_509] がある。
  - 衝突カスケードで τ や Ω を明示しつつ波打ちを説明する例として [@ThebaultAugereau2007_AA472_169] が挙げられる。
  - ブローアウト端での「波打ち」をレビュー的に整理する資料として Wyatt 系の講義ノートがあり、モデルの基本をなぞる形で説明されている。
- 文献で見つからなかった部分: `wavy_strength` のように振幅を単一パラメータ化する設計や、s_min をブローアウト/設定/動的床でクリップしたときの優先順位は先行研究で同名の定義が見当たらず、モデル化の選択（provenance.type=impl_choice）として明示する必要がある。
- 欠落情報: wavy 振幅とフェーズの式番号、`s_min_effective` 算定の優先順位、`apply_evolved_min_size` の適用条件、`wavy_strength` を 0 にした場合の wavy 抑制の定義。
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
  - [marsdisk/physics/surface.py#step_surface_density_S1 [L110–L192]]
  - [marsdisk/run_zero_d.py#run_zero_d [L1392–L5977]]
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
  - tests/integration/test_scalings.py
  - tests/integration/test_phase3_surface_blowout.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 文献で支えられる部分:
  - t_coll ∝ (Ω τ)^-1 のスケーリングはレビュー [@Wyatt2008] に整理され、単純化が破れうる理由は [@ThebaultAugereau2007_AA472_169] が詳しい。
  - τ や Ω を衝突カスケードの議論に明示的に組み込んだ例として [@ThebaultAugereau2007_AA472_169] があり、Wyatt 型の単純化と同じ変数で接続できる。
  - 速度分散や衝突確率を力学から扱う枠組みは [@Ohtsuki2002_Icarus155_436] の三体計算と解析式が代表。
- 文献で見つからなかった部分: Wyatt と Ohtsuki の regime をどの条件で切り替えるか、Smol カーネルと表層 t_coll を併用する手順、`f_wake` の形は先行研究に明文化がなく、実装仕様として定義が必要。高 τ で t_coll≈Ω^-1 に切り替える「上限」も安全策であり、文献由来ではない（provenance.type=impl_choice）。
- 欠落情報: Ohtsuki regime への切替条件、`f_wake` の式番号、Smol カーネルと表層 t_coll の整合性、Ω^-1 への上限の根拠と閾値。
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
  - [marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]
  - [marsdisk/physics/sublimation.py#choose_psat_backend [L434–L555]]
  - [marsdisk/run_zero_d.py#run_zero_d [L1392–L5977]]
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
  - tests/integration/test_sinks_none.py
  - tests/integration/test_sublimation_phase_gate.py
  - tests/integration/test_phase_branching_run.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 文献で支えられる部分:
  - 放射圧とガス抗力の競合を含む dust-gas 運動は [@TakeuchiLin2002_ApJ581_1344] が代表で、表層アウトフローを gas-rich 条件で扱うのは [@TakeuchiLin2003_ApJ593_524]。
  - 火星衝突円盤が溶融主体で蒸気≲数%となり得るという gas-poor の見通しは [@Hyodo2017a_ApJ845_125] が示す。
  - 小衛星を残すには低質量円盤が要るという方向性は [@CanupSalmon2018_SciAdv4_eaar6887] が Science Advances で議論する。
  - 放射圧を揮発散逸に組み込む前提は [@Hyodo2018_ApJ860_150] で扱われ、昇華速度はヘルツ＝クヌーセン式（例: [@Markkanen2020_AA643_A16] の彗星ダスト熱物理モデル）が広く使われる。
- 文献で見つからなかった部分: TL2003 をいつ有効化するか、ガス抗力をどの密度でオンにするかといった閾値は先行研究に明示がなく、無次元比（放射圧加速と抗力減速の比較など）で仕様化する必要がある。`sinks.mode` や `rp_blowout.enable` の優先順位も設計判断。Pollack–Burns–[@PollackBurnsTauber1979_Icarus37_587] はガス抗力側の参照であり、昇華の ds/dt 根拠に使う場合は出典ずれに注意する。
- 欠落情報: 昇華式の (E.xxx) ひも付け、TL2003 無効の根拠引用位置、gas-rich 感度試験時の手順、昇華 ds/dt に紐付く参照（[@Markkanen2020_AA643_A16] など）を registry へ登録するかどうかの判断。
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
  - [marsdisk/schema.py#DiskGeometry [L48–L75]]
  - [marsdisk/grid.py#omega_kepler [L17–L33]]
  - [marsdisk/io/diagnostics.py#write_zero_d_history [L28–L142]]
inputs:
  - r_in_RM / r_out_RM  # runtime radius is derived from disk.geometry
outputs:
  - summary.runtime_orbital_radius_m
  - run_config.runtime_orbital_radius_rm
tests:
  - tests/integration/test_scope_limitations_metadata.py
  - tests/integration/test_run_regressions.py
status: draft
owner: maintainer
last_checked: YYYY-MM-DD
```

- 文献で支えられる部分: 幅の狭いリングや one-zone/annulus 近似を代表半径で扱う手法はレビュー [@Wyatt2008] やリング進化モデル [@CridaCharnoz2012_Science338_1196] で一般的。
- 文献で見つからなかった部分: 0D 前提で `disk.geometry` を必須入力にし、1D 拡張時にどの式が 0D 固定かをタグ管理する運用は先行研究に類例がなく、プロジェクト仕様として明記する必要がある。
- 欠落情報: 半径解像度を持たない式の一覧、1D 拡張時に再確認すべき E.xxx、`scope.region` との整合。
- 次に確認する資料: `assumption_trace_data_sources.md` の設定ファミリ、`analysis/overview.md` の geometry 記述。
- 先行研究メモ: single-annulus 的に代表半径で衝突カスケードを解く枠組みはレビュー [@Wyatt2008] で整理されるが、火星ロッシュ円盤のような高光学的厚さリングを 0D 固定で扱い、後段で 1D に拡張する手順を明文化した文献は未確認。

### 2.7 前提トレーサビリティと標準（PROV/FAIR/Codemeta/RO-Crate）
assumption_id と provenance 情報を機械可読で持たせる仕組みは、W3C PROV-DM の「実体・活動・責任主体」や FAIR 原則、研究ソフトウェア向けメタデータ（CodeMeta）、研究データ梱包（RO-Crate）の方針と整合する。assumption_trace 系では以下を運用する:

- `provenance.type` で `literature` / `impl_choice` / `safety_cap` / `data_source` を区別し、文献式と実装安全策の混同を避ける。
- data source（例: Q_pr テーブル、Φ テーブル）の生成元・屈折率ソース・近似名を registry/UNKNOWN_REF_REQUESTS で追跡し、run_card にも残す。
- activity（生成スクリプト）と agent（担当者/CI）を CodeMeta/RO-Crate 互換で外部化する余地を残しつつ、当面は registry と run_card のメタデータで代替する。

## 3. 先行研究の有無まとめ
- blowout_core_eid_v1 (E.007/E.013/E.014): β・a_blow・t_blow≃Ω^-1 は [@Burns1979_Icarus40_1; @Wyatt2008; @Hyodo2018_ApJ860_150]（β=0.5境界は [@PawellekKrivov2015_MNRAS454_3207]が Burns 式として明示）で支えられるが、`fast_blowout` 補正や `use_solar_rp`、Q_pr テーブルの来歴は設計判断。
- shielding_gate_order_v1 (E.015/E.016/E.017/E.031): 表層の遮蔽・アウトフローは [@TakeuchiLin2003_ApJ593_524] が根拠、Φテーブル出典や two-stream/delta-Eddington などの近似名、ゲート順序は実装規約。
- psd_wavy_floor_scope_v1 (E.008): ブローアウト近傍の wavy PSD は [@Krivov2006_AA455_509; @ThebaultAugereau2007_AA472_169] で確認され、`wavy_strength` と s_min クリップ優先順位は設計判断。
- tcoll_regime_switch_v1 (E.006/E.007): t_coll∝(Ωτ)^-1 の整理は [@Wyatt2008; @ThebaultAugereau2007_AA472_169; @Ohtsuki2002_Icarus155_436] で裏付けられ、Wyatt/Ohtsuki 切替や Ω^-1 への上限設定、Smol 併用条件は実装判断。
- sublimation_gasdrag_scope_v1 (E.018/E.019/E.036/E.037/E.038): ガス抗力＋放射圧枠組みは [@TakeuchiLin2002_ApJ581_1344; @TakeuchiLin2003_ApJ593_524]、gas-poor 既定は [@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887]、放射圧導入は [@Hyodo2018_ApJ860_150] を根拠とし、ガス抗力閾値や昇華 ds/dt の参照先、TL2003/gas_drag のオン・オフ閾値は設計判断。
- radius_fix_0d_scope_v1 (E.001/E.002): 0D one-zone/annulus 近似は [@Wyatt2008; @CridaCharnoz2012_Science338_1196] で一般的だが、`disk.geometry` 固定を前提とするタグ管理は文献なし。

## 4. 最優先で確認する文献（6クラスタ共通の芯）
- [@Burns1979_Icarus40_1]: β と Q_pr を含む放射圧の古典整理（ブローアウト境界の基本式）。
- [@Wyatt2008]: ブローアウト・衝突時間・カスケードを横断的にレビューする標準資料。
- [@TakeuchiLin2003_ApJ593_524]: 光学的に厚い gas-rich 円盤表層の放射圧アウトフローと遮蔽の扱い。
- [@Krivov2006_AA455_509]: 放射圧＋衝突で PSD/空間分布とブローアウト端の歪みを扱う代表例。
- [@Hyodo2017a_ApJ845_125; @CanupSalmon2018_SciAdv4_eaar6887]: 火星起源円盤が低質量・gas-poor である前提の根拠（小衛星形成条件を含む）。

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
| ops:qpr_table_generation | module_default | - | ops:qpr_table | radiation.qpr_table_path | prep | assumption:qpr_table_provenance | needs_ref |
| equations_unmapped_stub | module_default | E.003, E.004, E.005, E.009, E.010, E.011, E.012, E.020, E.021, E.022, E.023, E.024, E.025, E.026, E.027, E.028, E.032, E.033, E.035, E.039 | placeholder | - | - | assumption:eq_unmapped_placeholder | needs_ref |
<!-- @-- END:ASSUMPTION_REGISTRY -- -->
