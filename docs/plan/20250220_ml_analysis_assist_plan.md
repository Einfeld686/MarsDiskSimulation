# ML 補助プラン（analysis 限定）

> **目的**: コードを改変せず、analysis ドキュメントとレビュー効率を ML で補助する。すべて警告・提案のみで、人間レビュー必須。

## 0. 共通方針
- 適用範囲は `analysis/` と生成レポートのみ。数値コード・物理式の自動変更禁止。
- 出力は警告/提案リスト（CI非ブロック）。自動確定しない。
- 依存: scikit-learn（既導入）、joblib（バンドル済み）。キャッシュは `.cache/doc_sync/` 配下。

## 1. 式↔コードマップ優先度付け強化
- 入力: equations サブコマンドのパーサー出力、inventory。
- 特徴: TF-IDF 類似度、ファイル名一致、シンボル名の部分一致、過去レビュー履歴（既存 eq_map との差分）。
- モデル: 既存 TF-IDF + cosine に LogisticRegression を重ね、未マップ式に優先スコアを付与。
- 出力: `analysis/equation_code_map.json` に `ml_suggested_refs`（score/confidence/priority）として追記。`provenance_report.md` に「要レビュー」小節を追加（警告のみ）。

## 2. 文献・用語ゆれ統合の提案
- 入力: `analysis/glossary.md` `analysis/literature_map.md` の見出し・別名列。
- 処理: TF-IDF/BM25 で類似クラスタを作り、表記ゆれ候補を抽出。
- 出力: `analysis/outputs/<glossary_suggestions>.json` を新設し、統一候補と信頼度を警告として記録。自動置換しない。

## 3. アンカー異常検知
- 入力: doc_refs + inventory 行範囲。
- 特徴: アンカー長（行数）、重複回数、逆順/欠損のフラグ。
- モデル: IsolationForest（軽量）で外れ値スコアを算出。
- 出力: `analysis/outputs/<anchor_anomalies>.json` に警告リスト。CI非ブロック、DocSyncレポートに統合。

## 4. 実行ログの外れ値フラグ
- 入力: `out/<run_id>/series/*.parquet` の統計列（mass_budget_error, dt_over_t_blow など）。
- 特徴: 時系列の分位点、ステップ間差分。簡易標準化のみ。
- モデル: IsolationForest または IQR ルールで外れ値検知。
- 出力: `out/<run_id>/run_card.md` 補助用の `out/<run_id>/checks/anomaly_flags.json` を生成（分析用、Git無視）。analysis には集計サマリだけを参照で追記。

## 5. 未参照シンボルの優先度付け
- 入力: coverage holes（unreferenced functions）、docstring、パス。
- モデル: TF-IDF 類似度 + ルール（physics/io/run）で重要度スコアを計算。
- 出力: `analysis/outputs/<coverage_priorities>.json` に順位付きリストを生成。autostub は従来どおり手動。

## 実装フェーズ
1. 式↔コード優先度（本プランの最優先）: equation_matcher を拡張し、score/confidence/priority を eq_map に出力。DocSync `--with-ml-suggest` のデフォルト警告運用を維持。
2. アンカー異常検知 + 未参照シンボル優先度: doc_sync_agent にオプション追加、json 出力を analysis 配下に保存。
3. 用語ゆれ/文献統合の提案: glossary/literature_map を読み、提案JSONを生成するサブコマンドを追加。
4. 実行ログ外れ値: analysis/run-recipes.md に追記し、出力は Git ignore。CI 非ブロックを徹底。

## 安全策
- すべての ML 出力は「警告・提案」のみ。自動書き換えや CI fail は禁止。
- 新しい JSON 出力は analysis への参照に留め、物理コード・式ファイルは不変。
- パラメータ（閾値/top-K）を CLI 引数で明示し、デフォルトは保守的に設定。
