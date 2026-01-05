# scripts ディレクトリ

## 位置付けと意図（AGENTS.md に基づく）
- `AGENTS.md` は、火星ロッシュ限界内の 0D カップリング（C1–C4, R1–R3, S0–S1）を 2 年間積分し、$\dot{M}_{\rm out}(t)$ と $M_{\rm loss}$ を定量化することを必須要件として定めています。
- 本ディレクトリは、その要件を満たすための公式 CLI／自動化スクリプト群をまとめた場所であり、すべて `python -m marsdisk.run` もしくは `marsdisk` 内部 API を呼び出して **AGENTS で規定された 0D モデルを再利用**します。
- `tools/` 以下の旧ラッパーは互換目的で残置されていますが、順次削除予定です。以降の運用・機能拡張は本 `scripts/` 配下を参照してください。

## runsets（OS 別の実行ラッパ）
- `scripts/runsets/<os>/run_one.{sh,cmd}`: 単発実行（1D 既定、0D は `--0d` で明示）
- `scripts/runsets/<os>/run_sweep.{sh,cmd}`: パラメータスタディ（1D 既定）
- `scripts/runsets/common/base.yml`: `configs/base.yml` と同期（runsets の共通コア）
- `scripts/runsets/<os>/overrides.txt`: I/O・数値設定のみ（物理設定は base/study に固定）
- `scripts/runsets/common/hooks/*`: plot/eval/preflight の共通ラッパ
- `scripts/runsets/<os>/legacy/*`: 旧来の OS 依存ランナー（互換目的で残置）
- chunk 出力の整合確認は `scripts/runsets/common/hooks/preflight_streaming.py`、merge は `tools/merge_streaming_chunks.py` を使用

例:
```
scripts/runsets/mac/run_sweep.sh --study scripts/runsets/common/study_temp_supply.yml
scripts/runsets/mac/run_one.sh --t 4000 --eps 1.0 --tau 1.0
```

## 役割別ディレクトリ
- `scripts/admin/`: DocSync/テーブル生成/収集ユーティリティ
- `scripts/debug/`: 実装検証・診断系
- `scripts/plots/`: 可視化（Windows 用 `.cmd` は `scripts/plots/windows/`）
- `scripts/runs/`: 大量実行・スイート系ランナー
- `scripts/sweeps/`: パラメータスイープ/マップ生成
- `scripts/research/`: 研究用の共通ランナー/評価スクリプト（runsets から呼び出し）

