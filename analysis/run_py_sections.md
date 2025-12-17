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
| `SECONDS_PER_YEAR` | L78 | クラス | Module constant |
| `MAX_STEPS` | L79 | クラス | Module constant |
| `AUTO_MAX_MARGIN` | L80 | クラス | Module constant |
| `TAU_MIN` | L81 | クラス | Module constant |
| `KAPPA_MIN` | L82 | クラス | Module constant |
| `_KAPPA_WARNED_LABELS` | L83 | ヘルパー | Module constant |
| `DEBUG_STAGE` | L84 | クラス | Module constant |
| `_log_stage` | L87 | ヘルパー | Emit coarse-grained progress markers for hang診断用. |
| `DEFAULT_SEED` | L96 | クラス | Module constant |
| `MASS_BUDGET_TOLERANCE_PERCENT` | L97 | クラス | Module constant |
| `SINK_REF_SIZE` | L98 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_THRESHOLD` | L99 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_STRICT` | L100 | クラス | Module constant |
| `PHASE7_SCHEMA_VERSION` | L101 | クラス | Module constant |
| `MEMORY_RUN_ROW_BYTES` | L103 | クラス | Module constant |
| `MEMORY_PSD_ROW_BYTES` | L104 | クラス | Module constant |
| `MEMORY_DIAG_ROW_BYTES` | L105 | クラス | Module constant |
| `_ensure_finite_kappa` | L108 | ヘルパー | Return a finite, non-negative kappa value, clampin... |
| `_resolve_los_factor` | L124 | ヘルパー | Return the multiplicative factor f_los scaling τ_v... |
| `compute_phase_tau_fields` | L140 | 関数 | Return (τ_used, τ_vertical, τ_los) for phase evalu... |
| `ProgressReporter` | L156 | クラス | Lightweight terminal progress bar with ETA feedbac... |
| `_parse_override_value` | L265 | ヘルパー | Return a Python value parsed from a CLI override s... |
| `_apply_overrides_dict` | L292 | ヘルパー | Apply dotted-path overrides to a configuration dic... |
| `_merge_physics_section` | L330 | ヘルパー | Inline the optional ``physics`` mapping into the r... |
| `_safe_float` | L349 | ヘルパー | Return ``value`` cast to float when finite, otherw... |
| `_float_or_nan` | L361 | ヘルパー | Return a finite float or ``nan`` to stabilise Parq... |
| `_format_exception_short` | L373 | ヘルパー | Collapse whitespace and truncate exception text fo... |
| `_resolve_feedback_tau_field` | L384 | ヘルパー | Normalise feedback.tau_field and reject unknown va... |
| `_derive_seed_components` | L397 | ヘルパー | No description available. |
| `_resolve_seed` | L422 | ヘルパー | Return the RNG seed, seed expression description, ... |
| `_auto_chi_blow` | L437 | ヘルパー | Return an automatic chi_blow scaling based on β an... |
| `_fast_blowout_correction_factor` | L452 | ヘルパー | Return the effective loss fraction ``f_fast = 1 - ... |
| `_compute_gate_factor` | L472 | ヘルパー | Return gate coefficient f_gate=t_solid/(t_solid+t_... |
| `_human_bytes` | L494 | ヘルパー | Return a human-readable byte string. |
| `_memory_estimate` | L506 | ヘルパー | Return short and long memory hints estimated from ... |
| `_normalise_physics_mode` | L531 | ヘルパー | Return the canonical physics.mode string. |
| `_clone_config` | L547 | ヘルパー | Return a deep copy of a configuration object. |
| `_resolve_time_grid` | L555 | ヘルパー | Return (t_end, dt_nominal, dt_step, n_steps, info)... |
| `_Phase5VariantResult` | L657 | ヘルパー | Artifacts recorded for a variant within the Phase ... |
| `_read_json` | L670 | ヘルパー | No description available. |
| `_hash_payload` | L675 | ヘルパー | No description available. |
| `_prepare_phase5_variants` | L680 | ヘルパー | Return normalized variant specifications or raise ... |
| `RunConfig` | L713 | クラス | Configuration parameters for a zero-dimensional ru... |
| `RunState` | L730 | クラス | State variables evolved during the run. |
| `ZeroDHistory` | L740 | クラス | Per-step history bundle used by the full-feature z... |
| `StreamingState` | L764 | クラス | Manage streaming flush of large histories to Parqu... |
| `step` | L946 | 関数 | Advance the coupled S0/S1 system by one time-step. |
| `run_n_steps` | L998 | 関数 | Run ``n`` steps and optionally serialise results. |
| `load_config` | L1028 | 関数 | Load a YAML configuration file into a :class:`Conf... |
| `_gather_git_info` | L1053 | ヘルパー | Return basic git metadata for provenance recording... |
| `_configure_logging` | L1080 | ヘルパー | Configure root logging and optionally silence Pyth... |
| `MassBudgetViolationError` | L1091 | クラス | Raised when the mass budget tolerance is exceeded. |
| `_write_zero_d_history` | L1095 | ヘルパー | Persist time series, diagnostics, and rollups for ... |
| `run_zero_d` | L1198 | メイン | Execute the full-feature zero-dimensional simulati... |
| `_run_phase5_variant` | L5100 | ヘルパー | Execute a single-process variant run and capture i... |
| `_write_phase5_comparison_products` | L5162 | ヘルパー | Aggregate per-variant artifacts into the compariso... |
| `run_phase5_comparison` | L5304 | 関数 | Run the Phase 5 dual single-process comparison wor... |
| `main` | L5339 | 関数 | Command line entry point. |

## 3. 主要セクション（目安）

> 以下の行範囲はコード変更により変動します。`inventory.json` を基に自動更新されます。

- **`run_zero_d()`**: L1198–? (メイン実行ドライバ)
- **`main()`**: L5339–? (CLI エントリポイント)
- **`StreamingState`**: L764–? (ストリーミング出力管理)
- **`ZeroDHistory`**: L740–? (ステップ履歴管理)
## 4. 探索ガイド

| 調べたいこと | 参照シンボル | 備考 |
|-------------|-------------|------|
| 設定ロード | [`load_config`](L1028) | YAML→Config変換 |
| 時間グリッド | [`_resolve_time_grid`](L555) | dt, n_steps決定 |
| シード解決 | [`_resolve_seed`](L422) | RNG初期化 |
| 高速ブローアウト補正 | [`_fast_blowout_correction_factor`](L452) | dt/t_blow補正 |
| 進捗表示 | [`ProgressReporter`](L156) | プログレスバー |
| 履歴書き出し | [`_write_zero_d_history`](L1095) | Parquet/CSV出力 |
| Phase5比較 | [`run_phase5_comparison`](L5304) | バリアント比較 |

---

## 5. 関連ドキュメント

- [physics_flow.md](file:///analysis/physics_flow.md): 計算フローのシーケンス図
- [sinks_callgraph.md](file:///analysis/sinks_callgraph.md): シンク呼び出しグラフ
- [overview.md](file:///analysis/overview.md): モジュール責務
- [equations.md](file:///analysis/equations.md): 物理式リファレンス

---

*最終更新: inventory.json から自動生成*
