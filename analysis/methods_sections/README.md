# methods.md 分割ソース

このディレクトリの `*.md` は `analysis/methods.md` の編集用ソースです。
番号付きの分割ファイル（`[0-9][0-9]_*.md`）はローカル運用のために Git から除外します。
`analysis/methods_sections/manifest.txt` がある場合はその順序で結合し、なければ番号順で結合します。

再生成:

```bash
python -m analysis.tools.merge_methods_sections --write
```

注意:
- `README.md` は結合対象外です。
- 章の追加や並び替えが増える場合は `manifest.txt` を編集してください。
