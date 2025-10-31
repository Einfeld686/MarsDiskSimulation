## caseA_t1
### コマンド
`python -m marsdisk.run --config analysis/agent_tests/configs/caseA_t1.yml`
### 主要ファイル存在確認
- analysis/agent_tests/caseA_t1/series/run.parquet
- analysis/agent_tests/caseA_t1/summary.json
- analysis/agent_tests/caseA_t1/checks/mass_budget.csv
- analysis/agent_tests/caseA_t1/run_config.json
### 検証
| チェック | 結果 |
| --- | --- |
| `run.parquet` に必須列 (`time`,`dt`,`M_out_dot`,`mass_lost_by_blowout`,`mass_lost_by_sinks`) を確認 | OK |
| `mass_lost_by_sinks` 全行 0 | OK |
| `case_status=ok` （β=0.493<0.5=threshold） | OK |
| `s_min_effective=1.0e-6=max(config, blowout)` | OK |
| `mass_budget` 最終 `error_percent=7.6e-15` (≦0.5%) | OK |
### 判定
合格（出力・検証とも想定通り）
### 補足
- `summary.json` の `M_loss=2.09e-08` M_Mars
- 出力先: `analysis/agent_tests/caseA_t1/`

## caseB_t2
### コマンド
`python -m marsdisk.run --config analysis/agent_tests/configs/caseB_t2.yml`
### 主要ファイル存在確認
- analysis/agent_tests/caseB_t2/series/run.parquet
- analysis/agent_tests/caseB_t2/summary.json
- analysis/agent_tests/caseB_t2/checks/mass_budget.csv
- analysis/agent_tests/caseB_t2/run_config.json
### 検証
| チェック | 結果 |
| --- | --- |
| `mass_lost_by_sinks` 累積 = 2.16e-08 (>0) | OK |
| `s_min_components` に `config`,`blowout`,`effective` のみが存在し、`s_min_effective = max(config, blowout)` | OK |
| `M_out_dot + M_sink_dot` と `dM_dt_surface_total` の最大差 0 (≲1e-6) | OK |
| `mass_budget` 最終 `error_percent = 4.6e-15` (≦0.5%) | OK |
### 判定
合格（昇華シンク有効時の増分・サイズ下限反映を確認）
### 補足
- 設定差分: `sinks.T_sub=850 K`（昇華境界を顕在化）
- `summary.json` の `M_loss=2.26e-08` M_Mars（うち sinks=2.16e-08）
- 出力先: `analysis/agent_tests/caseB_t2/`

## caseC_dt_ratio
### コマンド
- `python -m marsdisk.run --config analysis/agent_tests/configs/caseC_inner.yml`
- `python -m marsdisk.run --config analysis/agent_tests/configs/caseC_outer.yml`
### 主要ファイル存在確認
- analysis/agent_tests/caseC_inner/series/run.parquet
- analysis/agent_tests/caseC_inner/summary.json
- analysis/agent_tests/caseC_inner/checks/mass_budget.csv
- analysis/agent_tests/caseC_inner/run_config.json
- analysis/agent_tests/caseC_outer/series/run.parquet
- analysis/agent_tests/caseC_outer/summary.json
- analysis/agent_tests/caseC_outer/checks/mass_budget.csv
- analysis/agent_tests/caseC_outer/run_config.json
### 検証
| Case | `t_blow` 初期 [s] | `dt_over_t_blow` 平均 | fast係数max (`factor`,`ratio`) | mass budget `error_percent` |
| --- | --- | --- | --- | --- |
| inner (r≈2.6 R_M) | 3.998e+03 | 1.58e-01 | 0.0 / 0.0 | 7.81e-15 |
| outer (r≈5.0 R_M) | 1.066e+04 | 5.92e-02 | 0.0 / 0.0 | 7.51e-15 |
- `run.parquet` には `t_blow`, `t_blow_s`, `dt_over_t_blow` が出力され、粗密半径で比が単調 (`inner > outer`)。
- `case_status` が `ok` のため fast blowout 診断列は全て 0.0。
- `mass_lost_by_sinks` は全行 0。
### 判定
合格（ブローアウト時定数と dt の記録・診断列が仕様どおり動作）
### 補足
- 両ケースとも `summary.json` は `case_status="ok"`, `s_min_effective = max(config, blowout)` を維持。
- 出力先: `analysis/agent_tests/caseC_inner/`, `analysis/agent_tests/caseC_outer/`

## caseD_min_evolve
### コマンド
- `python -m marsdisk.run --config analysis/agent_tests/configs/caseD_t1_a.yml`
- `python -m marsdisk.run --config analysis/agent_tests/configs/caseD_t1_b.yml`
### 主要ファイル存在確認
- analysis/agent_tests/caseD_t1_a/series/run.parquet
- analysis/agent_tests/caseD_t1_a/summary.json
- analysis/agent_tests/caseD_t1_a/checks/mass_budget.csv
- analysis/agent_tests/caseD_t1_a/run_config.json
- analysis/agent_tests/caseD_t1_b/series/run.parquet
- analysis/agent_tests/caseD_t1_b/summary.json
- analysis/agent_tests/caseD_t1_b/checks/mass_budget.csv
- analysis/agent_tests/caseD_t1_b/run_config.json
### 検証
| Case | `apply_evolved_min_size` | `s_min_evolved` 初期→最終 [m] | `s_min_effective` 最終 [m] | 単調性 | mass budget `error_percent` |
| --- | --- | --- | --- | --- | --- |
| (a) diagnostics | false | 1.05e-06 → 6.41e-05 | 1.00e-06 | ↗ (nondecreasing) | 7.41e-15 |
| (b) applied     | true  | 1.05e-06 → 6.41e-05 | 1.00e-06 | ↗ (nondecreasing) | 7.41e-15 |
- 両ケースとも `s_min_evolved` カラムが存在し、時間とともに単調増加。
- (a) は診断のみのため `s_min_effective` は設定値 (1.0e-6 m) を維持。
- (b) も PSD 下限は `max(config, blowout)` のまま据え置かれ、`s_min_evolved` のみが昇華 `ds/dt` を追跡する（診断列）。
- `mass_lost_by_sinks` は全行 0、質量収支は許容内。
### 判定
合格（最小粒径進化フックの診断・適用挙動を確認）
### 補足
- `summary.json` (b) の `s_min_components` は `config`,`blowout`,`effective` のみ。
- 出力先: `analysis/agent_tests/caseD_t1_a/`, `analysis/agent_tests/caseD_t1_b/`
