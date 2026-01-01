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
| `SECONDS_PER_YEAR` | L91 | クラス | Module constant |
| `MAX_STEPS` | L92 | クラス | Module constant |
| `AUTO_MAX_MARGIN` | L93 | クラス | Module constant |
| `TAU_MIN` | L94 | クラス | Module constant |
| `KAPPA_MIN` | L95 | クラス | Module constant |
| `DEFAULT_SEED` | L96 | クラス | Module constant |
| `MASS_BUDGET_TOLERANCE_PERCENT` | L97 | クラス | Module constant |
| `SINK_REF_SIZE` | L98 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_THRESHOLD` | L99 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_STRICT` | L100 | クラス | Module constant |
| `EXTENDED_DIAGNOSTICS_VERSION` | L101 | クラス | Module constant |
| `SmolSinkWorkspace` | L109 | クラス | No description available. |
| `SupplyStepResult` | L119 | クラス | No description available. |
| `SurfaceSupplyStepResult` | L128 | クラス | No description available. |
| `_get_smol_sink_workspace` | L135 | ヘルパー | No description available. |
| `_apply_supply_step` | L155 | ヘルパー | No description available. |
| `_apply_shielding_and_supply` | L212 | ヘルパー | No description available. |
| `_apply_blowout_correction` | L283 | ヘルパー | No description available. |
| `_apply_blowout_gate` | L294 | ヘルパー | No description available. |
| `_resolve_t_coll_step` | L307 | ヘルパー | No description available. |
| `_reset_collision_runtime_state` | L334 | ヘルパー | Clear per-run collision caches and warning state. |
| `_get_max_steps` | L341 | ヘルパー | Return MAX_STEPS, honoring overrides applied to th... |
| `_log_stage` | L355 | ヘルパー | Emit coarse progress markers for debugging long ru... |
| `_model_fields_set` | L361 | ヘルパー | Return explicitly-set fields for a Pydantic model ... |
| `_resolve_los_factor` | L372 | ヘルパー | Return the multiplicative factor f_los scaling τ_v... |
| `_surface_energy_floor` | L388 | ヘルパー | Return surface-energy-limited minimum size (Krijt ... |
| `_auto_chi_blow` | L427 | ヘルパー | Return an automatic chi_blow scaling based on β an... |
| `load_config` | L447 | 関数 | Load a YAML configuration file into a :class:`Conf... |
| `_gather_git_info` | L472 | ヘルパー | Return basic git metadata for provenance recording... |
| `MassBudgetViolationError` | L499 | クラス | Raised when the mass budget tolerance is exceeded. |
| `run_zero_d` | L505 | メイン | Execute the full-feature zero-dimensional simulati... |
| `main` | L5389 | 関数 | Command line entry point. |

## 3. 主要セクション（目安）

> 以下の行範囲はコード変更により変動します。`inventory.json` を基に自動更新されます。

- **`run_zero_d()`**: L505–? (メイン実行ドライバ)
- **`main()`**: L5389–? (CLI エントリポイント)
## 4. 探索ガイド

| 調べたいこと | 参照シンボル | 備考 |
|-------------|-------------|------|
| 設定ロード | [`load_config`](L447) | YAML→Config変換 |
| 時間グリッド | `_resolve_time_grid` | dt, n_steps決定 (未検出) |
| シード解決 | `_resolve_seed` | RNG初期化 (未検出) |
| 高速ブローアウト補正 | `_fast_blowout_correction_factor` | dt/t_blow補正 (未検出) |
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
