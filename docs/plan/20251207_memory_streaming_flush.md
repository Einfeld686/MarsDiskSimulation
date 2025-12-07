# 目的
- 0D シミュレーションの履歴を全メモリ保持せず、概算メモリ 80 GB 超でチャンク書き出しに切り替える仕組みを実装する。
- `--quiet --progress` を標準有効とし、開始時にメモリ見積りを提示したうえで自動フラッシュする運用に移行する。

# スコープ
- 0D ランナー（`run_zero_d` 系）の履歴管理・I/O まわり。
- 出力フォーマットは Parquet（pyarrow, snappy 既定）。
- ステップ間隔固定フラッシュではなく、メモリ/ステップ閾値をトリガにするハイブリッド方式。
- analysis 文書やスキーマの更新は別タスクとする。

# 非対象
- Smol カーネルのスパース化や I/O レイアウトの全面変更。
- 1D 拡張・phase7 診断の仕様変更。

# 実装ステップ
1. **閾値設定とフラッシュ条件**: `ZeroDHistory` あるいはランナーに、推定メモリとステップ数の閾値（例: 80 GB 相当、補助で 1 万ステップ）を設定可能にするフックを追加。run/psd/diagnostics を同じステップ範囲でまとめてフラッシュし、対応リストをクリア。
2. **Parquet チャンク書き出し**: `io.writer` へ `append_parquet_chunk(path, df, schema_hint, compression="snappy")` のようなユーティリティを追加し、初回スキーマを固定して連番ファイル（`run_chunk_0001.parquet` 等）へ追記する。NaN 埋めで欠損列を保持し、型ブレを防ぐ。最後に統合ビュー用メタ（チャンク一覧）を残す。
3. **進捗・メモリ表示**: `ProgressReporter` のヘッダに推定メモリと現在のバッファ使用概算を表示し、フラッシュ実行時にログを出す。`--quiet --progress` を標準 on にする CLI デフォルトを検討。
4. **クリーンアップと集約**: 終了時に残バッファをフラッシュし、（オプションで）チャンクを 1 本にマージするか、ディレクトリ読み込み手順を summary に記録。異常終了でも読めるよう、チャンク名にステップ範囲を含める。
5. **設定とドキュメント**: 閾値・チャンクサイズ・圧縮方式の設定キーを追加する場合は YAML/スキーマを拡張し、README/analysis に利用手順を追記。オプトアウトフラグも検討。

# 設定キーのたたき台
- `io.streaming.enable` (bool, default false): true でチャンクフラッシュを有効化し、`--quiet --progress` も自動で on。
- `io.streaming.memory_limit_gb` (float, default 80.0): 推定メモリ上限。超過でフラッシュ。
- `io.streaming.step_flush_interval` (int, default 10000): ステップ間隔の補助トリガ。
- `io.streaming.compression` (str, default "snappy"): Parquet 圧縮方式。
- `io.streaming.merge_at_end` (bool, default false): 終了時に単一ファイルへマージする優先度。false ならチャンク集合で読み出す。
- `io.streaming.opt_out` (bool, default false): true で従来の全保持モードに戻す（緊急回避用）。

# ロールバック/オプトアウト方針
- フィーチャフラグ（`io.streaming.enable` または `opt_out`）で全体を無効化できるようにし、不整合や性能退行が出た場合すぐ戻せるようにする。
- マージは必須ではなく低優先度（merge_at_end=false既定）。後段が必要なときだけ on にする。

# フラッシュタイミング詳細
- 毎ステップまたは一定ステップ間隔で「推定バイト数 > memory_limit_gb」または「steps_since_flush ≥ step_flush_interval」で発火。
- 発火時は run/psd/diagnostics を同じステップ範囲でまとめて書き出し、チャンク名に `start_end` を付与。
- バッファクリア後、ステップカウンタをリセットして次の閾値判定へ進む。

# パフォーマンス目標（暫定）
- 1e5 ステップ・40ビン規模で、ストリーミング有効時の wall time 増が +50% 以内。
- 1チャンク書き出し（~150 MB 想定）が 1 秒以内（NVMe 前提、snappy 圧縮）。
- CPUオーバーヘッドでスループットが 2× 以上悪化する場合はデフォルト off とし、閾値や圧縮を再調整。

# 実装メモ（進捗）
- `io.streaming` セクションを schema に追加（enable/opt_out/memory_limit_gb/step_flush_interval/compression/merge_at_end）。
- `run_zero_d` に StreamingState を挿入し、run/psd/diagnostics/step_diag/mass_budget を同じステップ範囲で同期フラッシュする実装を追加。
- Parquet 書き出しは snappy 既定、チャンクは `series/*_chunk_<start>_<end>.parquet` 形式。mass_budget は CSV 追記。
- streaming 有効時は summary にチャンク一覧と設定を記録し、merge_at_end=true で単一ファイルへ連結する。

# 追加考慮点（周辺影響）
- **単一ファイル前提の解析**: streaming 有効時は `series/run.parquet` が生成されないため、既存の分析スクリプトやテストが単一ファイルを前提にしている場合は `merge_at_end=true` を使うか、チャンクディレクトリ読み込みに対応する変更が必要。
- **ドキュメント更新**: `analysis/config_guide.md` や README/run-recipes に `io.streaming.*` キーとチャンク運用（mass_budget が追記型になる点、チャンク名パターン）を追記する必要あり。
- **スクリプト適用範囲**: `scripts/run_sublim_cooling.cmd` は override 済み。類似スクリプト（例: `scripts/run_sublim_windows_cooling.cmd`）で同様の挙動を望む場合は明示的に override を追加するかデフォルトを見直す。
- **テスト強化**: streaming 無効時の回帰は従来通り。有効ケースで小規模ランの簡易テスト（チャンク出力と summary.streaming ブロックの検証）を追加すると安全。
- **mass_budget 依存**: mass_budget がチャンク追記になるため、後処理ツールが単一CSVを期待していないか確認し、必要に応じて連結手順をドキュメント化する。

# テスト・検証
- 単体: チャンク 2 回以上のフラッシュでスキーマが維持されることを確認（Parquet 読み込みで列欠損がないか）。
- 回帰: 小規模ランで従来と同一の series/summary を生成するか（フラッシュ無発動ケース）。
- 性能: 1e5 ステップ相当でフラッシュ発動時の時間・メモリ変化を記録し、許容オーバーヘッドを評価。

# リスクと対応
- I/O オーバーヘッドで runtime が数倍に伸びる可能性 → チャンク閾値を可変にし、オプトアウト可能なフラグを用意。
- 型ブレ・欠損列でチャンク間でスキーマがずれるリスク → 初回スキーマ固定と欠損列フィルを徹底。
- フラッシュ単位がずれて run/psd/diagnostics の整合が崩れるリスク → 同一ステップ範囲で同期フラッシュを必須化。
- 異常終了時に中途半端なチャンクが残るリスク → チャンクにステップ範囲を埋め込み、再読み込み時にフィルタ可能にする。
- 進捗/メモリ表示が I/O バックプレッシャで遅延するリスク → refresh 間隔や圧縮（snappy/zstd）を設定化し、低速 FS 向けに緩和。
- 将来の並列化でファイル競合が起きるリスク → 書き込みは単一スレッド／プロセスにシリアライズ、ロックやキュー投入で拡張余地を残す。
