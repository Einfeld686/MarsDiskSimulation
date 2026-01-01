# パラメータスタディ計画（0D 火星ロッシュ内円盤）

目的と背景
----------
- gas-poor 標準（TL2003 無効, `ALLOW_TL2003=false`）の 0D 実行で、先行研究に明示値がない自由度を系統的に掃引する。
- 研究で固まっている定数（β=0.5, Q_D* 係数, ρ=3000 kg/m³ 等）は固定し、シナリオ依存のものだけを振る。
- ベース設定は `configs/base.yml`（analysis 指定の 2 年・40 bin）とし、各スイープは `out/<timestamp>_param_sweep__<sha>/` 配下に `out/<run_id>/run_card.md` を残す。

対象・非対象
------------
- 対象: 供給、PSD 床/波打ち、力学励起、遮蔽ゲート、昇華/ガス/水蒸気逃亡、放射ドライバ、数値安定化トグル。
- 非対象: CODATA 定数、β 閾値、Benz–Asphaug/LS12 Q_D* 係数、Mars 半径域（2.2–2.7 R_M 基本）は固定。

スイープ項目と意図
------------------
1. 外部供給 (`supply.*`): mode={const, powerlaw, table}, `prod_area_rate_kg_m2_s` 10^{-12}–10^{-8}, `mixing.epsilon_mix` 0.05–1.0 で表層/Smol 質量源の感度を見る。
2. PSD と最小径: `psd.alpha` 1.7–1.9, `wavy_strength` 0–0.3, `floor.mode` {fixed, evolve_smin}, `sizes.evolve_min_size`/`dsdt_model` 有効化で s_min 床優先順位の影響を確認。
3. 力学励起・wake: `e0` 0.1–0.7, `i0` 0.01–0.1, `t_damp_orbits` 5–50, `f_wake` 1–3, `kernel_ei_mode` {config, wyatt_eq}, `kernel_H_mode` {ia, fixed(H/a=0.02–0.05)}。
4. 遮蔽・ゲート: `shielding.mode` {psitau, fixed_tau1}, `fixed_tau1_tau` 0.1–5, `radiation.tau_gate.enable`/`tau_max` 0.3–3, `blowout.gate_mode` {none, sublimation_competition, collision_competition} の順序効果。
5. 昇華・ガス/水蒸気シンク: `sinks.mode` {none, sublimation}, `sub_params.mode` {logistic, hkl, hkl_timescale}, HKL A/B/α_evap の±20% バリエーション、`enable_gas_drag` on with `rho_g` 10^{-12}–10^{-9} kg/m³、`hydro_escape.enable` on で `strength` 10^{-6}–10^{-4} s^{-1}（T_ref=2000–2500 K）を試す。
6. 放射ドライバ: `radiation.TM_K` 3000–5000 K とテーブル切替（`mars_temperature_driver` constant/table）、`Q_pr` 明示 0.7–1.3 vs テーブル参照で β・a_blow の感度を見る。
7. 数値設定: `numerics.dt_init` {auto, 1e4, 3e4, 1e5} s、`dt_over_t_blow_max` {0.05, 0.1, 0.3}、`io.correct_fast_blowout`/`substep_fast_blowout` on/off と `substep_max_ratio` 1–5 で IMEX 安定性と質量誤差の余裕を測る。

進め方・メモ
------------
- 各スイープは 1 本ずつ軸を変え、他軸は `configs/base.yml` に固定。セット間の変更は `out/<run_id>/run_card.md` に差分として記録。
- マスバジェット 0.5% を必ず確認し、`out/<run_id>/checks/mass_budget.csv` が閾値越えの場合は再試行またはステップ設定を緩和する。
- TL2003/gas-rich シナリオは対象外。必要時は別プランを起こし、`ALLOW_TL2003=true` を明示した上で扱う。

リスクと緩和
------------
- 計算量増大: supply×PSD×遮蔽の組み合わせ爆発を避け、1 軸ずつ実施。必要なら `io.streaming` を併用。
- 数値不安定（dt/t_blow 大）: `dt_over_t_blow_max`/サブステップを併用し、Wyatt スケールとの整合を tests/integration/test_scalings.py でスポット確認。
- テーブル欠損: Q_pr/Φ/温度テーブルが無い場合は実行前に配置し、なければテーブルを外して analytic フォールバックを明示。

完了判定
--------
- 主要軸（供給、PSD床/波、力学励起、遮蔽/ゲート、昇華/ガス、放射、数値）の最低 1 本ずつについて、範囲を走らせた `out/<run_id>/run_card.md` と `out/<run_id>/summary.json` を `out/<run_id>/` 以下に保存。
- 失敗ケースを含め、使用した設定・ハッシュ・主要メトリクスを `out/<run_id>/run_card.md` に記録（analysis へ詳細を複写しない）。
