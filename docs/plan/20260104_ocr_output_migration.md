# OCR結果の出力置換プラン（pdf_extractor/outputs への移植）

目的と背景
---------
- `paper/ocr_references/` のOCR本文を正本として、`paper/pdf_extractor/outputs/<Key>/result.md` を置き換える。
- 置換時に明らかなOCR崩れ（改行、連結ミス等）を整形し、読みやすい完成版にする。
- 数式はOCR精度が低いため、**数式番号のみのプレースホルダ**に置換して後日手入力で補完する。

対象範囲
--------
- 対象: `paper/ocr_references/*.md` と `paper/pdf_extractor/outputs/*/result.md`
- 対象: Key 名の整合（必要ならファイル名のリネーム）
- 対象: 本文整形・数式プレースホルダ化

非対象範囲
----------
- 数式の内容復元（後日手入力のため本プランでは実施しない）
- 表データの復元（後日手入力のため本プランでは実施しない）
- 画像抽出の再処理（`images/` は現状維持）
- 文献の正誤・内容の事実確認（OCR整形のみ）

成果物
------
- `paper/pdf_extractor/outputs/<Key>/result.md` の本文が高精度OCRへ段階的に置換済み
- `paper/ocr_references/` は置換完了・追加作業の凍結後に削除予定（削除は完了判定後に実行）

更新頻度
--------
- OCR追加が発生したタイミングで随時更新する（最長でも月1回は対応表と保留リストを更新）
- 大量追加がある場合は「追加作業の波」を1スプリントとして区切り、完了確認まで実施する

数式プレースホルダ方針
----------------------
- ブロック数式・インライン数式ともに `[[EQN:(番号)]]` へ置換
- 式番号が明示されていない場合は `[[EQN:unnumbered]]` を使用
- 本文中の参照（例: “Eq. (2)”）はそのまま保持
- 置換時にOCR式を残したい場合は、直後に `<!-- OCR_EQN_RAW: ... -->` を追加（任意）
- 未番号の数式は **自動置換しない**。目視確認で `[[EQN:unnumbered]]` を挿入し、必要に応じてOCR原文をコメントで残す
- 表は `[[TABLE:(番号)]]` に置換し、表本文は削除する
- 表番号が明示されていない場合は `[[TABLE:unnumbered]]` を使用する

本文整形ルール（最小限・保守的）
--------------------------------
- ヘッダ/フッタ、ページ番号、印刷情報など「本文ではないもの」の除去
- ハイフン改行の復元と段落の連結整理（意味変更を伴わない範囲）
- 文字化けやOCR誤認の修正は「原文で確認できる場合のみ」
- 数式はプレースホルダ化（上記方針）
- 表本文は削除し、表番号プレースホルダのみ残す

ジャンク除去ルール（追加）
-----------------------
- `[image\d+]` のような画像参照のジャンクは除去する
- 連続した空行が3行以上続く場合は2行までに圧縮する
- 章節・段落と無関係な「孤立番号」（単独行の数字やページ番号の残骸）は削除する
- 図表/式番号の直前・直後にある単独数字/ローマ数字は除去対象外とする（例: Figure/Fig./Table/Eq. と連続する場合）
- ページ番号の単独行（例: `1`, `2`）は前後の空行条件を撤廃して除去対象とする（式行・図表行の番号補完と判断できる場合のみ保持）
- 5桁以上の単独数値は無条件で除去対象とする
- ジャーナル名・巻号・ページ範囲などが各ページで繰り返されるヘッダ/フッタは削除する（ただし1ページ目の表記は保持）
- ダウンロード/利用条件のバナー（例: `Downloaded from ... For personal use only`）やウェブ導線の定型文は除去する
- 出版社サイト案内の定型文（例: `Article published by ... and available at ...`）は除去する
- プレプリントの組版注記（例: `Preprint typeset using ...`）は除去する
- 章見出し直前/直後の単語断片や記号のみの行は削除する
- 迷う場合は除去せず変換ログに「保留」として記録する

