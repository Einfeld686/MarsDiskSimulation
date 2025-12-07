# Phase 7 最小診断の拡張

## 目的
2 年スケールの解析で必要な損失経路の可視化を、既存の物理・数値処理を変えずに補足する。後方互換を維持するため、新しい出力は `diagnostics.phase7.enable` を `true` にしたときだけ追加される。

## 追加出力（enable=true のときのみ）
- `out/series/run.parquet` に新規カラムを追加する。`mloss_blowout_rate`（放射圧吹き飛びレート, M_Mars s^-1 with gate/Φ補正後）、`mloss_sink_rate`（昇華/ガス抗力/水素逃走など追加シンクの瞬時レート, M_Mars s^-1）、`mloss_total_rate`（両者の和）、`cum_mloss_blowout` / `cum_mloss_sink` / `cum_mloss_total`（累積損失, M_Mars）、`t_coll`（Wyatt 型 1/(Ωτ) で τ≤1 面を評価）、`ts_ratio=t_blow/t_coll`、`beta_eff`（`beta_at_smin_effective` の別名）、`kappa_eff` / `tau_eff`（遮蔽後の実効値）。ブローアウト時間 `t_blow` と `a_blow` は既存列をそのまま利用。
- `summary.json` に `M_loss_blowout_total`、`M_loss_sink_total`、`M_loss_total`、`max_mloss_rate` と `max_mloss_rate_time`、`median_ts_ratio`、`phase7_diagnostics_version` を追加。
- `orbit_rollup.csv` に平均/ピークレート（`mloss_blowout_rate_mean/peak`, `mloss_sink_rate_mean/peak`, `mloss_total_rate_mean/peak`）と `ts_ratio_median` を追加。平均は既存の per-orbit 質量集計から、ピーク/中央値は区間にかかるステップのレート系列から取得する。
- `checks/mass_budget.csv` に `delta_mloss_vs_channels`（総損失と blowout+sink の相対差 [%]）を追加。許容誤差 0.5% を維持。

## 互換性とフラグ
- デフォルトは `diagnostics.phase7.enable=false` で、既存の I/O には一切カラムやキーが増えない。
- `schema_version` の既定値は `phase7-minimal-v1`。summary に同じ値を `_version` として記録し、後段の処理系で判別できるようにする。
- 追加カラムは既存の実効値のみを再利用し、再計算や新しい物理式は導入しない（遮蔽/ゲート後の outflux、t_coll, kappa_eff, tau_eff などその場の値を記録）。

## 確認ポイント
- `mloss_total_rate ≈ mloss_blowout_rate + mloss_sink_rate`、`cum_mloss_total ≈ cum_mloss_blowout + cum_mloss_sink`（許容は質量収支と同一）。
- フラグ無効時に従来のファイル構造・ハッシュが変わらないこと。
- `max_mloss_rate_time` がシリーズの時刻軸（秒）と整合すること、`ts_ratio_median` が NaN ではなく有限値を返す条件（τ>TAU_MIN）で埋まること。

## 設定例（YAML断片）
```yaml
diagnostics:
  phase7:
    enable: true
    schema_version: phase7-minimal-v1
```

## シングルプロセスシナリオ（Phase7 追加要件）
### 目的
内側ディスクの 2 年程度の解析窓で、昇華のみ・衝突のみの極端ケースを明示的に比較できるようにする。物理式は既存のまま、モード選択と可視化だけを強化する。

### シナリオ別ゲート（内側・火星放射限定）

| シナリオ | 衝突/PSD | ブローアウト | 昇華/ガス抗力 | 太陽放射 | 典型用途 |
| --- | --- | --- | --- | --- | --- |
| sublimation_only | OFF | OFF | ON | OFF | 昇華のみで質量損失を評価 |
| collisions_only | ON | ON | OFF | OFF | 衝突＋放射圧だけの損失を評価 |
| combined (default) | ON | ON | ON | OFF | 従来の複合挙動を維持 |

`physics_mode`（CLI/Config 経由）は上記 3 値に正規化され、解決結果は `primary_scenario` に保存される。`collisions_active`/`blowout_active` は `primary_scenario` が `sublimation_only` 以外のときに有効、`sinks_active` は `physics_mode` が `collisions_only` でないかつ `sinks.mode!="none"` のときに有効。

### 設定キーと例

- 単一過程指定: `physics_mode: sublimation_only` / `collisions_only` / `default`（既定で combined）。
- ブローアウトは `blowout.enabled=true` かつ `sinks.rp_blowout.enable=true` かつ `radiation.use_mars_rp=true` かつ `collisions_active=true` のときのみ有効。太陽放射は常に無効（gas-poor 内側前提）。
- 昇華/ガス抗力シンクは `sinks.mode!="none"` かつ `physics_mode!="collisions_only"` のときに残り、`collisions_only` では `ds/dt` と追加シンクの両方が停止する。

```yaml
# 昇華のみ
physics_mode: sublimation_only
sinks:
  mode: sublimation

# 衝突のみ
physics_mode: collisions_only
sinks:
  mode: sublimation  # 設定は残っても無効化される

# 既定（併用）
physics_mode: default
```

### 出力での可視化

- summary.json に `primary_scenario` と `process_overview` ブロックを追加。`collisions_active` / `sinks_active` / `sublimation_active` / `blowout_active` の真偽と、入力元（`primary_process_cfg`・`physics_mode_source`）を記録する。
- run_config.json の `process_controls` と `process_overview` に同じ解決結果を保存し、`blowout_active` や `sinks_mode` を実行時の値で追跡する。
- `diagnostics` / `mass_budget` の列構造は従来のまま。モードに応じてブローアウト系カラムが 0 になるか、シンク系カラムが 0 になるかでゲート状態を確認できる。

### 制約

- 対象は内側ディスク・火星放射のみ（`scope.region` が inner）。太陽放射は常に無効化される。
- 解析窓は数年スパンを想定し、Phase7 では衝突と昇華の相互作用を新規に導入しない。
- 複合モード（combined）は後方互換に合わせ、既存の相互作用・数値仕様を変えない。
