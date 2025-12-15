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
| `SECONDS_PER_YEAR` | L76 | クラス | Module constant |
| `MAX_STEPS` | L77 | クラス | Module constant |
| `AUTO_MAX_MARGIN` | L78 | クラス | Module constant |
| `TAU_MIN` | L79 | クラス | Module constant |
| `KAPPA_MIN` | L80 | クラス | Module constant |
| `_KAPPA_WARNED_LABELS` | L81 | ヘルパー | Module constant |
| `DEBUG_STAGE` | L82 | クラス | Module constant |
| `_log_stage` | L85 | ヘルパー | Emit coarse-grained progress markers for hang診断用. |
| `DEFAULT_SEED` | L94 | クラス | Module constant |
| `MASS_BUDGET_TOLERANCE_PERCENT` | L95 | クラス | Module constant |
| `SINK_REF_SIZE` | L96 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_THRESHOLD` | L97 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_STRICT` | L98 | クラス | Module constant |
| `PHASE7_SCHEMA_VERSION` | L99 | クラス | Module constant |
| `MEMORY_RUN_ROW_BYTES` | L101 | クラス | Module constant |
| `MEMORY_PSD_ROW_BYTES` | L102 | クラス | Module constant |
| `MEMORY_DIAG_ROW_BYTES` | L103 | クラス | Module constant |
| `_ensure_finite_kappa` | L106 | ヘルパー | Return a finite, non-negative kappa value, clampin... |
| `_resolve_los_factor` | L122 | ヘルパー | Return the multiplicative factor f_los scaling τ_v... |
| `compute_phase_tau_fields` | L138 | 関数 | Return (τ_used, τ_vertical, τ_los) for phase evalu... |
| `ProgressReporter` | L154 | クラス | Lightweight terminal progress bar with ETA feedbac... |
| `_parse_override_value` | L263 | ヘルパー | Return a Python value parsed from a CLI override s... |
| `_apply_overrides_dict` | L290 | ヘルパー | Apply dotted-path overrides to a configuration dic... |
| `_merge_physics_section` | L328 | ヘルパー | Inline the optional ``physics`` mapping into the r... |
| `_safe_float` | L347 | ヘルパー | Return ``value`` cast to float when finite, otherw... |
| `_resolve_feedback_tau_field` | L359 | ヘルパー | Normalise feedback.tau_field and reject unknown va... |
| `_derive_seed_components` | L372 | ヘルパー | No description available. |
| `_resolve_seed` | L397 | ヘルパー | Return the RNG seed, seed expression description, ... |
| `_auto_chi_blow` | L412 | ヘルパー | Return an automatic chi_blow scaling based on β an... |
| `_fast_blowout_correction_factor` | L427 | ヘルパー | Return the effective loss fraction ``f_fast = 1 - ... |
| `_compute_gate_factor` | L447 | ヘルパー | Return gate coefficient f_gate=t_solid/(t_solid+t_... |
| `_human_bytes` | L469 | ヘルパー | Return a human-readable byte string. |
| `_memory_estimate` | L481 | ヘルパー | Return short and long memory hints estimated from ... |
| `_normalise_physics_mode` | L506 | ヘルパー | Return the canonical physics.mode string. |
| `_clone_config` | L522 | ヘルパー | Return a deep copy of a configuration object. |
| `_resolve_time_grid` | L530 | ヘルパー | Return (t_end, dt_nominal, dt_step, n_steps, info)... |
| `_Phase5VariantResult` | L632 | ヘルパー | Artifacts recorded for a variant within the Phase ... |
| `_read_json` | L645 | ヘルパー | No description available. |
| `_hash_payload` | L650 | ヘルパー | No description available. |
| `_prepare_phase5_variants` | L655 | ヘルパー | Return normalized variant specifications or raise ... |
| `RunConfig` | L688 | クラス | Configuration parameters for a zero-dimensional ru... |
| `RunState` | L705 | クラス | State variables evolved during the run. |
| `ZeroDHistory` | L715 | クラス | Per-step history bundle used by the full-feature z... |
| `StreamingState` | L739 | クラス | Manage streaming flush of large histories to Parqu... |
| `step` | L872 | 関数 | Advance the coupled S0/S1 system by one time-step. |
| `run_n_steps` | L924 | 関数 | Run ``n`` steps and optionally serialise results. |
| `load_config` | L954 | 関数 | Load a YAML configuration file into a :class:`Conf... |
| `_gather_git_info` | L979 | ヘルパー | Return basic git metadata for provenance recording... |
| `_configure_logging` | L1006 | ヘルパー | Configure root logging and optionally silence Pyth... |
| `MassBudgetViolationError` | L1017 | クラス | Raised when the mass budget tolerance is exceeded. |
| `_write_zero_d_history` | L1021 | ヘルパー | Persist time series, diagnostics, and rollups for ... |
| `run_zero_d` | L1124 | メイン | Execute the full-feature zero-dimensional simulati... |
| `_run_phase5_variant` | L4878 | ヘルパー | Execute a single-process variant run and capture i... |
| `_write_phase5_comparison_products` | L4940 | ヘルパー | Aggregate per-variant artifacts into the compariso... |
| `run_phase5_comparison` | L5082 | 関数 | Run the Phase 5 dual single-process comparison wor... |
| `main` | L5117 | 関数 | Command line entry point. |

## 3. 主要セクション（目安）

> 以下の行範囲はコード変更により変動します。`inventory.json` を基に自動更新されます。

- **`run_zero_d()`**: L1124–? (メイン実行ドライバ)
- **`main()`**: L5117–? (CLI エントリポイント)
- **`StreamingState`**: L739–? (ストリーミング出力管理)
- **`ZeroDHistory`**: L715–? (ステップ履歴管理)
## 4. 探索ガイド

| 調べたいこと | 参照シンボル | 備考 |
|-------------|-------------|------|
| 設定ロード | [`load_config`](L954) | YAML→Config変換 |
| 時間グリッド | [`_resolve_time_grid`](L530) | dt, n_steps決定 |
| シード解決 | [`_resolve_seed`](L397) | RNG初期化 |
| 高速ブローアウト補正 | [`_fast_blowout_correction_factor`](L427) | dt/t_blow補正 |
| 進捗表示 | [`ProgressReporter`](L154) | プログレスバー |
| 履歴書き出し | [`_write_zero_d_history`](L1021) | Parquet/CSV出力 |
| Phase5比較 | [`run_phase5_comparison`](L5082) | バリアント比較 |

---

## 5. 関連ドキュメント

- [physics_flow.md](file:///analysis/physics_flow.md): 計算フローのシーケンス図
- [sinks_callgraph.md](file:///analysis/sinks_callgraph.md): シンク呼び出しグラフ
- [overview.md](file:///analysis/overview.md): モジュール責務
- [equations.md](file:///analysis/equations.md): 物理式リファレンス

---

*最終更新: inventory.json から自動生成*
