# run_temp_supply_sweep.sh 現行設定まとめ（外部向け）

> **作成日**: 2025-12-13  
> **対象**: `scripts/research/run_temp_supply_sweep.sh` の既定挙動とスイープ設定  
> **目的**: スクリプトを知らない人でも実行条件・出力・トグルを追えるようにする

## 役割と基本フロー
- 0D 円盤で温度・混合効率・初期光学的厚さを掃引し、各ケースを `python -m marsdisk.run` で 2 年間回すバッチランナー。base config は `configs/sweep_temp_supply/temp_supply_T4000_eps1.yml`。
- 実行前に `.venv` が無ければ作成し、`requirements.txt` をインストール。完了後は外付け SSD（存在し書込可なら `<external_out_root>/<run_id>/...`）を優先し、なければ `out/<run_id>/...` へ保存。
- 出力ルートは `OUT_ROOT`（未設定なら上記ルール）配下に `temp_supply_sweep/<YYYYMMDD-HHMMSS>__<gitsha>__seed<BATCH_SEED>/` を作成。各ケースは `T${T}_eps${EPS_TITLE}_tau${TAU_TITLE}` ディレクトリにまとまり、`out/<run_id>/series/`, `out/<run_id>/checks/`, `out/<run_id>/plots/`, `out/<run_id>/summary.json`, `out/<run_id>/run_config.json` を生成する。
- 各 run 後に quick-look プロット（`plots/overview.png`, `plots/supply_surface.png`）を自動生成。`EVAL=1`（デフォルト）なら `scripts/research/evaluate_tau_supply.py` で τ・供給維持の簡易評価を行い、`out/<run_id>/checks/tau_supply_eval.json` に記録する。

## スイープ軸（固定グリッド）
- 温度 `T_LIST`: 4000 / 3000 K（高温順に実行）。各ケースで `radiation.TM_K` と `data/mars_temperature_T${T}p0K.csv` を適用。
- 混合効率 `EPS_LIST`: 1.0 / 0.5 / 0.1 → `supply.mixing.epsilon_mix` に代入（実効供給は const×epsilon_mix をログ表示）。
- 初期光学的厚さ `TAU_LIST`: 1.0 / 0.5 → `optical_depth.tau0_target` に代入。
- 出力ディレクトリは上記 3 軸の直積で 12 ケース作成。

## ベース config（要点）
- 幾何: 0D、`r_in=1.0 R_M`, `r_out=2.7 R_M`、`n_bins=40`、`s_min=1e-7 m`, `s_max=3 m`。
- 初期質量: `mass_total=1e-5 M_Mars`、melt ログ正規混合（細粒率 0.25、`s_fine=1e-4 m`、`s_meter=1.5 m`）。
- 衝突・PSD: `collision_solver=smol`, `e0=0.5`, `i0=0.05`, `wavy_strength=0`。`chi_blow=auto`、`blowout.layer=surface_tau_le_1`。
- 供給: `supply.mode=const`、`const.mu_orbit10pct=1.0`、`orbit_fraction_at_mu1=0.05`、`headroom_policy=clip`。`optical_depth.tau0_target` で初期 Σ を定義し、`init_tau1.scale_to_tau1` は optical_depth と排他のため使わない。
- 遮蔽: `shielding.mode=off`（Φ=1）を既定とし、テーブルは使わない。
- 放射: `use_mars_rp=true`, `use_solar_rp=false`。`qpr_table_path` は既定で `configs/overrides/material_forsterite.override` を読み、`data/qpr_planck_forsterite_mie.csv` を参照。
- シンク: `sinks.mode=sublimation`, `sublimation_location=smol`, `mass_conserving=true`（昇華で a_blow を跨ぐ分はブローアウト側に合算）。
- 数値: `t_end_years=2`, `dt_init=2 s`, `dt_over_t_blow_max=0.1`, streaming snappy 有効（20 GB リミット, flush 10000 step）。

