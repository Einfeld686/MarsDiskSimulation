# 0D スモークテストマトリクス

> **作成日**: 2026-01-02  
> **ステータス**: 運用中  
> **対象**: 0D（短時間）スモーク

## 目的

- CLI (`python -m marsdisk.run`) が短時間で完走することを確認する
- `summary.json` / `series/run.parquet` / `checks/mass_budget.csv` が揃うことを確認する
- 主要な損失経路（衝突・ブローアウト・昇華）の切り替えが崩れていないことを確認する

## 共通ルール

- CI/pytest など軽量系は `FORCE_STREAMING_OFF=1` または `IO_STREAMING=off` を先に設定する
- 既定の短時間設定: `numerics.t_end_years=0.0001` / `numerics.dt_init=1000`
- 出力先は `out/<run_id>/smoke/<case_id>` に分離する

## コマンドテンプレ

```bash
FORCE_STREAMING_OFF=1 python -m marsdisk.run --config <config> \
  --override numerics.t_end_years=0.0001 numerics.dt_init=1000 \
  --override io.outdir=out/<run_id>/smoke/<case_id> io.streaming.enable=false \
  --quiet
```

## コア行列（CI/日次の最小セット）

| case_id | config | 追加override | 重点 | 最低限の確認 |
| --- | --- | --- | --- | --- |
| collisions_only | `configs/innerdisk_collisions_only.yml` | なし | ブローアウトのみ（昇華/ガス抗力なし） | `out/<run_id>/smoke/collisions_only/summary.json` と `out/<run_id>/smoke/collisions_only/series/run.parquet` と `out/<run_id>/smoke/collisions_only/checks/mass_budget.csv` が生成 |
| sublimation_only | `configs/innerdisk_sublimation_only.yml` | なし | 昇華のみ（ブローアウト無効） | `out/<run_id>/smoke/sublimation_only/summary.json` と `out/<run_id>/smoke/sublimation_only/series/run.parquet` と `out/<run_id>/smoke/sublimation_only/checks/mass_budget.csv` が生成 |
| fiducial_combined | `configs/innerdisk_fiducial.yml` | なし | 衝突 + ブローアウト + 昇華 + 相分岐 | `out/<run_id>/smoke/fiducial_combined/summary.json` と `out/<run_id>/smoke/fiducial_combined/series/run.parquet` と `out/<run_id>/smoke/fiducial_combined/checks/mass_budget.csv` が生成 |
| base_sublimation | `configs/base_sublimation.yml` | なし | 0D の既定構成（昇華ON） | `out/<run_id>/smoke/base_sublimation/summary.json` と `out/<run_id>/smoke/base_sublimation/series/run.parquet` と `out/<run_id>/smoke/base_sublimation/checks/mass_budget.csv` が生成 |

## 最低限の合格基準（全ケース共通）

- `out/<run_id>/smoke/<case_id>/checks/mass_budget.csv` の `error_percent` が 0.5% 以内
- `out/<run_id>/smoke/<case_id>/summary.json` が生成され、`M_loss` と `case_status` が含まれる
- `out/<run_id>/smoke/<case_id>/series/run.parquet` が生成され、`time`/`dt`/`M_out_dot` を含む

## 補足（任意の拡張）

- 旧経路の動作確認は `ALLOW_TL2003=true` を明示した上で実施し、出力は `out/<run_id>/smoke/legacy_surface_ode/...` に分離する  
  - `ALLOW_TL2003=true FORCE_STREAMING_OFF=1 python -m marsdisk.run --config configs/base_sublimation.yml --override surface.collision_solver=surface_ode io.outdir=out/<run_id>/smoke/legacy_surface_ode numerics.t_end_years=0.0001 numerics.dt_init=1000 io.streaming.enable=false --quiet`
