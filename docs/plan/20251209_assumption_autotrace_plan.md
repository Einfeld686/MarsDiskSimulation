# 仮定自動抽出システム（初期草案）

目的: code/analysis から仮定と式参照を機械抽出し、`analysis/assumption_trace.*` と `analysis/assumptions_overview.md` を自動更新するための段取りをまとめる。詳細な式やアンカー定義は `analysis/equations.md`・`analysis/AI_USAGE.md` の規約に従い、ここでは実装フェーズと責務だけを整理する。

## 0. 事前確認と運用ルール
- analysis を触るフェーズでは必ず `python -m tools.doc_sync_agent --all --write` → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を同一バッチで回し、coverage とアンカー整合率を保つ。
- 仮定が出典不明な場合は `analysis/UNKNOWN_REF_REQUESTS.jsonl` に slug を登録し、コードや docs では `TODO(REF:slug)` を使う（AI_USAGE 準拠）。
- 数式の唯一ソースは `analysis/equations.md`。本システムは式本文を再生成せず、eq_id とアンカーを参照するだけとする。

## 1. スコープと非スコープ
- 対象: 0D ロジック（ブローアウト・遮蔽・PSD・表層 ODE・Smol カーネル）と設定 YAML、analysis 配下のメタ資料（assumption_trace.*, assumptions_overview.md）。
- 非対象: 1D 拡散や paper 用テキスト生成、SiO₂ cooling サブプロジェクト。外部論文の全文スクレイプも行わない。

## 2. 成果物イメージ
- `analysis/assumption_registry.jsonl` に機械抽出したレコードを追記（eq_id, config_keys, code_path, provenance）。
- `analysis/assumption_trace.md` と `analysis/assumptions_overview.md` を自動レンダーする CLI（例: `python -m analysis.tools.render_assumptions`）の拡張。
- 検知ログとカバレッジ: 未解決 slug 一覧、検出できなかった仮定の穴（function_reference_rate に影響する箇所）を TSV/JSON で出力。

## 3. フェーズ案
1. ベースライン調査: 既存 skeleton（assumption_trace.*, assumptions_overview.md）と `analysis/AI_USAGE.md` の UNKNOWN_REF_REQUESTS 運用を棚卸しし、必須フィールド一覧を固める。
2. スキーマ確定: `analysis/assumption_trace_schema.md` を補完し、eq_id/assumption_tags/config_keys/code_path/run_stage/tests の必須化・型を定義。欠損時のフォールバック（TODO slug）も明文化。
3. 抽出パイプライン PoC:
   - `analysis/equations.md` の (E.xxx) とラベルをパースし、eq_id 辞書を生成。
   - `analysis` 配下の docs と `marsdisk/` ソースを rg/AST で走査し、仮定候補（assumption_tags や TODO(REF:*)）を拾う。
   - YAML 設定（configs/*）からトグルキーとデフォルト値を抽出し、config_keys に紐付ける。
4. 集約・レンダー: 抽出結果を `assumption_registry.jsonl` に書き出し、レンダー関数で `assumption_trace.md` / `assumptions_overview.md` を再生成。未解決 slug はそのまま残す。
5. 検証・CI フック: doc_sync → analysis-doc-tests → evaluation_system を結合する make ターゲット（例: `make assumptions-autogen-check`）を追加し、function_reference_rate / anchor_consistency_rate が下がらないことを確認。

## 4. 技術メモ
- 解析手段: Python スクリプトで Markdown/py ファイルをパース（正規表現＋`ast`）。eq_id のパースはヘッダと `(E.xxx)` だけを対象とし、式本文は無視する。
- コード位置の解決: `analysis/inventory.json` のアンカーを優先利用し、ズレ検出時は DocSyncAgent に任せる。新規関数は `inventory.json` に追加される前提。
- 出典管理: 参照不明は `UNKNOWN_REF_REQUESTS.jsonl` に登録し、registry には `paper_ref: TODO(REF:slug)` を入れる。既存論文キーは `analysis/references.registry.json` に沿う。

## 5. リスクと緩和
- アンカーずれ・誤検出: DocSyncAgent 連動と `analysis/tools/check_docs.py --strict` で検査。誤検出を減らすため、スキャナは eq_id 未発見時に fail ではなく WARN で続行。
- スコープ膨張: 1D 拡散や paper 自動生成への派生は別プランに分離する。フェーズ 3 の PoC 完了をマイルストーンにして分岐可否を決める。
- 依存追加: 新規ライブラリが必要な場合は社内相談の上で最小化し、標準ライブラリ優先。

## 6. 直近の ToDo（作業順メモ）
- [ ] フェーズ1: `assumption_trace_gap_list.md` / `assumption_trace_schema.md` / `assumption_trace_data_sources.md` の現状確認と必須フィールド表の起こし。
- [ ] フェーズ2: スキーマ draft を更新し、必要な slug を UNKNOWN_REF_REQUESTS に登録。
- [ ] フェーズ3: PoC スクリプトを `analysis/tools/render_assumptions.py` 直下に追加し、registry に1件でも自動登録できることを確認（手動実行）。
- [ ] フェーズ4: レンダー出力を既存 docs と diff で確認し、coverage が下がらないことを `make analysis-doc-tests` で検証。
- [ ] フェーズ5: make ターゲットと CI 相当の手順書を追加（docs だけならローカル運用メモで可）。
