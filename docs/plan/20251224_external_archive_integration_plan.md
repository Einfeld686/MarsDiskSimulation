# 目的
- 内部SSD(約1TB)の制約下で、27パターン総量~4.5TB規模のシミュレーション出力を安定運用できるようにする。
- 1パターン完了後の最終フェーズ（ストリーミングチャンクの統合・図生成・集計）をトリガに、外部HDDへ安全に移行/保管する仕組みを既存ランナーへ統合する。

# 背景
- 現行の `out/<run_id>/...` 直下にチャンク/統合Parquet/図を保存する運用では、全パターン完走後の移動が内部SSD容量を超過する（run_id は `<timestamp>...` 形式）。
- ストリーミング書き出しは既に前提となっており、`merge_at_end` での統合タイミングに合わせたアーカイブが自然な切り分け点。
- 統合Parquet自体は既存実装で対応済み（streaming の `merge_at_end` で `out/<run_id>/series/run.parquet` 等を生成）。

# 方針（推奨アーキテクチャ）
- **最終フェーズ（post_finalize）でアーカイブ**を起動し、図生成後に外部HDDへコピーしたうえでローカルの大容量データを削除または最小化する。
- **統合Parquetは外部HDD出力を既定**とし、`merge_target=external` を標準運用とする。
- **安全性優先**: 整合性検証は「標準+」を既定とし、失敗時はローカル保持を継続する。

# 外部HDD接続性（実装チェック項目）
- [x] マウント確認: 設定した `io.archive.dir` が存在し、書き込み可能であることを事前チェックする。
- [ ] ボリューム同定: 期待するボリューム名/UUID と一致するか検証し、誤ったディスクへの書き込みを防ぐ。
- [x] 空き容量判定: アーカイブ対象サイズ + 余裕分（例: 10%）を満たすか確認する。
- [x] 断線/スリープ検知: コピー中の I/O エラーを捕捉し、`INCOMPLETE` マーカーで再開可能にする。
- [x] パフォーマンス記録: コピー総量と所要時間/速度をログに残す。
- [x] 低速デバイス警告: 閾値を定めて警告を出す（throughput が閾値未満で警告）。
- [x] パス永続化: `out/<run_id>/run_card.md` に実際の保存先を記録する。
- [x] ボリューム情報記録: `out/<run_id>/run_card.md` にボリューム名/UUID などの識別情報を追記する。
- [x] Windows向け: `io.archive.dir` はドライブレター/UNC の絶対パス前提で解決し、解決後の実パスをログに残す。
- [x] `io.archive.enabled=true` の場合は `io.archive.dir` の明示指定を必須とし、未指定なら設定エラーで停止する。

# 5点の方針（合意済み）
- アーカイブのタイミング: 図生成完了後の `post_finalize` を既定とする。
- 移動方式とローカル保持: `mode=copy` + 検証後削除、`keep_local=metadata` を既定とする。
- 整合性検証の厳密さ: 既定は「標準+」（manifest + 主要成果物ハッシュ + Parquetメタ検証）。
- 失敗時の扱い: アーカイブ失敗は警告で継続し、`INCOMPLETE` を残して再試行可能にする（厳格モードは別途）。
- アーカイブ先の構造: `out/<run_id>/...` と同一命名で外部HDDへミラーし、`out/<run_id>/run_card.md` に `archive_path` とボリューム情報を記録する（run_id は `<timestamp>...` 形式）。
- 明示指定必須: `io.archive.enabled=true` の場合は `io.archive.dir` を必ず指定する。

# Windows運用補足（明示パス運用）
- Windows runset は `--config`/`--overrides`/`--out-root` を明示指定する前提で運用しているため、アーカイブも `io.archive.dir` を overrides で明示的に指定する。
- `io.archive.dir` は `<archive_root_windows>` を固定値として運用し、ドライブレター付き絶対パスで指定する（相対パスや `~` 展開には依存しない）。
- 外付けHDDの保存先は `<archive_root_windows>` に固定する。
- `out/<run_id>/run_card.md` には指定値と解決後の実パスの両方を記録する（Windowsのパス解決差異を吸収するため）。
- `io.archive.enabled=true` の場合は `io.archive.dir` 未指定を許可しない（runset 側で必須化）。

# 整合性検証（標準+）の実装チェック項目
- [x] manifest を出力し、ファイル数・サイズ・mtime を記録する。
- [x] 小さな成果物（`out/<run_id>/summary.json`/`checks/*.csv`/`out/<run_id>/run_card.md`/図ファイル）はハッシュ一致を確認する。
- [x] 統合Parquetは `schema_hash`/`row_count`/`row_group_count` を比較する。
- [x] チャンク合算行数と統合Parquet行数の一致を検査する。
- [x] Parquetの先頭/末尾row groupを読み込み、簡易チェックサムで実読検証する。
- [x] 整合性検証が合格した場合のみローカル削除を許可する。

# verify_level 判定項目メモ
- `standard`: manifest（ファイル数/サイズ/mtime）+ 主要成果物の存在確認（`out/<run_id>/summary.json`/`checks/*.csv`/`out/<run_id>/run_card.md`/統合Parquet）。
- `standard_plus`: `standard` + 主要成果物のハッシュ一致 + 統合Parquetの `schema_hash`/`row_count`/`row_group_count` + チャンク合算行数一致 + 先頭/末尾row groupの簡易チェックサム。
- `strict`: `standard_plus` + 全ファイルのハッシュ一致 + Parquet全row groupの読み込み検証。

