廃止予定キーの撤去計画（暫定）
================================
ステータス: 計画（暫定）

目的
----
非推奨の設定キー・互換ルートを段階的に撤去し、`physics_mode` と新スタイルの入出力へ一本化する。破壊的変更の影響を最小化し、CI とサンプル設定の両方が移行後も通る状態を保証する。

対象となる非推奨項目
--------------------
- ジオメトリ: `geometry.r`, `geometry.runtime_orbital_radius_rm`
- 温度: `temps.T_M`
- 物理モード: `single_process_mode`, `modes.single_process`, `process.primary`
- フェーズマップ: `phase.map.entrypoint`
- テーブル: `radiation.qpr_table`, `shielding.phi_table`

進め方（フェーズ分割）
--------------------
1. **現状調査と洗い替え**  
   - 全設定・スクリプト・テストでの使用箇所をリスト化し、新キーへの置換パッチを準備する（`rg` で検出済みパスを確認）。  
   - 置換ポリシーを README/analysis ではなく `analysis/overview.md`/`analysis/equations.md` に追記し、DocSync と doc テストを走らせる。
2. **設定ファイルの一括移行**  
   - `configs/` 配下を新キーへ置換（例: `geometry.r` → `disk.geometry.r_in_RM`/`r_out_RM`、`temps.T_M` → `radiation.TM_K`）。  
   - スイープ系スクリプトの生成ロジックも新キーを吐くよう更新。  
   - 互換キーは一時的に残しつつ、設定側が旧キーを使わなくなることを CI で確認。
3. **テストと解析ユーティリティの更新**  
   - `tests/` で旧キーを使うケースを新キーへ修正し、期待値が変わる場合は差分を説明。  
   - `marsdisk/analysis/` 配下のサンプラー類も新キーへ修正し、回帰データの再生成が必要ならスコープを明記。
4. **コード本体の互換ルート削除**  
   - `schema.py` の旧フィールド定義・バリデータ・警告を削除し、`run_zero_d.py` のフォールバックロジックも撤去。  
   - 旧キーを受け付けないバリデーションを追加し、エラーメッセージに移行先を明記。  
   - `config_validator.py` など補助バリデータから旧キー分岐を除去。
5. **仕上げとガード強化**  
   - DocSyncAgent → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を一連で実行し、coverage とアンカー健全性を確認。  
   - CI で旧キーを含む入力が失敗することを確認する回帰テストを追加し、破壊的変更が意図的であることを明文化。

リスクと緩和策
-------------
- **外部ユーザー設定の破壊**: 互換ルート削除前にリリースノートを用意し、移行ガイドを `README` に短く追記する。  
- **解析スクリプトの取り残し**: `scripts/` と `marsdisk/analysis/` を一括 grep し、MR でチェックリスト化。  
- **ドキュメントの整合性低下**: DocSync/coverage を必須ステップにし、アンカー崩れを即検出。

実行順チェックリスト
------------------
- [ ] 設定置換パッチを準備し、旧キーが configs/ に残らないことを `rg` で確認。  
- [ ] テスト入力を新キーへ更新し、`pytest` 完走を確認。  
- [ ] `run_zero_d.py`/`schema.py`/`config_validator.py` から互換分岐を削除。  
- [ ] DocSyncAgent → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を連続実行。  
- [ ] リリースノート/README に移行ガイドを追記。
