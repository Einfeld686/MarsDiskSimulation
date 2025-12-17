# Phase 6 リサーチ（時間解像度診断と表層ゲートの下調べ）

## 1. 時間解像度の実態
- 時間グリッド決定は `_resolve_time_grid` で `t_end` を `numerics.t_end_orbits` または `t_end_years` から決定し、`dt_init="auto"` の場合は `0.05*t_blow_nominal` と `t_end/200` の最小値を採用、明示指定時はその値を使う。決定値は `time_grid` メタデータとしてまとめられる（dt が `MAX_STEPS` を超える場合のみ刻み直し）（marsdisk/run.py:249-310, 984-995, 1891-1902）。
- メインループは固定刻み `dt` で `time_start=step_no*dt` を進め、`eval_per_step` 有効時に毎ステップ `Omega`・`t_orb`・`⟨Q_pr⟩`・`a_blow`・`s_min` を再評価する（marsdisk/run.py:1040-1084）。
- ブローアウト時間は `t_blow_step = chi_blow_eff/Omega_step` で毎ステップ更新し、`dt_over_t_blow` として記録される。`fast_blowout_ratio` からサブステップ数を決定し、`io.substep_fast_blowout` と `substep_max_ratio` に従って `dt_sub=dt/n_substeps` を設定。補正式 `_fast_blowout_correction_factor` は「未解像」補正として計算され、`correct_fast_blowout` またはサブステップ有効時にだけ outflux へ乗算される（marsdisk/run.py:1086-1087, 1243-1283, 1371-1377, 1428-1454; marsdisk/run.py:205-222）。
- サブステップごとの処理順は「(1) shielding 用に τ 評価→ κ_eff/Σ_{τ=1} 決定」「(2) supply から prod_rate 取得」「(3) `surface.step_surface` で Σ_surf 更新と outflux/sink_flux 評価」「(4) 必要なら fast_blowout 係数を outflux に乗算」。サブステップ累計後に質量レートや dt_over_t_blow が記録される（marsdisk/run.py:1304-1390, 1428-1454）。
- PSD 由来の drift/床更新は表層ループの前にまとめて実施され、`apply_uniform_size_drift` が Σ_surf を変化させてから遮蔽・表層計算に入る（marsdisk/run.py:1088-1144, 1128-1134）。遮蔽の τ→Σ_{τ=1} クリップは `shielding` ブロック内で決定され、同じサブステップで `surface.step_surface` に渡される。

## 2. 特性時間の所在
- `t_blow` は常に火星放射基準（`radiation_field="mars"` がデフォルトで、`use_solar_rp` を立ててもログに無効化を残すだけ）。`_resolve_blowout` と `radiation.blowout_radius` は火星定数のみを参照するパスで、summary/run_config には「solar_radiation.enabled=False」が明記される（marsdisk/run.py:591-612, 793-812, 1906-1934; marsdisk/physics/radiation.py:1-120）。
- 衝突時間は Wyatt 型 `t_coll = 1/(Omega*tau)` を `surface.wyatt_tcoll_S1` で提供し、`surface.step_surface` で τ>TAU_MIN のときに自動で挿入される（marsdisk/physics/surface.py:23-88, 131-154; marsdisk/run.py:1346-1363）。
- 追加シンク時間は `sinks.total_sink_timescale` が sublimation/gas_drag の最短を返し、`t_sink_total_value` として保持。非昇華成分のみの最短を `t_sink_surface_only` に抽出し、診断テーブルには `t_sink_total_s`/`t_sink_surface_s`/`t_sink_sublimation_s`/`t_sink_gas_drag_s` が出力される（marsdisk/physics/sinks.py:33-123; marsdisk/run.py:1146-1175, 1236-1241, 1680-1695）。
- 昇華レート `ds_dt` は `sizes.eval_ds_dt_sublimation` から取得し、`apply_uniform_size_drift` へ渡すのみで時間スケールには直接変換していない。昇華ベースの τ や t_sublimation を明示的に公開する I/F は現状なし（marsdisk/run.py:1088-1144）。
- ガス抗力時間はオプションで `gas_drag_timescale` により `components["gas_drag"]` として評価され、診断列 `t_sink_gas_drag_s` に書き出される（marsdisk/physics/sinks.py:51-122; marsdisk/run.py:1680-1695）。