# スコープ
- 0D/1D ランナーの終了処理（ストリーミング統合・図生成・summary/run_card 出力）にアーカイブフックを追加。
- 設定スキーマにアーカイブ設定を追加し、CLI/環境変数で上書き可能にする。
- アーカイブ用のユーティリティ（コピー/移動、検証、再試行）を新設する。

# 非対象
- 物理モデルや数値スキームの変更。
- 既存の出力フォーマット（Parquet列やJSON構造）の刷新。
- 外部HDD上での逐次チャンク書き込み（性能/信頼性の検討は別タスク）。

# 実装ステップ
1. [ ] **要件整理とサイズ見積もり**: 1パターンの最大出力量（チャンク総量・統合Parquet・図）を測定し、内部SSDで保持可能な上限を把握する。
2. [x] **設定/CLI 追加**: `io.archive` ブロックをスキーマに追加。CLI では `--archive-dir` 等を許可し、環境変数で明示的に無効化できるようにする。
   - [x] `io.archive.enabled=true` かつ `io.archive.dir` 未指定は設定エラーにする。
3. [x] **アーカイブユーティリティ**: `marsdisk/io/archive.py` を追加し、(a)コピー/移動、(b)manifest/ハッシュ生成、(c)再試行/中断検知（INCOMPLETE マーカー）を実装。
4. [x] **終了処理へのフック**: `run_zero_d.py` / `run_one_d.py` の post_merge/post_finalize にアーカイブ呼び出しを追加。流れは以下を想定。
   - [x] チャンクのフラッシュ/統合（既存フロー）
   - [ ] 図生成（必要なら統合Parquetを参照）
   - [x] summary/run_card を確定（既存フロー）
   - [x] アーカイブ（標準+検証に合格後、ローカル削除 or 最小化）
5. [x] **二重持ち回避オプション**: `merge_target=external` を実装し、統合Parquetの出力先を外部HDDに切り替えられるようにする。図生成の参照先も連動させる。
6. [x] **失敗時フォールバック**: 外部HDD未接続・空き不足・コピー失敗時はローカル保持に戻し、次回再試行できる状態を残す。
7. [ ] **ドキュメント更新**: README/run-recipes/analysis に運用手順と注意点（外部HDD未接続時の挙動、再試行方法）を追記。
8. [x] **Windows runset 対応**: `scripts/runsets/windows/overrides.txt` へ `io.archive.*` を明示追記し、`--out-root` と同様に絶対パス運用を徹底する。

# 設定キー案（実装対象）
- [x] `io.archive.enabled` (bool, default false): アーカイブ有効化。
- [x] `io.archive.dir` (str, required when enabled): 外部HDDのルート（例: `<archive_root>`）。未指定なら設定エラー。
- [x] `io.archive.mode` (str, default "copy"): `copy`/`move` を選択。
- [x] `io.archive.trigger` (str, default "post_finalize"): `post_finalize` / `post_merge` など最終フェーズのフック位置。
- [x] `io.archive.merge_target` (str, default "external"): `local` / `external`。
- [x] `io.archive.verify` (bool, default true): `false` で検証を無効化。
- [x] `io.archive.verify_level` (str, default "standard_plus"): `standard` / `standard_plus` / `strict`。
- [x] `io.archive.keep_local` (str, default "metadata"): `none`/`metadata`/`all`。
- [x] `io.archive.record_volume_info` (bool, default true): run_card にボリューム識別情報を記録する。
- [x] `io.archive.warn_slow_mb_s` (float, default 40.0): 低速警告の throughput 閾値（MB/s）。
- [x] `io.archive.warn_slow_min_gb` (float, default 5.0): 警告判定を行う最小転送サイズ（GB）。
- [x] `io.archive.min_free_gb` (float, optional): 内部SSDの空きが不足したら早期アーカイブを促す。
- [x] 環境変数: `IO_ARCHIVE=off` で強制無効化（CI/pytest向け）。

# エラー処理/リカバリ設計
- [x] **外部未接続**: `ARCHIVE_SKIPPED` マーカーを作成し、ローカル保持で終了。
- [x] **中断/失敗**: `INCOMPLETE` マーカーと途中manifestを残し、再実行で `--archive-resume` を可能にする。
- [x] **整合性検証**: アーカイブ後に `out/<run_id>/run_card.md` へ `archive_path` と `manifest_hash` を記録。

# テスト計画
- [x] 単体: `archive.py` の copy/move/verify を小規模ディレクトリで検証（ローカル一時ディレクトリで実施）。
- [x] 結合: streaming ON の短尺 run を実行し、アーカイブ後に外部HDD側で `out/<run_id>/summary.json`/`out/<run_id>/checks/mass_budget.csv`/`series` が揃うことを確認（ローカルアーカイブ先で検証）。
- [x] 二重持ち回避: `merge_target=external` でローカルに統合Parquetが残らないことを検証（短尺 run で確認）。
- [x] 失敗時: 外部パスが存在しない場合に `ARCHIVE_SKIPPED` が生成され、ローカルにデータが残ることを確認（短尺 run で確認）。
- [x] 設定検証: `io.archive.enabled=true` かつ `io.archive.dir` 未指定で設定エラーになることを確認。

# 完了条件（案）
- [x] パターン実行後、最終フェーズで自動アーカイブが走り、外部HDDにフルセットが移行される（短尺 run でフローを確認）。
- [x] ローカル側は `keep_local` 設定に従って最小化され、内部SSDの占有が抑制される（keep_local=metadata で確認）。
- [x] 外部未接続/失敗時に安全にローカル保持へフォールバックする（`ARCHIVE_SKIPPED` で確認）。
