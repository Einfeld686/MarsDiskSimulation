# scripts ディレクトリ

## 位置付けと意図（AGENTS.md に基づく）
- `AGENTS.md` は、火星ロッシュ限界内の 0D カップリング（C1–C4, R1–R3, S0–S1）を 2 年間積分し、$\dot{M}_{\rm out}(t)$ と $M_{\rm loss}$ を定量化することを必須要件として定めています。
- 本ディレクトリは、その要件を満たすための公式 CLI／自動化スクリプト群をまとめた場所であり、すべて `python -m marsdisk.run` もしくは `marsdisk` 内部 API を呼び出して **AGENTS で規定された 0D モデルを再利用**します。
- `tools/` 以下の旧ラッパーは互換目的で残置されていますが、順次削除予定です。以降の運用・機能拡張は本 `scripts/` 配下を参照してください。

## ファイル別サマリー
| ファイル | 主目的 | 主な入出力・備考 |
| --- | --- | --- |
| `__init__.py` | 空モジュール | `scripts` を Python パッケージとして認識させるためのプレースホルダーです。 |
| `analysis_sync.py` | DocSyncAgent の CLI（引数転送対応） | `python scripts/analysis_sync.py --all --write` などで `marsdisk.ops.doc_sync_agent.main` を起動し、analysis/ 以下の仕様同期を実行します。 |
| `analyze_radius_trend.py` | 半径スイープ診断ランナー | 与えた半径リストごとに `marsdisk.run` を呼び、`series/run.parquet` と `summary.json` から Ω, $t_{\rm blow}$, $\dot{M}_{\rm out}$ などを抽出して `radius_sweep_metrics.csv` を生成します。 |
| `collect_series.py` | 時系列 Parquet の一括収集 | `*/run_id/series/run.parquet` を走査して 1 つの Parquet に結合し、ケース ID と出力先を付与します。 |
| `doc_sync_agent.py` | DocSyncAgent 互換ラッパー | 引数なしで `marsdisk.ops.doc_sync_agent.main()` を呼び出します。旧コマンド (`python scripts/doc_sync_agent.py`) 互換用途です。 |
| `make_qpr_table.py` | Planck 平均 $\langle Q_{\rm pr}\rangle$ テーブル生成 | `marsdisk.ops.make_qpr_table.main` を起動し、CSV/NPZ の Q_pr テーブルを作成します。 |
| `plot_axis_r_sweep.py` | AXIS_r_sweep 結果の可視化 | `analysis/agent_runs/AXIS_r_sweep/summary.csv` を読み、温度ごとの $M_{\rm loss}$ vs r/R_M を PNG として保存します。 |
| `plot_heatmaps.py` | パラメータマップの描画 | `results/map*.csv` をピボットしてヒートマップ化し、β 系指標や失敗セルのハッチングも表示します。 |
| `plot_tau_timescales.py` | τ–timescale 図の生成 | `series/run.parquet` から `t_sub`/`t_coll`/`t_blow` を計算し、τとの散布図を `figures/` へ保存します。 |
| `plot_tau_timescales.cmd` | τ–timescale 図の Windows 実行 | `.venv` セットアップ後に `plot_tau_timescales.py` を呼び、CPU/メモリ検出ログを出力します。 |
| `run_axis_r_sweep.py` | r–T–M グリッドの大量実行 | `analysis/agent_runs/AXIS_r_sweep` 以下に YAML／結果ディレクトリを生成し、`marsdisk.run` をケースごとに起動。`summary.json` 等を検証・集計します。 |
| `run_inner_disk_suite.py` | Φ(1)×T_M スイート | Φ(1)={0.20,0.37,0.60} と温度掃引を組み合わせて 1 年積分し、`series/*.parquet`・PSD フレーム・GIF・`orbit_rollup.csv` を生成します。 |
| `sweep_beta_map.py` | β(r/R_M, T_M, t) 立方体生成 | `marsdisk.analysis.sample_beta_over_orbit` を用いて 1 軌道分の β 時系列をサンプリングし、Zarr 立方体＋ `map_spec.json` を出力します。 |
| `sweep_heatmaps.py` | 汎用 2D パラメータスイープ | マップ定義とバリアント指定を展開し、並列で `marsdisk.run` を実行。`results/map*.csv` と検証 JSON を保存します。 |
| `sweep_mass_loss_map.py` | 1 軌道あたり質量損失マップ（高速版） | `marsdisk.analysis.massloss_sampler.sample_mass_loss_one_orbit` を呼び、`map_massloss.csv` とメタデータ `logs/spec.json` を作成します。必要に応じて `sinks.mode='none'` 比較も併記。 |
| `sweep_massloss_heatmap_gif.py` | Φ テーブル別の質量損失ヒートマップ＋GIF | Φ テーブルごとに 1 年積分を行い、`orbit_rollup.csv` から per-orbit 指標を抽出。PNG ヒートマップとアニメーション GIF を `out/phi*/` に保存します。 |
| `sweep_massloss_map.py` | `_configs/05_massloss_base.yml` ベースの Map-1 ドライバ | (r/T) グリッドの YAML を生成して `marsdisk.run` を実行し、`map1/` 以下に `summary.json`・`series/run.parquet`・質量収支ログと検証結果をまとめます。 |

## 運用メモ
- すべてのスクリプトは `python scripts/<name>.py [options]` で単独起動できます。CI・エージェントから呼び出す場合もこのパスを基準にしてください。
- 分析用ユーティリティが必要になった場合は、`tools/` ではなく本ディレクトリに追加し、本 README の表へ追記する運用に統一します。
- 既存の `tools/` には互換ラッパーが一時的に残っていますが、将来的に削除されても本 README に列挙した機能は維持される想定です。
- 新しいシミュレーションランナーを Windows 向けに用意する場合は、本ディレクトリ直下に `.cmd` 形式で追加します。`run_sublim_windows.cmd` を雛形に、(1) `.venv` が無ければ作成し `requirements.txt` から依存を取得、(2) `OUTDIR` を標準の保存規則（例: `out/<YYYYMMDD-HHMM>_<short-title>__<shortsha>__seed<n>/`）に従って設定し、必要なら `if not exist "%OUTDIR%" mkdir "%OUTDIR%"` で生成、(3) `python -m marsdisk.run` を既存スクリプトと同じフローで起動して結果を書き込む、を必須手順とします。追加した `.cmd` はこの README の表にも用途を一行で追記してください。