## ファイル別サマリー
| ファイル | 主目的 | 主な入出力・備考 |
| --- | --- | --- |
| `scripts/__init__.py` | 空モジュール | `scripts` を Python パッケージとして認識させるためのプレースホルダーです。 |
| `scripts/admin/analysis_sync.py` | DocSyncAgent の CLI（引数転送対応） | `python scripts/admin/analysis_sync.py --all --write` などで `marsdisk.ops.doc_sync_agent.main` を起動します。 |
| `scripts/admin/doc_sync_agent.py` | DocSyncAgent 互換ラッパー | 引数なしで `marsdisk.ops.doc_sync_agent.main()` を呼び出します。旧コマンド互換用途です。 |
| `scripts/admin/make_qpr_table.py` | Planck 平均 $\langle Q_{\rm pr}\rangle$ テーブル生成 | `marsdisk.ops.make_qpr_table.main` を起動し、CSV/NPZ の Q_pr テーブルを作成します。 |
| `scripts/admin/analyze_radius_trend.py` | 半径スイープ診断ランナー | `series/run.parquet` と `summary.json` から Ω, $t_{\rm blow}$, $\dot{M}_{\rm out}$ などを抽出して `radius_sweep_metrics.csv` を生成します。 |
| `scripts/admin/collect_series.py` | 時系列 Parquet の一括収集 | `*/run_id/series/run.parquet` を走査して 1 つの Parquet に結合します。 |
| `scripts/plots/plot_axis_r_sweep.py` | AXIS_r_sweep 結果の可視化 | `analysis/agent_runs/AXIS_r_sweep/summary.csv` を読み、温度ごとの $M_{\rm loss}$ vs r/R_M を PNG として保存します。 |
| `scripts/plots/plot_from_runs.py` | 図生成の簡易ユーティリティ | beta/mass_budget/PSD などの定型図を生成します。 |
| `scripts/plots/plot_heatmaps.py` | パラメータマップの描画 | `results/map*.csv` をピボットしてヒートマップ化し、β 系指標や失敗セルのハッチングも表示します。 |
| `scripts/plots/plot_qpr_planck_sio2.py` | Q_pr 可視化 | テーブルを読み込み、温度ごとの曲線を描画します。 |
| `scripts/plots/plot_sblow_curve.py` | blow-out 曲線の描画 | 温度依存の $a_{\\rm blow}$ を可視化します。 |
| `scripts/plots/plot_smol_mass_error.py` | 質量保存の可視化 | `mass_budget.csv` を読み、誤差推移をプロットします。 |
| `scripts/plots/plot_tau_reference_mismatch.py` | τ 参照系の比較 | LOS 参照と指定テーブルの差分をヒートマップ化します。 |
| `scripts/plots/plot_tau_timescales.py` | τ–timescale 図の生成 | `series/run.parquet` から `t_sub`/`t_coll`/`t_blow` を計算し、τとの散布図を保存します。 |
| `scripts/plots/windows/plot_tau_timescales.cmd` | τ–timescale 図の Windows 実行 | `.venv` セットアップ後に `plot_tau_timescales.py` を呼びます。 |
| `scripts/tests/run_cell_parallel_consistency.cmd` | 1Dセル並列のWindowsテスト実行 | `.venv` を作成し、`pytest` で `test_cell_parallel_on_off_consistency` を実行します。 |
| `scripts/tests/run_cell_parallel_speed_check.sh` | 1Dセル並列の速度比較（bash） | `.venv` を使って `cell_parallel_speed_check.py` を実行します（Windowsのみ。非Windowsで試す場合は `--force-non-windows`）。 |
| `scripts/tests/run_sweep_parallel_speed_check.sh` | スイープ並列の速度比較（bash） | `.venv` を使って `sweep_parallel_speed_check.py` を実行します。 |
| `scripts/tests/run_sweep_parallel_smoke_check.sh` | スイープ並列の構造スモーク（bash） | `.venv` を使って `sweep_parallel_smoke_check.py` を実行し、出力整合を検証します。 |
| `scripts/tests/run_temp_supply_parallel_smoke.sh` | temp_supply 並列スモーク（bash） | `.venv` を使って `temp_supply_parallel_smoke.py` を実行します。 |
| `scripts/tests/run_overparallel_benchmark.cmd` | 過剰並列の簡易ベンチ（Windows） | `.venv` を作成し、並列数を振って短時間の1D実行を計測し、各runに `perf.json` と `perf_summary.json` を残します。 |
| `scripts/tests/check_run_sweep_cpu_bound.py` | run_sweep のCPU負荷/スレッド予算チェック | dry-run で並列設定を取得し、任意で短縮スイープを実行してCPU使用率を評価します。 |
| `scripts/tests/sweep_vs_cell_parallel_speed_check.py` | スイープ並列 vs セル並列の速度比較 | run_sweep.cmd を2回実行し、wall time を比較して `speed_check_summary.json` を出力します（Windows専用）。 |
| `scripts/tests/numba_on_off_benchmark.py` | Numba on/off の簡易ベンチ | 0D の短時間実行を 2 回行い、`bench_summary.json` に速度比を記録します。 |
| `scripts/plots/render_figures_from_tasks.py` | 図タスクの一括生成 | 解析タスク定義から `plot_from_runs.py` を呼び出して図を生成します。 |
| `scripts/runs/run_autotuned.py` | auto-tune 既定のランナー | `python -m marsdisk.run` に `--auto-tune` を付与します。 |
| `scripts/runs/run_axis_r_sweep.py` | r–T–M グリッドの大量実行 | `analysis/agent_runs/AXIS_r_sweep` に YAML／結果を生成し、ケースを実行します。 |
| `scripts/runs/run_inner_disk_suite.py` | Φ(1)×T_M スイート | Φ(1)={0.20,0.37,0.60} と温度掃引を組み合わせて 1 年積分します。 |
| `scripts/debug/debug_psd_drift.py` | PSD サイズドリフトの再ビン比較 | 実装と参照リビンの差分を CSV/JSON に出力します。 |
| `scripts/debug/debug_supply_powerlaw_slope.py` | powerlaw 供給の傾き診断 | 供給注入の `dN/ds` 傾きと質量整合を CSV/JSON に記録します。 |
| `scripts/debug/debug_fragment_tensor_lr.py` | 破片テンソルの LR 配分診断 | `Y[k_lr,i,j]` と `f_lr` の差、総和のズレを CSV/JSON に記録します。 |
| `scripts/debug/debug_blowout_chi_scaling.py` | chi_blow スケーリング診断 | `a_blow` と bin 端点の関係、および `dSigma_dt_blowout` の時系列を出力します。 |
| `scripts/sweeps/sweep_beta_map.py` | β(r/R_M, T_M, t) 立方体生成 | 1 軌道分の β 時系列をサンプリングし、Zarr 立方体＋ `map_spec.json` を出力します。 |
| `scripts/sweeps/sweep_heatmaps.py` | 汎用 2D パラメータスイープ | マップ定義とバリアント指定を展開し、並列で `marsdisk.run` を実行します。 |
| `scripts/sweeps/sweep_mass_loss_map.py` | 1 軌道あたり質量損失マップ | `sample_mass_loss_one_orbit` を呼び、`map_massloss.csv` と `logs/spec.json` を作成します。 |
| `scripts/sweeps/sweep_massloss_heatmap_gif.py` | Φ テーブル別の質量損失ヒートマップ＋GIF | 温度掃引と GIF 生成をまとめて実行します。 |
| `scripts/sweeps/sweep_massloss_map.py` | `_configs/05_massloss_base.yml` ベースの Map-1 ドライバ | (r/T) グリッドの YAML を生成し `map1/` 以下に出力します。 |

