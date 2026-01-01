# paper/ ディレクトリ運用メモ（ローカルのみ）

目的
----
- 論文草稿や PDF などをローカルで一時保管するワーク領域として `paper/` を使う。
- Git 追跡外で運用し、リポジトリ本体の履歴を汚さない。

追跡ポリシー
------------
- `.git/info/exclude` に `/paper/` `/paper/*.md` を登録済み。Git 管理下に載せない。
- 共有や提出が必要な場合は別ストレージや専用ブランチで扱い、本リポジトリには追加しない。

推奨レイアウト（ローカル専用）
------------------------------
- `paper/references.bib`：`python -m tools.reference_tracker export-bibtex -o paper/references.bib` で生成。registry をソースにする。
- `paper/references/`：実際の文献 PDF を格納。ファイル名はキー基準を推奨（例: `StrubbeChiang2006_ApJ648_652.pdf`）。
- `paper/draft*.md` など草稿が必要ならここに置く（Git には載らない）。

運用フロー（例）
----------------
1. 文献キーを registry (`analysis/references.registry.json`) に追加・更新する。
2. BibTeX を再生成: `python -m tools.reference_tracker export-bibtex -o paper/references.bib`
3. 必要な PDF を `paper/references/` に配置（キー名で命名）。ライセンスに留意し、配布禁止版は共有しない。
4. コードや analysis に文献を使う場合は `[@Key]` 形式で引用し、DocSync/analysis-doc-tests を回す。

注意点
------
- `paper/` 配下のファイルは CI・テスト対象外。バックアップは各自で管理する。
- registry と `paper/references/` の整合は手動管理。欠けていてもビルドは通るが、草稿生成時に参照不備が起きないよう定期的に整理する。
