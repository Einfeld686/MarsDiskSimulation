# 拡張診断（extended_diagnostics）Gate 拡張

## 目的
火星放射圧ブローアウトの抑制要因（時間スケール競合と τ ゲート）を、既存フローを変えずに定量化する。`diagnostics.extended_diagnostics.enable=true` のときのみ追加出力し、既存 I/O 互換を維持する。

## 追加出力（enable=true のときのみ）
- summary.json: `median_gate_factor`（ゲート係数の中央値）、`tau_gate_blocked_time_fraction`（τゲート遮断が有効だった時間割合）、`extended_diagnostics_version` を付与。
- orbit_rollup.csv: `gate_factor_median` を各軌道区間のブローアウトゲート係数中央値として追加（区間内ステップの中央値が NaN のときは全体中央値で代入）。
- 既存の拡張診断カラム（`mloss_*`、`ts_ratio`、`beta_eff`、`kappa_eff`、`tau_eff`）や summary/rollup 拡張は phase7_minimal_diagnostics に準拠。

## 互換・動作
- フラグOFF時は一切の新規キー/列を書かない。既存ハッシュと互換。
- ゲート係数は `_compute_gate_factor(t_blow, t_solid)` の既存実装そのまま（collision/sublimation 競合）。`tau_gate_blocked_time_fraction` は `tau_gate_blocked` が真だったステップの `dt` 積算を全積算時間で割ったもの。

## テスト観点
- 拡張診断トグル: ONで新キーが出力され、OFFで出ないこと。
- τゲート遮断: `tau_gate_blocked_time_fraction>0` かつ blowout レートが 0 近傍になること。
- 衝突/昇華競合: `blowout.gate_mode` が collision/sublimation の簡易ケースで `median_gate_factor<1` を確認（質量収支は既存許容の 0.5% 以内）。

## YAML 例
```yaml
diagnostics:
  extended_diagnostics:
    enable: true
blowout:
  gate_mode: collision_competition
radiation:
  tau_gate:
    enable: true
    tau_max: 1.0e-6
```

## 既存 phase7_minimal との差分
- summary: ゲート関連の中央値・遮断時間割合を追記。
- orbit_rollup: 区間中のゲート係数中央値 `gate_factor_median` を追加。
- 本拡張は新式を導入せず、既存ゲート/τ判定のログ化のみ。
