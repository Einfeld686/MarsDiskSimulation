# assumption_registry スキーマ（draft）

目的: `analysis/assumption_registry.jsonl` を単一ソースとし、仮定→式→設定→コードパスの対応を機械可読に保つ。各フィールドの型・必須/任意・生成責務（人手/自動）をここで固定する。

## フィールド定義と生成責務

| フィールド | 型 / 必須 | 生成方法 | 説明 |
| --- | --- | --- | --- |
| `id` | str / 必須 | Phase1: 人手 (`category:slug`, 英小文字+数字+`-`/`:`)。将来: eq_id + tag から自動生成可 | 安定識別子（例: `ops:gas_poor_default`） |
| `title` | str / 任意 | 人手（registry 由来） | 読みやすい短い題目 |
| `description` | str / 任意 | 人手（registry 由来） | 仮定クラスタの説明 |
| `scope` | enum / 任意 | 人手: `project_default` / `module_default` / `toggle` | 仮定が効く範囲 |
| `eq_ids` | list[str] / 0件可 | スキャナ: `analysis/equations.md` から DocSync 前提で自動 | 関連する (E.xxx) 配列 |
| `assumption_tags` | list[str] / 0件可 | Phase1: 人手。Phase2: TODO(REF:slug) やタグ候補から補完 | 分類ラベル（`geometry:thin_disk` 等） |
| `config_keys` | list[str] / 0件可 | スキャナ: `schema.Config` introspect + `config_utils` の label を note に格納 | Pydantic フィールドのドットパス（例: `physics.blowout.enabled`） |
| `code_path` | list[str] / 0件可 | スキャナ: `analysis/source_map.json` / `analysis/inventory.json` を優先、無ければ `[file:line–line]` fallback | アンカー付きコード参照 |
| `run_stage` | list[str] / 1件推奨 | Phase1: 人手（`init_ei`/`time_grid`/`physics_controls`/`surface_loop`/`smol_kernel` 初期マップ）。将来 decorator 等で自動化 | 実行段階の列挙 |
| `provenance` | dict / 必須 | スキャナ（不足時は TODO slug） | `paper_key`（任意, references.registry.json），`unknown_slug`（任意, `assumption:` プレフィックス推奨），`source_kind`（必須: `equation`/`config`/`code_comment`/`test`），`type`（任意: `literature`/`impl_choice`/`safety_cap`/`data_source` を推奨），`note`（任意, config_utils label 等） |
| `tests` | list[str] / 0件可 | Phase1: 手入力のみ。将来 pytest メタから自動紐付け検討 | 関連 pytest 名 |
| `outputs` | list[str] / 0件可 | 任意（registry 由来） | 生成・検証する主なカラム/メトリクス |
| `status` | enum / 任意 | 手入力（`draft`/`needs_ref`/`ok` 等） | カバレッジ管理用ステータス |
| `last_checked` | str / 任意 | 手入力（`YYYY-MM-DD` 推奨） | 最終確認日 |

## run_stage の対応表（run.py 段階の列挙）
- `init_ei`: 初期 e/i 設定（run_config["init_ei"]）
- `time_grid`: 時間刻み・t_end 解決（_resolve_time_grid 系）
- `physics_controls`: blowout/shielding/psd_floor/sinks など物理トグル判定
- `surface_loop`: 表層 ODE・tau_gate/gate_factor・fast_blowout 判定
- `smol_kernel`: Smoluchowski カーネル、質量検査、C5 拡散（有効時）
- `prep`: 事前生成ユーティリティ（例: Q_pr テーブル計算）

## 運用方針
- registry（JSONL）が唯一の元データ。`assumption_trace.md` / `assumptions_overview.md` はレンダーで自動ブロックを上書きし、手書き部は共存可。
- UNKNOWN_REF_REQUESTS の slug は仮定系では `assumption:<slug>` を推奨し、式レベルの slug と混在させない。
- coverage 指標:
  - `equation_coverage = (#registry に含まれる eq_id の一意数) / (analysis/equations.md の eq_id 総数)`
  - `function_reference_rate = (source_map.json で equation 出典を持つ code_path のうち registry で参照された割合)`
  - `anchor_consistency_rate = (source_map.json と inventory.json の行範囲が scanner 推定と一致する割合, ±数行許容)`
- make ターゲット `assumptions-autogen-check` で doc_sync → scan → render → analysis-doc-tests → evaluation_system を束ね、上記しきい値未達で FAIL（暫定: equation_coverage≥0.95）。
- provenance.type は PROV-DM/FAIR の「実体/活動/責任主体」整理と整合させ、文献式（literature）と実装側の安全策・上限（impl_choice/safety_cap）、入力データ源（data_source）を区別して登録する。