## 運用メモ
- すべてのスクリプトは `python scripts/<category>/<name>.py [options]` で単独起動できます。CI・エージェントから呼び出す場合もこのパスを基準にしてください。
- Windows 向け `.cmd` を新規作成・更新した場合は、**必ず preflight をテストとして実行**します（非Windowsは `--simulate-windows` を付与）。必要に応じて `--check-tools` / `--require-powershell` を追加してください。
- 分析用ユーティリティが必要になった場合は、`tools/` ではなく本ディレクトリに追加し、本 README の表へ追記する運用に統一します。
- 既存の `tools/` には互換ラッパーが一時的に残っていますが、将来的に削除されても本 README に列挙した機能は維持される想定です。
- 新しい Windows 向け `.cmd` ランナーは `scripts/runsets/windows/` か `scripts/runsets/windows/legacy/` に追加します。`scripts/runsets/windows/legacy/run_sublim_windows.cmd` を雛形に、(1) `.venv` が無ければ作成し `requirements.txt` から依存を取得、(2) `OUTDIR` を標準の保存規則（例: `out/<YYYYMMDD-HHMM>_<short-title>__<shortsha>__seed<n>/`）に従って設定し、必要なら `if not exist "%OUTDIR%" mkdir "%OUTDIR%"` で生成、(3) `python -m marsdisk.run` を既存スクリプトと同じフローで起動して結果を書き込む、を必須手順とします。追加した `.cmd` はこの README の表にも用途を一行で追記してください。
