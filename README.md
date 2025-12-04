# marsshearingsheet クイックガイド

> **For AI Agents**: 必ず [`analysis/AI_USAGE.md`](analysis/AI_USAGE.md) を読んでから作業してください。UNKNOWN_REF_REQUESTS や DocSync 手順はそちらが唯一の基準です。

## 前提とルール
- 解析対象は **gas-poor** の火星ロッシュ内ダスト円盤。Takeuchi & Lin (2003) は既定で無効（`ALLOW_TL2003=false`）。gas-rich 試験をする場合のみ環境変数で明示的に許可する。
- CLI ドライバは `python -m marsdisk.run --config <yaml>`。追加上書きは `--override path=value` を複数指定する。`--sinks {none,sublimation}` と `--single-process-mode {off,sublimation_only,collisions_only}` も用意。
- ⟨Q_pr⟩ テーブルが必須（例: `data/qpr_table.csv`）。存在しないとエラーになるので最初に確認する。
- 出力ルートは `io.outdir`（YAML側）。既定は `out`。サブフォルダは自動で作成しないので、モードごとに outdir を変えると管理が楽。

## 最短クイックスタート（0D）
1. 任意: `python -m venv .venv && source .venv/bin/activate`
2. 依存導入: `pip install -r requirements.txt`（少なくとも numpy/pandas/pyarrow/ruamel.yaml/pydantic）
3. ベースライン実行（gas-poor, 供給0, ブローアウトON, 昇華OFF, 表層ODE）  
   ```bash
   python -m marsdisk.run --config configs/base.yml
   ```
4. 成功確認  
   - `out/series/run.parquet` があり `mass_lost_by_sinks=0`（昇華無効）。  
   - `out/summary.json` の `case_status` が β判定と一致、`mass_budget_max_error_percent ≤ 0.5`。  
   - `out/checks/mass_budget.csv` の `error_percent` が 0.5% 以内。

## モードピッカー（0D）
「何を指定すれば何が動くか」を最短で把握するための一覧。コマンドは必要に応じて `--override io.outdir=...` で出力先を分けると便利。

| シナリオ | 主要トグル / 設定 | コマンド例 |
| --- | --- | --- |
| ベースライン（gas-poor、昇華OFF） | `sinks.mode=none`（既定）、`surface.collision_solver=surface_ode`、`psd.wavy_strength=0.0`、`supply.const=0` | `python -m marsdisk.run --config configs/base.yml` |
| 昇華 ON（wavy=0.2付き） | `sinks.mode=sublimation`、`enable_sublimation=true`、`psd.wavy_strength=0.2` | `python -m marsdisk.run --config configs/base_sublimation.yml` |
| フル衝突カスケード（Smol） | 多ビン Smoluchowski に切替: `surface.collision_solver=smol` | `python -m marsdisk.run --config configs/base.yml --override surface.collision_solver=smol` |
| “wavy” PSD 感度だけ見たい | wavy を上書き: `psd.wavy_strength>0`（他はベースライン） | `python -m marsdisk.run --config configs/base.yml --override psd.wavy_strength=0.2` |
| 高速ブローアウトをサブステップ解像 | `io.substep_fast_blowout=true`、`io.substep_max_ratio=1.0`（必要なら `io.correct_fast_blowout=true`） | `python -m marsdisk.run --config configs/base.yml --override io.substep_fast_blowout=true --override io.substep_max_ratio=1.0` |
| gas-rich/TL2003 試験（オプトイン） | **環境変数** `ALLOW_TL2003=true` を付け、表層ODEを強制。gas-poor 既定の外なので要注意。 | `ALLOW_TL2003=true python -m marsdisk.run --config configs/base.yml --override surface.collision_solver=surface_ode` |

- 供給を入れたい場合は `--override supply.mode=const --override supply.const.prod_area_rate_kg_m2_s=1e-8` のように追加する。
- 昇華を完全に切りたい場合はどの YAML でも `--sinks none` で上書きできる。

## 出力チェックの定型
- `series/run.parquet`：`prod_subblow_area_rate`, `M_out_dot`, `mass_lost_by_blowout`, `mass_lost_by_sinks`, `dt_over_t_blow`, `fast_blowout_*` を確認。Smol 時は `n_substeps` や `dSigma_dt_*` がカスケード経路の値になる。
- `summary.json`：`case_status`（β>=0.5 なら blowout）、`s_min_components`（config/blowout/effective）、`mass_budget_max_error_percent`（0.5% 以内）、`collision_solver`, `single_process_mode` を見る。
- `checks/mass_budget.csv`：質量収支が 0.5% 以内かを確認し、超えたら `--enforce-mass-budget` で再実行する。
- `run_config.json`：使用した式・定数・トグル・シード・温度ソース・⟨Q_pr⟩/Φテーブルのパスが記録される。再現や差分解析時はここを参照。

## さらに詳しく
- モード別の詳細手順と確認ポイント: `analysis/run-recipes.md`（冒頭のモード早見表を参照）。
- 代表RUNの索引: `analysis/run_catalog.md`（RUN_* ID と config/outdir の対応表）。
- 数式・物理: `analysis/equations.md`。アンカー付きで唯一の式ソース。