## 3. 表層面密度更新とフラックス
- `surface.step_surface` は Σ_surf、prod_rate、dt、Omega を受け取り、Wyatt 衝突時間や追加シンク（`t_sink`）、遮蔽クリップ（`sigma_tau1`）、ブローアウト有効フラグを引数で受ける。暗黙 Euler で `sigma_new = (sigma+dt*prod)/(1+dt*loss)` を求め、`sigma_tau1` があれば上限クリップ。その後 outflux=`sigma_new*Omega`（enable_blowout=false なら 0）、sink_flux=`sigma_new/t_sink`（t_sink 無効なら 0）を返す。負値ガードは τ=1 クリップのみで、下限 0 への明示クリップは無し（marsdisk/physics/surface.py:64-154）。
- 呼び出しはサブステップ単位で遮蔽結果を噛ませた直後に行われ、`tau_for_coll`（Wyatt）、`t_sink_current`（sinks/hydro 選択）、`sigma_tau1_active`（layer が surface_tau_le_1 のときのみ）を渡す。戻り値は fast_blowout 補正を乗算してから質量積分に反映される（marsdisk/run.py:1304-1377）。
- Σ_surf の初期化は `initfields.surf_sigma_init` を通じ、`freeze_sigma` 有効時は参照値固定。Σ_{τ=1} クリップは shielding 処理内で算出され、表層計算とは同じサブステップで適用されるため順序依存はない（marsdisk/run.py:900-1016, 1304-1364）。
- 質量収支ログは各ステップ末尾で `mass_budget` に追記し、許容 0.5% 超過時に `mass_budget_violation` を記録、`--enforce-mass-budget` 時のみループ中断。`mass_budget.csv` には time/initial/remaining/lost/diff/error_percent/tolerance_percent などが保存される（marsdisk/run.py:1752-1795, 1890-1902, 1939-1942; marsdisk/io/writer.py:260-274）。
- 既存の「吹き飛び時間未解像」補正は outflux に直接係数を掛けるだけで Σ_surf を書き戻さないため、表層ゲート導入時は同じ場所（補正乗算直後）で係数連携するのが最小差分となる（marsdisk/run.py:1243-1283, 1371-1377）。

## 4. 設定と I/O
- Pydantic スキーマでは `Numerics` に t_end/dt_init/`eval_per_step`/`orbit_rollup`/`dt_over_t_blow_max` があり時間解像度関連フラグの受け皿になる。`IO` に fast_blowout 補正式とサブステップ制御、`Blowout` に layer/phase トグル、`Shielding`・`Surface` に freeze_sigma/use_tcoll 等があるが「安全スイッチ」相当のブロックは未定義（marsdisk/schema.py:613-744）。
- 時系列出力は `records`（run.parquet）と `diagnostics`（diagnostics.parquet）の2系統で、前者に `dt_over_t_blow`・`fast_blowout_*`・`Sigma_surf` など主系列、後者に `t_sink_*`・`sigma_tau1`・遮蔽Φなど詳細が入る。新カラムを追加する場合は writer の `units`/`definitions` にも追記が必要（marsdisk/run.py:1428-1750; marsdisk/io/writer.py:1-214）。
- `summary.json` には `time_grid`（dt_mode/step/n_steps/t_end）と `dt_over_t_blow_median`、質量収支誤差が既に含まれる。`run_config.json` にも time_grid/physics_controls を格納しているため、設定値の再現用メタデータはここに統合するのが最小変更（marsdisk/run.py:1860-2052; marsdisk/io/writer.py:215-274）。
- 有効半径・温度などの provenance は run_config/summary 双方に出力済み。新しい安全スイッチの既定値を既存挙動互換（完全無効）に設定すれば後方互換を保てる（既存フラグは全てデフォルトが「現行動作」）。

## 5. テストの入口と実行時間目安
- `tests/test_fast_blowout.py` が `_fast_blowout_correction_factor`・補正乗算・サブステップ挙動・診断カラムの整合を確認する。`tests/test_per_step_blowout.py` は eval_per_step と刻み差の影響、質量収支、orbit_rollup を比較する。
- 質量保存は `tests/integration/test_mass_conservation.py`・`tests/test_mass_flux_consistency.py` で `mass_budget.csv` と出力列の整合を検査。ブローアウト面のワビー挙動は `tests/integration/test_surface_outflux_wavy.py` が PSD を評価する。
- これらのテストはいずれも短尺（t_end ≲ 1e-3 年、dt ~1e3-1e4 s）で実行時間は CI レベル。年オーダー（〜2 年）長尺ケースの実行時間や安定性は自動テストに含まれておらず、非回帰確認には既存設定での手動/スモーク実行が必要。

## フック候補（最小差分）
- 第一候補（診断とゲート併設）: `run_zero_d` のサブステップ準備〜集計ブロック（fast_blowout_ratio 算出〜 mass loss 集計）に時間解像度判定と表層ゲートを挿入する。利点: dt/t 系の情報・Σ_surf 更新量・遮蔽結果が同一スコープにあり、`records`/`diagnostics`/`mass_budget` への書き足しが容易。リスク: 1 ステップ内のサブステップで再入するため、係数の適用順を誤ると fast_blowout 補正との二重計算が起き得る。
- 第二候補（関数レベルのガード）: `surface.step_surface` にオプション引数で「ゲート係数」を渡し、Σ_surf 更新・outflux・sink_flux を一括スケールする。利点: 呼び出し側のループ変更を最小化でき、サブステップ数に依存しない。リスク: 既存テストが参照する API シグネチャ変更や、遮蔽クリップ後の挙動が全呼び出しに波及するため後方互換性の検証が必要。
