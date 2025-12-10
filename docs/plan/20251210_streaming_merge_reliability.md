目的と背景
---------
- `io.streaming.merge_at_end=true` で途中終了した場合にチャンク統合が走らず、`series/run.parquet` や `summary.json` が欠落する問題が temp_supply_sweep で顕在化。将来のスイープ解析への影響が大きいため、統合リカバリと再発防止を計画する。

対象範囲
--------
- `marsdisk/run.py` のストリーミング書き出し経路と終了処理（`merge_chunks` 呼び出し）。
- `scripts/research/run_temp_supply_sweep.cmd` など streaming を前提にするスイープ実行スクリプト。
- 残存チャンクの事後統合・検出を行う補助スクリプト/CLI。

非対象
------
- 物理モデルや数値スキームの変更は行わない。
- ストレージ圧縮形式・列定義の刷新は後続検討とし、今回の修正では手を入れない。

フェーズ/タスク案
----------------
1. 現状調査: `run_zero_d` の例外経路で `merge_chunks` がスキップされる箇所を特定し、再現ケースを最小化する。テスト用に短尺 run を用意。
2. リカバリ導線: 残存チャンクを検出し、`run.parquet`/`diagnostics.parquet`/`psd_hist.parquet` を再結合する CLI または `make` ターゲットを追加。出力先の整合（summary/run_config の有無）も確認する手順を記述。
3. 終了処理強化: `run_zero_d` の終了ブロックを `try/finally` で包み、例外時でも `flush`/`merge_chunks` を試行するか、少なくとも実行ログに再結合手段を出す。必要なら mass_budget/summary の出力順を見直す。
4. 回帰テスト: pytest でストリーミング ON + 意図的例外を投げるモックを組み、チャンクが残っても merge ヘルパーで復元できることを検証。CI 追加も検討。
5. ドキュメント更新: `analysis/run-recipes.md` か README にリカバリ手順を追記し、DocSyncAgent → analysis-doc-tests → evaluation_system の標準手順を実行。

リスクと緩和
------------
- 例外時の再結合で schema 不一致があると失敗する可能性: マージ前に列一致を検査し、差分があれば警告ログを出してスキップしないようにする。
- 大規模チャンクの再結合でメモリ圧迫: `ParquetWriter` をストリーミングする現行方式を維持し、メモリを食わない順次マージとする。

完了条件チェック
----------------
- 例外終了してもチャンクが残ればリカバリ CLI で `run.parquet` 系を生成でき、summary/mass_budget が揃うことを手元テストで確認。
- 正常終了時は従来通り自動マージされ、余分なチャンクが残らないことを確認。
- 関連ドキュメントを更新し、DocSyncAgent → analysis-doc-tests → evaluation_system を通過。
