# 20251208 analysis doc update

目的
- 20251207_deprecation_followups.md で挙げた旧キー排除を analysis 側に反映し、ドキュメントとサンプル出力を現行スキーマ（disk.geometry / radiation.TM_K / physics_mode_override）へ統一する。
- DocSync と coverage の基準（function_reference_rate >=0.75, anchor_consistency_rate >=0.98）を維持したまま evaluation_system まで流す手順を固定する。

スコープ
- 含む: analysis/run-recipes.md・analysis/equations.md・analysis/assumption_trace.md・analysis/slides_outline.md の記述更新、analysis/outputs/* のサンプル再生成、DocSyncAgent→analysis-doc-tests→evaluation_system の実行とログ化。
- 含まない: コード側の新機能追加、計算結果の大量再生成（必要最低限のサンプル差し替えのみ）。

タスクと順序
1. 旧キー記述の洗い出し確認  
   - `rg "geometry.r|temps.T_M|single_process_mode|phi_table\\b|qpr_table\\b" analysis` を基準に差分対象をリスト化（run-recipes/equations/assumption_trace/slides_outline を主対象）。
2. ドキュメント更新  
   - run-recipes: サンプル YAML と CLI フラグを disk.geometry.*, radiation.TM_K, physics_mode_override に書き換え、旧キーは「使用不可」注記のみに整理。  
   - equations: T_M_source の説明から temps.T_M を削除し、現行優先順位に更新。  
   - assumption_trace: 半径入力の優先順位を disk.geometry 優先に修正し、legacy key を「無効/非推奨」と明示。  
   - slides_outline: S07 の key_points_draft から `phi_table` を除去し `shielding.table_path` に統一。
3. サンプル出力差し替え  
   - 現行バイナリで `analysis/outputs/{summary.json,run_config.json,baseline_blowout_only/*}` を再生成し、T_M_source/r_source/single_process_mode など旧フィールドを排除。
4. 同期・検証バンドル  
   - `make analysis-sync` → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>`（直近の出力パスを指定）を連続実行。  
   - coverage 指標を確認し、しきい値未達なら追加参照を補う。
5. 記録  
   - 実行コマンドと結果を当プランに追記し、必要なら関連 Issue/PR に転記。

リスクと緩和
- サンプル出力更新に伴うアンカーずれ: DocSyncAgent 直後に doc テストを必ず実行。  
- coverage 低下: 参照不足が出た場合は equations/overview への参照追加で対処。  
- 再生成コスト: 最小限のサンプルのみ更新し、大規模 run 再計算は避ける。

完了条件
- analysis 内に旧キー参照が残らず、最新スキーマの説明に統一されている。  
- DocSyncAgent + analysis-doc-tests + evaluation_system が成功し、しきい値を満たす。  
- 本ファイルに実行ログが追記されている。
