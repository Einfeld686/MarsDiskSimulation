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
| `SECONDS_PER_YEAR` | L66 | クラス | Module constant |
| `MAX_STEPS` | L67 | クラス | Module constant |
| `TAU_MIN` | L68 | クラス | Module constant |
| `KAPPA_MIN` | L69 | クラス | Module constant |
| `DEFAULT_SEED` | L70 | クラス | Module constant |
| `MASS_BUDGET_TOLERANCE_PERCENT` | L71 | クラス | Module constant |
| `SINK_REF_SIZE` | L72 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_THRESHOLD` | L73 | クラス | Module constant |
| `FAST_BLOWOUT_RATIO_STRICT` | L74 | クラス | Module constant |
| `EXTENDED_DIAGNOSTICS_VERSION` | L75 | クラス | Module constant |
| `TimeGridInfo` | L83 | クラス | Information about the simulation time grid. |
| `SimulationState` | L114 | クラス | Mutable state variables during simulation. |
| `PhysicsFlags` | L162 | クラス | Boolean flags controlling physics behavior. |
| `OrchestrationContext` | L179 | クラス | Context object holding all simulation parameters a... |
| `resolve_time_grid` | L210 | 関数 | Resolve (t_end, dt_nominal, dt_step, n_steps, info... |
| `resolve_orbital_radius` | L313 | 関数 | Resolve orbital radius from configuration. |
| `resolve_physics_flags` | L320 | 関数 | Resolve physics control flags from configuration. |
| `derive_seed_components` | L412 | 関数 | Return a deterministic seed basis string from conf... |
| `resolve_seed` | L439 | 関数 | Return the RNG seed, seed expression description, ... |
| `human_bytes` | L454 | 関数 | Return a human-readable byte string. |
| `memory_estimate` | L466 | 関数 | Return short and long memory hints estimated from ... |
| `safe_float` | L536 | 関数 | Return value cast to float when finite, otherwise ... |
| `human_bytes` | L558 | 関数 | Return a human-readable byte string. |
| `series_stats` | L580 | 関数 | Compute min, median, max of a list of values. |

## 3. 主要セクション（目安）

> 以下の行範囲はコード変更により変動します。`inventory.json` を基に自動更新されます。

## 4. 探索ガイド

| 調べたいこと | 参照シンボル | 備考 |
|-------------|-------------|------|
| 設定ロード | `load_config` | YAML→Config変換 (未検出) |
| 時間グリッド | [`resolve_time_grid`](L210) | dt, n_steps決定 |
| シード解決 | [`resolve_seed`](L439) | RNG初期化 |
| 高速ブローアウト補正 | `fast_blowout_correction_factor` | dt/t_blow補正 (未検出) |
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