## スクリプトが毎回付与する override（デフォルト値）
- 材料: `EXTRA_OVERRIDES_FILE` 未指定時は `configs/overrides/material_forsterite.override` を読み込み、ρ/Q_pr/HKL/Q_D* をフォルステライトに差し替える。
- 時間刻み: `numerics.dt_init=20` に引き上げ。
- 出力: `io.outdir=<ケースごとの OUTDIR>`（`RUN_TS`/`GIT_SHA`/`BATCH_SEED` で一意化）。
- 乱数: `dynamics.rng_seed=<ケースごとに secrets.randbelow>`。
- 温度: `radiation.TM_K=<T>`、`radiation.mars_temperature_driver.table.path=data/mars_temperature_T${T}p0K.csv`。
- 衝突強度単位: `qstar.coeff_units=${QSTAR_UNITS}`（既定 `ba99_cgs`）。
- 供給: `supply.enabled=true`、`supply.mode=${SUPPLY_MODE}`（既定 `const`）、`supply.const.mu_orbit10pct=${SUPPLY_MU_ORBIT10PCT}`、`supply.const.orbit_fraction_at_mu1=${SUPPLY_ORBIT_FRACTION}`、`supply.mixing.epsilon_mix=${EPS}`、`supply.headroom_policy=${SUPPLY_HEADROOM_POLICY}`（既定 clip）。
- 初期 τ: `optical_depth.tau0_target=${TAU}` をケースごとに上書き。
- 遮蔽: `shielding.mode=${SHIELDING_MODE}`（既定 off）。`SHIELDING_MODE=fixed_tau1` のときは `shielding.fixed_tau1_sigma=${SHIELDING_SIGMA}`（既定 auto/auto_max 可）、`shielding.auto_max_margin=${SHIELDING_AUTO_MAX_MARGIN}` を付与。
- 高速ブローアウト補正: `SUBSTEP_FAST_BLOWOUT=1` の場合のみ `io.substep_fast_blowout=true`、`SUBSTEP_MAX_RATIO` が空でなければ `io.substep_max_ratio` を上書き（既定は base config の 1.0）。
- ストリーミング: `STREAM_MEM_GB` / `STREAM_STEP_INTERVAL` を指定した場合、`io.streaming.memory_limit_gb` / `io.streaming.step_flush_interval` を追加。

## オプション環境変数（既定は全て無効）
- **リザーバ**: `SUPPLY_RESERVOIR_M`（質量 [M_Mars] を指定すると有効）、`SUPPLY_RESERVOIR_MODE`=`hard_stop|taper`、`SUPPLY_RESERVOIR_TAPER`（既定 0.05）。
- **τ フィードバック**: `SUPPLY_FEEDBACK_ENABLED`=1 で有効化。`target_tau`（既定 1.0）、`gain`（1.0）、`response_time_years`（0.5）、`min/max_scale`（0/10）、`tau_field`（tau_los）、`initial_scale`（1.0）を override。
- **温度スケール**: `SUPPLY_TEMP_ENABLED`=1 で `supply.temperature.*` を一括設定（mode=scale/table、`reference_K`=1800、`exponent`=1、`floor`=0、`cap`=10 など）。表形式の場合は `SUPPLY_TEMP_TABLE_PATH` と列名を渡す。
- **注入レンジ/速度**: `SUPPLY_INJECTION_MODE`（min_bin|powerlaw_bins, 既定 min_bin）、`SUPPLY_INJECTION_Q`（3.5）、`SUPPLY_INJECTION_SMIN/SMAX`、`SUPPLY_INJECTION_VEL_*`（mode=fixed_ei, e=0.05, i=0.025, blend=rms, weight=delta_sigma）。  
  transport 系は `SUPPLY_TRANSPORT_MODE`（既定 deep_mixing）、`SUPPLY_TRANSPORT_TMIX_ORBITS`（既定 50）、`SUPPLY_TRANSPORT_HEADROOM`（soft/hard, 既定 soft）、legacy `SUPPLY_DEEP_TMIX_ORBITS` も t_mix に転送。
- **進捗表示**: `ENABLE_PROGRESS`（TTY で 1 のときのみ進捗バー ON、非 TTY は強制 OFF）。
- **評価の有無**: `EVAL=0` で `evaluate_tau_supply.py` 呼び出しをスキップ。

## ポストプロセス・ログのポイント
- プロットは `out/<run_id>/series/run.parquet` が無い場合スキップし、欠損列があっても NA で埋めて生成する安全策が入っている。
- `out/<run_id>/summary.json` から `M_loss`、`mass_budget_max_error_percent`、`effective_prod_rate_kg_m2_s`、`supply_clip_time_fraction` などを拾ってグラフタイトルに出力。
- `SHIELDING_SIGMA=auto_max` 指定時はデバッグ専用である旨を警告。`optical_depth.tau0_target` が小さすぎると headroom が不足し、供給クリップが増える可能性をログ。
- バッチ全体のシード `BATCH_SEED` と各 run の `dynamics.rng_seed` は別管理。ベース設定に対する上書き内容は各 run の `out/<run_id>/run_config.json` に残るため、再解析時はこれを参照すれば足りる。
