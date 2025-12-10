# assumption_trace_data_sources（stub）

目的: 仮定スキャナが参照すべき入力ソースを一覧化する。詳細設計や探索キーワードは `out/plan/assumption_trace_data_sources.md` にある作業メモを参照し、本ファイルはリポジトリ内の正式な参照先を短くまとめる。

## 主な入力ソース
- 数式: `analysis/equations.md`（DocSync 済みの (E.xxx) 見出し）
- 出典カタログ: `analysis/references.registry.json`、`analysis/UNKNOWN_REF_REQUESTS.jsonl`
- コードインデックス: `analysis/source_map.json`、`analysis/inventory.json`
- 設定スキーマ: `marsdisk/schema.py`（Pydantic Config）、`marsdisk/config_utils.py`（label 付与）
- 設定例: `configs/` 配下の YAML（値・ブールトグル確認用）
- 既存 registry: `analysis/assumption_registry.jsonl`（正規化ターゲット）

補足: gap やデータソースの詳細メモは `out/plan/assumption_trace_gap_list.md` / `out/plan/assumption_trace_data_sources.md` を参照（手書きの作業ログ扱い）。
