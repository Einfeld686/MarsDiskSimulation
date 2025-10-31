# Reference Coverage (RC) Tool Suite

このスイートは、analysis ドキュメントにおける `[marsdisk/path.py:行–行]` 形式のアンカー参照と、`marsdisk/**/*.py` の公開シンボルを突合し、参照漏れの根本原因を特定するための最小セットです。既存のドキュメント規約を厳守し、検出→原因診断→修正案→CI ガードまで一貫して運用できます。

## 構成と役割
- `rc_scan_ast.py` : AST を用いて公開シンボル（トップレベル def/class）を抽出し、`reports/ast_symbols.json` に出力します。
- `rc_scan_docs.py` : analysis/*.md 等から参照アンカーを収集し、`reports/doc_refs.json` を生成します。`[marsdisk/run.py:520–612]` および `#... [L520–L612]` 形式を両対応。
- `rc_compare.py` : AST とアンカーを突合し、カバレッジ指標（特に公開関数）を算出。`reports/coverage.json` と `reports/coverage_report.md` を出力し、Top Coverage Gaps を明示します。
- `rc_root_cause_probe.py` : `tools/doc_sync_agent.py` の DEFAULT_DOC_PATHS / RG_PATTERN / SKIP_DIR_NAMES を点検し、仮説 A–C の判定と grid 系関数の E2E 状況を `reports/root_cause_probe.md` に記録します。
- `rc_anchor_suggestions.py` : 未参照シンボルごとに Markdown パッチ案（`.mdpatch`）を `suggestions/` 以下へ生成し、`reports/suggestions_index.json` に索引を残します。
- `rc_ci_guard.py` : `coverage.json` を読み取り、`--fail-under` を下回れば終了コード 2 を返す CI 用ガードです。
- `rc_run_all.py` : 上記 1→2→3→4→5 を順に実行し、`reports/summary.md` に要約を集約します。`--strict` や `--fail-under` を下流へ伝播します。

生成物は `agent_test/reports/` 配下に JSON/MD、`agent_test/suggestions/` にパッチ案を並べ、既存ファイルは上書きしません。

## 参照スタイルと根拠
- 角括弧内で `[marsdisk/grid.py:17–33]` のように、相対パス + コロン + 行範囲（`–`/`-`）を記述します。
- 既存ドキュメントの例: `analysis/run-recipes.md`, `analysis/overview.md`, `analysis/sinks_callgraph.md`。
- DocSyncAgent 既定: `DEFAULT_DOC_PATHS` は上記 analysis ファイルを含み、`RG_PATTERN` は `beta_at_smin|beta_threshold|s_min` に限定されています（詳細は `rc_root_cause_probe.py` が記録）。

## 使い方
1. `python -m agent_test.rc_run_all`  
   - 主な artefact: `reports/ast_symbols.json`, `doc_refs.json`, `coverage.json`, `coverage_report.md`, `root_cause_probe.md`, `suggestions_index.json`, `summary.md`。
   - `--strict` : private シンボル（`_` 始まり）も集計対象。
   - `--fail-under 0.70` : カバレッジが 70% 未満なら rc_compare が終了コード 2。rc_run_all の exit code は各ステップの最大値を返します。
   - `--json-only` : summary.md をコンパクト化して JSON 生成物中心に列挙します。
2. 生成された `suggestions/*.mdpatch` を確認し、適切な analysis/*.md に追記事項として適用。
3. 必要に応じて DocSyncAgent (`python -m tools.doc_sync_agent --all --write`) を実行し、行番号を再同期します。

### 個別 CLI
- `python -m agent_test.rc_scan_ast --help` など、各スクリプトは `--help` を備えています。
- `rc_ci_guard.py`  
  - 例: `python -m agent_test.rc_ci_guard --fail-under 0.70`  
  - 終了コード: 0 (基準達成) / 2 (未達)。標準出力で現在値・閾値・上位未参照 5 件を報告します。

## 推奨ワークフロー
1. `rc_run_all.py` で現状診断。
2. `reports/coverage_report.md` の "Top Coverage Gaps" から優先度を判断。
3. `suggestions/` のパッチ案を参考にドキュメントへアンカー追記。
4. DocSyncAgent で行番号同期 → `rc_run_all.py` を再実行して改善を確認。
5. CI では `rc_ci_guard.py --fail-under 0.70` を組み込み、閾値を満たさない場合に検知。

## 例外方針
- private ヘルパーやテスト専用関数はデフォルトで母数から除外（`--strict` で明示的に含める）。
- 自動生成コード・テーブル読込ユーティリティ等で人手フォローが難しい場合は、`suggestions_index.json` を根拠に保留する判断も可能。

## 参考資料
- `analysis/overview.md`: アーキテクチャ概要と `[marsdisk/grid.py:17–33]` 形式のアンカー例。
- `analysis/run-recipes.md`: CLI 実行経路と入出力仕様のアンカー例。
- `analysis/sinks_callgraph.md`: シンク挙動の参照グラフとアンカー例。
