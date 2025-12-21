# run.py 内部セクション対応表

> **文書種別**: リファレンス（Diátaxis: Reference）
> **自動生成**: このドキュメントは `analysis/tools/make_run_sections.py` により自動生成されます。
> 手動編集しないでください。

本ドキュメントは `marsdisk/run.py` の内部構造をセクション別に分類し、
AIエージェントがコード検索を効率化するためのマップを提供します。

---

## 1. トップレベル構造

| シンボル | 行 | 種別 | 概要 |
|---------|-----|------|------|
| `SECONDS_PER_YEAR` | L87 | クラス | Module constant |
| `MAX_STEPS` | L88 | クラス | Module constant |
| `AUTO_MAX_MARGIN` | L89 | クラス | Module constant |
| `TAU_MIN` | L90 | クラス | Module constant |
| `KAPPA_MIN` | L91 | クラス | Module constant |
| `DEFAULT_SEED` | L92 | クラス | Module constant |
| `MASS_BUDGET_TOLERANCE_PERCENT` | L93 | クラス | Module constant |
| `SINK_REF_SIZE` | L94 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_THRESHOLD` | L95 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_STRICT` | L96 | クラス | Module constant |
| `EXTENDED_DIAGNOSTICS_VERSION` | L97 | クラス | Module constant |
| `_get_max_steps` | L103 | ヘルパー | Return MAX_STEPS, honoring overrides applied to th... |
| `_log_stage` | L117 | ヘルパー | Emit coarse progress markers for debugging long ru... |
| `_model_fields_set` | L123 | ヘルパー | Return explicitly-set fields for a Pydantic model ... |
| `_resolve_los_factor` | L134 | ヘルパー | Return the multiplicative factor f_los scaling τ_v... |
| `_surface_energy_floor` | L150 | ヘルパー | Return surface-energy-limited minimum size (Krijt ... |
| `_auto_chi_blow` | L174 | ヘルパー | Return an automatic chi_blow scaling based on β an... |
| `_fast_blowout_correction_factor` | L189 | ヘルパー | Return the effective loss fraction ``f_fast = 1 - ... |
| `load_config` | L212 | 関数 | Load a YAML configuration file into a :class:`Conf... |
| `_gather_git_info` | L237 | ヘルパー | Return basic git metadata for provenance recording... |
| `MassBudgetViolationError` | L264 | クラス | Raised when the mass budget tolerance is exceeded. |
| `run_zero_d` | L270 | メイン | Execute the full-feature zero-dimensional simulati... |
| `main` | L4815 | 関数 | Command line entry point. |

## 3. 主要セクション（目安）

> 以下の行範囲はコード変更により変動します。`inventory.json` を基に自動更新されます。

- **`run_zero_d()`**: L270–? (メイン実行ドライバ)
- **`main()`**: L4815–? (CLI エントリポイント)
## 4. 探索ガイド

| 調べたいこと | 参照シンボル | 備考 |
|-------------|-------------|------|
| 設定ロード | [`load_config`](L212) | YAML→Config変換 |
| 時間グリッド | `_resolve_time_grid` | dt, n_steps決定 (未検出) |
| シード解決 | `_resolve_seed` | RNG初期化 (未検出) |
| 高速ブローアウト補正 | [`_fast_blowout_correction_factor`](L189) | dt/t_blow補正 |
| 進捗表示 | `ProgressReporter` | プログレスバー (未検出) |
| 履歴書き出し | `_write_zero_d_history` | Parquet/CSV出力 (未検出) |
| Phase5比較 | `run_phase5_comparison` | バリアント比較 (未検出) |

---

## 5. 関連ドキュメント

- [physics_flow.md](file:///analysis/physics_flow.md): 計算フローのシーケンス図
- [sinks_callgraph.md](file:///analysis/sinks_callgraph.md): シンク呼び出しグラフ
- [overview.md](file:///analysis/overview.md): モジュール責務
- [equations.md](file:///analysis/equations.md): 物理式リファレンス

---

*最終更新: inventory.json から自動生成*
