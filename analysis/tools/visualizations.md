# tools 可視化スクリプト・リファレンス

本書は `tools/` 配下に配置された可視化・診断スクリプトの概要と入出力を整理したものです。エージェント向けの運用ルールは `tools/AGENTS.md` を参照してください。

## 1. ルート直下のスクリプト

| ファイル | 主な用途 | 入出力 | 備考 |
| --- | --- | --- | --- |
| `plotting.py` | PSD の温度×サイズマップを PNG/GIF に変換するユーティリティ関数群。 | 入力: 粒径エッジ、時間軸、温度配列、PSD キューブ等。出力: `fig_heatmap_t###.png`、モンタージュ、GIF。 | `prototypes/psd/` から呼び出される内部 API。Matplotlib `Agg` 固定。 |
| `psd_time_evolution.py` | PSD の 0D 時間進化を描画する CLI ラッパー。 | 入力: Q_pr テーブル、サイズレンジ、温度、シミュレーション設定。出力: PNG/GIF、`run.json`。 | 実装本体は `prototypes/psd/time_evolution.py`。 |
| `psd_T_time_map.py` | 温度走査付き PSD “wavy” マップの可視化。 | 入力: Q_pr テーブル、温度レンジ、PSD 初期条件。出力: Parquet、PNG、GIF。 | 実装は `prototypes/psd/temperature_time_map.py` に委譲。 |
| `psd_core.py` | PSD 実験用の物理ルーチンを re-export。 | 入力: なし | 新規コードは `prototypes/psd/core.py` に実装する。 |
| `doc_sync_agent.py` | ドキュメント同期ユーティリティの後方互換ラッパー。 | CLI 引数。 | 本体は `marsdisk.ops.doc_sync_agent`。ルート `tools/` に配置。 |
| `make_qpr_table.py` | Planck 平均 ⟨Q_pr⟩ テーブル生成ラッパー。 | 入力: 粒径レンジ、温度リスト。出力: HDF5。 | 本体は `marsdisk.ops.make_qpr_table`。ルート `tools/` に配置。 |

## 2. `tools/plotting/` サブディレクトリ

| ファイル | 主な可視化 | 入力 | 出力 |
| --- | --- | --- | --- |
| `make_beta_movie.py` | β(r/R_M, T_M, t) の時系列ムービー作成。 | `beta_cube.zarr`, `map_spec.json`。 | PNG フレームと MP4。 |
| `make_figs.py` | Map-1 のレジーム図、サイズ別寄与、質量収支タイムライン。 | `sweeps/*/map*/` の集計 CSV、`out/series/run.parquet` 等。 | 複数 PNG。 |
| `make_massloss_map.py` | 総質量損失率ヒートマップとシンク分率等値線。 | `results/*.csv`（`sweep_mass_loss_map.py` 生成）。 | PNG (`fig_massloss_map.png`)。 |
| `make_sweep_summary.py` | temp_supply_sweep バッチ全体のサマリー・ヒートマップ生成。 | sweep バッチディレクトリ（`T*_mu*_phi*` サブディレクトリ群）。 | CSV (`sweep_summary.csv`)、PNG (`fig_sweep_mloss.png`, `fig_sweep_clip.png`, `fig_sweep_sensitivity.png`)。 |
| `plot_mass_loss_map.py` | 1 周期あたり質量損失率ヒートマップ。 | `scripts/sweep_mass_loss_map.py` が生成した CSV。 | PNG (`fig_massloss_heatmap.png`)。 |
| `base.py` | プロット共通設定（フォント、スタイル、カラーマップ）。 | なし。 | 他スクリプトがインポートして使用。`configure_matplotlib()` 等を提供。 |

## 3. `tools/diagnostics/`

| ファイル | 主な可視化 | 入力 | 出力 |
| --- | --- | --- | --- |
| `beta_map.py` | β（遮蔽前後）を r×T グリッドで評価し CSV/PNG に出力。 | `configs/base.yml`、⟨Q_pr⟩ テーブル、Φ テーブル。 | CSV (`beta_map.csv` 等)、ヒートマップ PNG。 |

## 4. `tools/` 直下のその他のユーティリティ

| ファイル | 用途 | 備考 |
| --- | --- | --- |
| `derive_supply_rate.py` | 無次元パラメータ μ から供給率を計算し YAML 形式で出力。 | `supply` 設定の構築支援。 |
| `evaluation_system.py` | シミュレーション結果の自動検証・指標評価システム。 | CI/検証フローの中核。 |
| `run_analysis_doc_tests.py` | analysis ドキュメントのテストランナー。 | `make analysis-doc-tests` の実体。 |

## 5. 参照・運用ノート

- 各スクリプトは `python -m tools.<module>` で起動できる互換ラッパーを保持している。内部実装を移動した場合は本書を更新する。
- 生成物は `simulation_results/` または `figures/` 配下に保存するのが既定であり、ユーザー指定パスを優先する。
- 新しい可視化を追加する際は、入出力フォーマットと必要ライブラリを表形式で追記する。
