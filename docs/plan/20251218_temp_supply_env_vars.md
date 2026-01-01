# temp_supply_sweep 用環境変数まとめ

> **作成日**: 2025-12-18  
> **対象**: `scripts/research/run_temp_supply_sweep.sh` の実行時に使う環境変数  
> **目的**: どのスイッチを渡せば挙動が変わるかを一望できるようにする

## ベース設定
- `BASE_CONFIG` (既定: `configs/sweep_temp_supply/temp_supply_T4000_eps1.yml`)
- `QSTAR_UNITS` (既定: `ba99_cgs`)
- `T_LIST` / `EPS_LIST` / `TAU_LIST` … 温度・混合効率・初期光学的厚さのスイープ軸
- `BATCH_ROOT` / `OUT_ROOT` … 出力ルート（未指定なら `out/`、外付け SSD があれば `<external_out_root>`）
- `EVAL` … 1 なら各ケース後に評価スクリプトを呼ぶフック（0 でスキップ）

## 供給・遮蔽
- `SUPPLY_MODE` … 供給モード（既定 `const`）
- `SUPPLY_MU_ORBIT10PCT` … 供給スケール（`mu_orbit10pct`）
- `SUPPLY_ORBIT_FRACTION` … `orbit_fraction_at_mu1`
- `EPS_LIST` … epsilon_mix の掛け値（`supply.mixing.epsilon_mix` に代入）
- `TAU_LIST` … `optical_depth.tau0_target` の掃引値
- `SHIELDING_MODE` … 遮蔽モード（既定 `off`）
- `SHIELDING_SIGMA` … `fixed_tau1_sigma`（既定 `auto` を推奨）
- `SHIELDING_AUTO_MAX_MARGIN` … `auto_max` 使用時の余裕率（既定 `0.05`）
- `INIT_SCALE_TO_TAU1` … `init_tau1.scale_to_tau1` の ON/OFF（既定 `true`）
- **fast blowout サブステップ**:
  - `SUBSTEP_FAST_BLOWOUT` … 1 で `io.substep_fast_blowout=true` を付与（surface_ode 用）
  - `SUBSTEP_MAX_RATIO` … `dt/t_blow` 閾値（空ならベース設定のデフォルト 1.0 を使用）

## リザーバ / フィードバック / 温度カップリング
- `SUPPLY_RESERVOIR_M` … 有限リザーバ質量 [M_Mars]（空なら無効）
- `SUPPLY_RESERVOIR_MODE` … `hard_stop` / `taper`
- `SUPPLY_RESERVOIR_TAPER` … taper fraction
- `SUPPLY_FEEDBACK_ENABLED` … τフィードバックの有無（0/1）
- `SUPPLY_FEEDBACK_TARGET`, `SUPPLY_FEEDBACK_GAIN`, `SUPPLY_FEEDBACK_RESPONSE_YR`, `SUPPLY_FEEDBACK_MIN_SCALE`, `SUPPLY_FEEDBACK_MAX_SCALE`, `SUPPLY_FEEDBACK_TAU_FIELD`, `SUPPLY_FEEDBACK_INITIAL`
- `SUPPLY_TEMP_ENABLED` … 温度スケールの有無（0/1）
- `SUPPLY_TEMP_MODE` … `scale` / `table`
- `SUPPLY_TEMP_REF_K`, `SUPPLY_TEMP_EXP`, `SUPPLY_TEMP_SCALE_REF`, `SUPPLY_TEMP_FLOOR`, `SUPPLY_TEMP_CAP`
- `SUPPLY_TEMP_TABLE_PATH`, `SUPPLY_TEMP_TABLE_VALUE_KIND`, `SUPPLY_TEMP_TABLE_COL_T`, `SUPPLY_TEMP_TABLE_COL_VAL`

## 注入レンジと transport/velocity
- `SUPPLY_INJECTION_MODE` … `min_bin` / `powerlaw_bins`
- `SUPPLY_INJECTION_Q` … power-law 指数
- `SUPPLY_INJECTION_SMIN` / `SUPPLY_INJECTION_SMAX` … 注入サイズ範囲（空なら既定）
- `SUPPLY_TRANSPORT_MODE` … `deep_mixing`（既定） / `direct`
- `SUPPLY_TRANSPORT_TMIX_ORBITS` … deep→surf 混合時間 [orbit]（deep_mixing 時必須、既定 `50`）
- `SUPPLY_TRANSPORT_HEADROOM` … headroom gate（既定 `hard`）
- `SUPPLY_DEEP_TMIX_ORBITS` … legacy エイリアス（transport.t_mix_orbits に転送）
- `SUPPLY_VEL_MODE` … `fixed_ei`（既定） / `inherit` / `factor`
- `SUPPLY_VEL_E` / `SUPPLY_VEL_I` … `fixed_ei` 用 e/i（既定 `0.05` / `0.025`）
- `SUPPLY_VEL_FACTOR` … `factor` 用倍率
- `SUPPLY_VEL_BLEND` … ブレンド方法 `rms`（既定） / `linear`
- `SUPPLY_VEL_WEIGHT` … 重み付け `delta_sigma`（既定） / `sigma_ratio`

## ストリーミング・進捗
- `ENABLE_PROGRESS` … 1 で進捗バー ON（非 TTY では強制 OFF）
- `STREAM_MEM_GB` … `io.streaming.memory_limit_gb` 上書き
- `STREAM_STEP_INTERVAL` … `io.streaming.step_flush_interval` 上書き

## 実行中に確認しておきたいポイント
- ログに出る `effective supply`（const×epsilon_mix）と `shielding` 設定が意図通りか
- transport を deep_mixing にした場合、`supply.transport.t_mix_orbits` が必ず正にセットされているか
- velocity を fixed/factor にした場合、`supply.injection.velocity.*` が run_config.json に記録されているか
