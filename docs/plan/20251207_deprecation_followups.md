廃止キー撤去フォローアップ（短期タスク）
=====================================

背景と目的
----------
- `20251207_deprecation_migration.md` に従い、旧キー（geometry.r/temps.T_M/single_process_mode 等）をコード・設定・テストから完全排除する仕上げを行う。
- 既存のコード変更後に残存する参照とテスト失敗を解消し、新モード（physics_mode、disk.geometry、radiation.TM_K）へ統一する。

スコープ
--------
- 含む: scripts/tests の旧キー参照解消、run_zero_d シグネチャ追随、config/analysis の移行ポリシー反映。
- 含まない: 新規物理機能の追加、解析図の再生成。

TODO（優先順）
--------------
1. スクリプト/テストの追随  
   - `scripts/run_inner_disk_suite.py`、`run_inner_disk.sh`、`sweep_*` 系を `physics_mode`/`disk.geometry`/`radiation.TM_K` 基準に修正。  
   - 全テストで `single_process_mode` 依存を `physics_mode_override` に置換、期待フィールドを物理モード表記に更新。
2. 残留キーの掃除と設定整合  
   - `rg "geometry.r|temps.T_M|single_process_mode|phase.map|qpr_table|phi_table"` をリポジトリ全体に実行し、残存箇所を新キーへ置換。  
   - configs 配下が `disk.geometry` と `radiation.TM_K` のみで動くことを再確認。
3. ドキュメント更新と同期  
   - `analysis/overview.md` などに移行ポリシーを反映し、旧キー無効化を明記。  
   - DocSyncAgent → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` のバンドル実行。
4. 回帰テスト  
   - `pytest` を一通り実行し、`run_zero_d` 引数変更由来の失敗を修正。  
   - 必要に応じてサンプルランで `summary.json`/`run_config.json` のフィールドを確認。

リスクと緩和
------------
- テスト期待値ずれ: 物理モード表記変更による snapshot 破綻は逐次更新し、差分理由を記録。  
- 見落とし残存キー: `rg` で全域検索し、CI 失敗で気付けるよう早期に修正。  
- DocSync漏れ: ドキュメント変更時は必ず DocSyncAgent 実行を手順に組み込む。

完了判定
--------
- 旧キー参照が `rg` でヒットしない。  
- `pytest` が通り、`run_zero_d` 呼び出しは `physics_mode_override` に統一。  
- DocSync + doc テスト + evaluation_system が成功し、analysis で新ポリシーが明文化されている。