ジャンク検出パターン（正規表現）
------------------------------
- `^\[image\d+\]\s*$` : 画像参照ラベル単体
- `^\[image\d+\]:\s*<data:image/[^>]+>\s*$` : base64 参照定義
- `^<data:image/[^>]+>\s*$` : data URI 行
- `^\s*\d+\s*$` : 単独の数字（ページ番号として優先除去。前後空行条件は撤廃し、式/図表行が数字を含まず補完が必要な場合のみ除外）
- `^\s*\d{5,}\s*$` : 5桁以上の単独数値（無条件で除去）
- `^\s*[IVXLCDM]+\s*$` : 単独ローマ数字（前後が空行の場合に除去対象）
- `^\s*[\W_]+\s*$` : 記号のみの行
- `^\s*table\s+\S+` : 表の開始行（表番号プレースホルダ化のトリガ）
- `.*Downloaded from .*personal use only.*` : アクセス/利用条件バナー
- `.*Downloaded from .*` : ダウンロード元の残骸
- `^\W*(Other articles in this volume|Top cited articles|Top downloaded articles|Our comprehensive search)\b` : Web導線のメニュー
- `^Click here for quick links\b` : Web導線の定型文
- `^Annual Reviews content online\b` : Web導線の定型文
- `^including:\s*$` : Web導線の残骸
- `^Article published by .*available at\b` : 出版社サイト案内
- `^Preprint typeset using\b` : プレプリント組版注記

ページマーカー検出/トリム
----------------------
- `\bpage\s+\d+\s+of\s+\d+\b` : 行末に付く場合は末尾部分のみトリムする
- `^\s*\d+\s*/\s*\d+\s*$` : ページ分母表記は単独行なら除去対象とする
- `^[A-Z]\d+,\s*page\s+\d+\s+of\s+\d+` : A11/A192 などの表記は末尾のみトリムする

メタ情報検出（除去せずフラグ）
--------------------------
- `\b(Received|Accepted|Revised|Available online)\b` : 受付日/採択日などのメタ情報
- `\bDOI:\s*\S+` / `\bdoi:\s*\S+` : DOI 行
- `\bhttps?://\S+` : URL 行
- `\bArticle ID\b` : 記事ID表記

繰り返しヘッダ/フッタ検出（ヒューリスティック）
----------------------------------------
- 同一行がページ数の30%超で反復し、ページマーカー近傍に出現する行はヘッダ/フッタ候補とする
- 1ページ目のジャーナル名/巻号/ページ範囲は保持し、2ページ目以降の反復のみ除去対象とする
- 行末に `page X of Y` が付く場合は末尾部分のみトリムし、行本体は候補判定に使う
- ScienceDirect/Elsevier/Downloaded from などの出版社ヘッダが反復する場合は同条件で除去対象とする
- 除去は「ジャーナル名/年/巻号/ページ範囲」または出版社ヘッダに合致する行に限定し、該当しない反復行は保持してログに残す

精度保証ポリシー（必須）
----------------------
- **情報の正確性を最優先**し、意味解釈を伴う修正は禁止（言い換え、要約、補完をしない）
- 数値/単位/化学式/固有名詞/記号の変更は原文照合必須（照合できない場合は変更しない）
- 迷う箇所は修正せず、変換ログに「保留」として記録する
- 可読性向上を目的とした改変は行わない（内容の保持を最優先）

修正許可基準（チェックリスト）
----------------------------
- 行末ハイフンの結合、単語分割の復元
- 明らかなOCR誤認の修正（例: l↔1, O↔0 など、原文で確認できるもの）
- 重複したヘッダ/フッタの削除
- 明確なレイアウト由来の空白/改行の整理
- 不明確な場合は「修正しない」が既定

検証・レビュー手順（必須）
------------------------
- 原則として**自動チェックのみ**を実施し、目視は例外対応に限定する
- 置換単位ごとに `result.raw.md` と差分を自動記録し、変換ログへ残す
- 自動サンプル検査は「重要文献」＋「ランダム」から最低5件を選び、ログに記録する
- 問題があれば当該Keyは保留リストへ移動し、再OCRまたは再整形を優先する
- 置換後にジャンク検出と段落連結の統計を自動で集計し、変換ログへ反映する
- 通常運用: `python -m tools.ocr_output_migration` 実行後に `pytest -q tests/integration/test_eqn_placeholder_guard.py` を流す（`make ocr-update` で一括）

