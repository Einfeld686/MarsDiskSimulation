# Phase 6 運用メモ（表層ゲート）

- 目的: 内側円盤で時間解像度が粗いときに、火星放射圧による表層 blowout を安全側に抑制する。火星放射のみを対象とし、太陽放射は無効化されたまま。
- 設定: `blowout.gate_mode` を追加（schema.Blowout）。`none`（デフォルト・互換）、`sublimation_competition`（t_solid=a_blow/|ds/dt|）、`collision_competition`（t_solid=t_coll=1/(Ωτ)）から選択。
- ゲート係数: `f_gate = t_solid/(t_solid + t_blow)` を 0–1 にクリップ。異常値（NaN/0/負）や blowout 無効時は 1.0。
- 適用箇所: `surface.step_surface` で得た outflux に `_fast_blowout_correction_factor` を掛けた直後に `f_gate` を乗算。Σ_surf の更新式や sink_flux は変更しない。
- 出力: `series/` と `diagnostics/` に `t_solid_s`, `blowout_gate_factor` を追加。`summary.json` に gate_mode と t_solid/gate_factor の min/median/max を出力。`run_config.json` の physics_controls に gate_mode を残す。
- 留意点: デフォルト `none` では完全互換。ゲートは数値安全弁であり、時間グリッド設計やサブステップを置き換えるものではない。Σ_surf 進化は従来通りなので、ゲート有効時も解像度不足が根本原因なら時間刻みを見直す。`collision_competition` は `surface.use_tcoll=True`（Wyatt 衝突項を使う条件）でのみ有効にすることを推奨。
