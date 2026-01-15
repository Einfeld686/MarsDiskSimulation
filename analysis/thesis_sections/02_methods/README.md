# thesis/methods.md 分割ソース（本文5本＋付録）

このディレクトリの `*.md` は `analysis/thesis/methods.md` の編集用ソースです。
番号付きの分割ファイル（`[0-9][0-9]_*.md`）は結合対象として Git 管理します。

<!--
実装(.py): marsdisk/run.py, marsdisk/run_zero_d.py, marsdisk/run_one_d.py
-->

`analysis/thesis_sections/02_methods/manifest.txt` がある場合はその順序で結合し、なければ番号順で結合します。

再生成:

```bash
python -m analysis.tools.merge_methods_sections --write
```

注意:
- `README.md` は結合対象外です。
- 章の追加や並び替えが必要になった場合は `manifest.txt` を編集してください。
- スタイル規約は `analysis/thesis/STYLEGUIDE.md` を参照してください。

このセットについて:
- 本文は「5章」（00〜04）にまとめ、付録は別ファイル（05〜09）に分離しています。
- 既存の文章・式は変更せず、ファイル境界（分割単位）だけを揃えています。