自動検査の出力フォーマット
------------------------
- 出力先（Keyごと）: `paper/pdf_extractor/outputs/<Key>/checks/cleanup_report.json`
- 集計（任意）: `paper/pdf_extractor/outputs/_checks/cleanup_summary.csv`
- 監査（外部判定）: `paper/pdf_extractor/outputs/_checks/eqn_external_audit.tsv`
- cleanup_report.json の必須キー: `key`, `source_path`, `target_path`, `stats`, `junk`, `format_status`
- stats の必須キー: `line_count_before`, `line_count_after`, `paragraph_count_before`, `paragraph_count_after`, `paragraph_merge_count`, `hyphen_join_count`, `max_consecutive_blank_lines_before`, `max_consecutive_blank_lines_after`, `eq_placeholder_numbered`, `table_placeholder_numbered`, `table_placeholder_unnumbered`
- junk の必須キー: `found_by_pattern`, `removed_by_pattern`, `remaining_suspect_lines`, `repeated_header_footer_lines`, `repeated_header_footer_removed`, `page_marker_removed`, `page_marker_remaining`, `meta_flagged_lines`
- format_status は `clean` / `needs_review` / `blocked` を使用する

整形判定（format_status）基準
--------------------------
- clean: `remaining_suspect_lines==0` かつ `page_marker_remaining==0`
- needs_review: 上記条件を満たさず、本文が成立している場合
- blocked: `line_count_after < 0.5 * line_count_before` または `paragraph_count_after < 5`

変換ログの保存先/命名規則
-----------------------
- 変換ログ本体: `paper/pdf_extractor/outputs/<Key>/logs/convert_log.jsonl`
- 差分ログ: `paper/pdf_extractor/outputs/<Key>/logs/result.diff`
- JSONL の必須キー: `timestamp`, `key`, `source_path`, `target_path`, `raw_backup_path`, `diff_path`, `junk_removed_total`, `format_status`, `decision_notes`
- raw退避の命名: 既存の `result.raw.md` を維持し、追加の退避は `result.raw.<YYYYMMDD-HHMM>.md` とする

フェーズ（継続追加に対応）
------------------------
1. 対応表の作成（初回＋定期更新）
   - `paper/ocr_references/*.md` と `paper/pdf_extractor/outputs/*/result.md` のKeyを突合
   - 「両方あるKey / OCRのみ / outputsのみ」を継続的に更新
2. 置換作業（増分）
   - 両方あるKey: OCR本文を整形→`outputs/<Key>/result.md` に上書き
   - OCRのみ: `outputs/<Key>/result.md` を新規作成
   - outputsのみ: 置換対象外として保留リスト化（後日判断）
3. 数式プレースホルダ化（都度）
   - `[[EQN:(番号)]]` で統一、未番号は `[[EQN:unnumbered]]`
4. 完了確認（スプリント単位）
   - 追加分Keyの整合を確認
   - 重要文献はサンプル確認（数式位置・段落分割・見出し）
5. 後処理（凍結後）
   - `paper/ocr_references/` の削除は追加作業が落ち着いた段階で判断
   - `python tools/plan_lint.py` 実行

リスクと緩和策
--------------
- リスク: OCR誤りの「修正しすぎ」で意味が変わる
  - 緩和: 明らかなOCR崩れのみ最小限修正、判断に迷う箇所は原文維持
- リスク: 数式プレースホルダ位置のズレ
  - 緩和: 参照番号と周辺文脈の照合を優先し、位置が曖昧なら注記を残す
- リスク: outputsの上書きによる元データ消失
  - 緩和: 置換前に `result.md` を `result.raw.md` として退避（必要に応じて）

実装チェックリスト
-----------------
- [ ] Key対応表を更新し、分類（両方/OCRのみ/outputsのみ）を整理する
- [ ] 新規追加分のOCR本文を整形し、`outputs/<Key>/result.md` を更新する
- [ ] 数式を `[[EQN:(番号)]]` で置換する
- [ ] 置換後の自動品質チェック（段落/参照/数式位置）を実施する
- [ ] `checks/cleanup_report.json` を生成し、ジャンク検出/段落統計を記録する
- [ ] `logs/convert_log.jsonl` と `logs/result.diff` を残す
- [ ] 追加作業が落ち着いた時点で `paper/ocr_references/` の削除判断を行う
- [ ] `python tools/plan_lint.py` を実行する

追加ルール（明文化）
-------------------
- 受け入れ基準: Key整合率100%、数式プレースホルダ数の一致、サンプル検査での重大な崩れ無し、修正根拠の記録完了
- 変換ログ: 置換前後の差分ログ、修正箇所の根拠/判断理由メモ、`result.raw.md` の退避有無、ジャンク除去件数、整形判定、`logs/convert_log.jsonl` と `logs/result.diff` の保存
- 数式プレースホルダ仕様: `[[EQN:(番号)]]` の表記統一、番号不明時は `[[EQN:unnumbered]]`
- 文章修正の境界: 意味が変わる修正は禁止、OCR誤認が明白な場合のみ修正
- 表プレースホルダ仕様: `[[TABLE:(番号)]]` の表記統一、番号不明時は `[[TABLE:unnumbered]]` を使用する
- 図表/脚注の扱い: 表本文は削除し、表番号のみ維持する。脚注番号は残し本文と整合
- 置換対象外の扱い: outputsのみは保留リスト化、OCRのみは新規作成方針を明記
- サンプル検査: 代表5件（重要文献+ランダム）の**自動**点検項目（段落連結/式位置/見出し）
- 削除タイミング: `paper/ocr_references/` は検査完了・バックアップ後に削除
- 例外対応: 複数論文混在や式番号欠損時の処理ルール
- トレーサビリティ: 変換ログに元ファイル/日付/ハッシュを記録し、追跡可能にする
- 原文退避/復元性: `result.raw.md` を保存し、追加の退避は `result.raw.<YYYYMMDD-HHMM>.md` を作成する
- 正規化: UTF-8/NFC、改行コードLF、連続空白の扱いを統一する
- 表・図・脚注: 表ブロックは削除し、表番号のみ維持する。脚注番号は維持し本文と整合させる
- 数式置換の棚卸し: `[[EQN:...]]` と `[[TABLE:...]]` 一覧をKey単位で記録する
- 品質ステータス: Keyごとに `clean`/`needs_review`/`blocked` を付与する
- 混在検出: タイトル/著者/誌名の不一致があれば保留リスト化する
- ページ欠落検知: 参考文献/末尾セクション有無で欠落を簡易検知する
- Key整合監査: bibliography/registryと不一致のKeyは保留＋記録する
- 権利/配布: 共有制限のある文献は外部共有しない運用を明記する

具体的な作業手順（チェックボックス）
--------------------------------
- [ ] 1. Key対応表を更新し、`paper/ocr_references` と `paper/pdf_extractor/outputs` の突合一覧を作る
- [ ] 2. 追加分のKeyを識別し、着手順の優先度（重要文献/頻出参照）を付与する
- [ ] 3. 各Keyごとに `outputs/<Key>/result.md` を `result.raw.md` として退避する
- [ ] 4. OCR本文を読み込み、ヘッダ/フッタ/ページ番号を削除する
- [ ] 5. ハイフン改行・段落分断を整形し、明確なOCR誤認のみ修正する
- [ ] 6. 数式を `[[EQN:(番号)]]` または `[[EQN:unnumbered]]` に置換する
- [ ] 7. 表を `[[TABLE:(番号)]]` または `[[TABLE:unnumbered]]` に置換し、表本文を削除する
- [ ] 8. `outputs/<Key>/result.md` を置換し、差分ログを記録する
- [ ] 9. 追加分から代表5件を自動サンプル検査（段落連結/式位置/見出し/脚注）する
- [ ] 10. OCRのみ/outputsのみのKeyを保留リストに整理する
- [ ] 11. 追加作業が落ち着いた時点で `paper/ocr_references/` 削除を判断する
- [ ] 12. `python tools/plan_lint.py` を実行し、結果を記録する

進捗ログ
--------
- 2026-01-04: プラン作成
