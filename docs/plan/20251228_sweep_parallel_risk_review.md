# スイープ並列のトラブル整理（Windows: temp_supply sweep）

> **作成日**: 2025-12-28  
> **ステータス**: 草案（運用リスク整理）

---

## 目的
- スイープ並列（複数ケース同時実行）で起こりうる問題を洗い出し、長期運転時の「正常完走/保存」判定に役立てる。
- `run_temp_supply_sweep.cmd` を中心に、保存欠落・設定混入・終了コード未検知などのリスクを網羅する。

## 対象
- `scripts/research/run_temp_supply_sweep.cmd`
- `scripts/runsets/windows/run_sweep.cmd`（ラッパ）
- `scripts/runsets/common/win_process.py`（並列起動・生存確認）

---

## 既知の前提（現状の制御）
- **バッチ識別子の明示継承**: 子プロセスに `RUN_TS` / `BATCH_SEED` を渡して同一バッチ配下にまとめる。
- **ジョブ固有の一時領域**: `--run-one` 時の `TMP_ROOT` を `RUN_ONE_SEED` 付きディレクトリへ分離。
- **出力ディレクトリの分離**: 各ケースで `OUTDIR=BATCH_DIR\TITLE` を採用。

---

## トラブル一覧（症状/原因/影響/一次対策）

| 区分 | 症状 | 典型原因 | 影響 | 一次対策 |
| --- | --- | --- | --- | --- |
| 出力 | ケースが別々のバッチに分裂 | 子が `RUN_TS/BATCH_SEED` を継承しない | 出力が分散し「保存されていない」ように見える | `RUN_TS/BATCH_SEED` 継承を強制 |
| 出力 | 既存ケースが上書きされる | `TITLE` が重複（T/EPS/TAU 重複） | データ欠落 | スイープ入力の重複排除 |
| 出力 | `out/<run_id>/series/run.parquet` が無い | 途中停止、ストリーミング未マージ | 解析不可 | 途中停止の検知と再実行 |
| 出力 | `out/<run_id>/summary.json`/`out/<run_id>/run_config.json` 不在 | 実行失敗、例外終了 | 完走判定不可 | 終了コード集約、欠落チェック |
| 一時ファイル | overrides/sweep list が混在 | TMP 共有で上書き | 誤設定で実行 | ジョブ別 TMP_ROOT |
| アーカイブ | archive にのみ出力がある | `merge_target=external` で外部へ直接マージ | ローカルに結果が残らない | archive 先を正として確認 |
| アーカイブ | `ARCHIVE_DONE` 不在 | 外部ドライブ遅延/切断/権限 | 実質未保存 | archive エラー検知と再実行 |
| 並列管理 | 失敗が検知されない | 親が子の終了コードを集約しない | 失敗が完了扱い | 終了コード集約 or 欠落検査 |
| 依存関係 | 子で pip が走る/失敗 | `SKIP_PIP` 未設定 | 環境破損・停止 | `SKIP_PIP=1` を固定 |
| リソース | CPU 過負荷で極端に遅い | `PARALLEL_JOBS × NUMBA/BLAS` 過並列 | 実行遅延/タイムアウト | `NUMBA_NUM_THREADS=1` 等 |
| リソース | メモリ不足/スワップ | 同時実行数が多い | 途中停止/破損 | `PARALLEL_JOBS` を制限 |
| I/O | ファイルがロックされる | ウイルス対策/索引/外部ドライブ | 書き込み失敗 | ローカル出力＋後段アーカイブ |
| Windows | パスが長い/禁止文字 | `SWEEP_TAG`/`TITLE` に特殊文字 | mkdir 失敗 | タグの sanitize 徹底 |
| Windows | 追跡失敗で待機が延びる | `tasklist` 失敗/権限 | 親が待ち続ける | `win_process.py` の健全性確認 |

---

## 監視ポイント（長期運転向けチェック）

### 1. ケース単位の必須生成物
- `out/<run_id>/summary.json`
- `out/<run_id>/run_config.json`
- `out/<run_id>/checks/mass_budget.csv`
- `out/<run_id>/series/run.parquet`（ストリーミング OFF または merge 完了時）

### 2. アーカイブ関連
- `ARCHIVE_DONE` の有無（成功の指標）
- `ARCHIVE_SKIPPED` の有無（失敗理由の記録）
- `archive_manifest.json`（verify 時の完全性）

### 3. 並列全体の健全性
- 期待ケース数と出力ディレクトリ数の一致
- 出力先が **ローカル** か **アーカイブ先** かの把握（`merge_target=external` の場合）
- `out/<run_id>/summary.json` の欠落件数（=失敗推定）

---

## 欠落検査の自動化案（具体化）

### 目的
- 期待ケース数と実出力の突合を機械的に行い、欠落を即時に可視化する。
- 並列実行で「完了扱いでも欠落している」状況を検知する。

### 入力（期待ケースの定義）
- **一次ソース**: `write_sweep_list.py` が生成する `SWEEP_LIST_FILE`（`T EPS TAU` の行）
- **保存方針**: `SWEEP_LIST_FILE` を `BATCH_DIR\\checks\\expected_sweep_list.txt` へコピーし、完走後検査の唯一ソースにする。

### 期待ケース -> OUTDIR の決定ロジック
- ケースタイトル: `TITLE=T{T}_eps{EPS_TITLE}_tau{TAU_TITLE}`
- `EPS_TITLE/TAU_TITLE` の整形規則（cmd と一致）:
  - `0.` を `0p` に置換（例: `0.1` -> `0p1`）
  - `.` を `p` に置換（例: `1.0` -> `1p0`）

### 実出力の判定ルール
- **必須ファイル（最小）**:
  - `out/<run_id>/summary.json`
  - `out/<run_id>/run_config.json`
  - `out/<run_id>/checks/mass_budget.csv`
  - `out/<run_id>/series/run.parquet`（または `out/<run_id>/series/*.parquet` が存在すれば OK）
- **アーカイブが有効な場合**:
  - `merge_target=external` のときは、`io.archive.dir` 側の出力も探索対象にする。
  - `ARCHIVE_DONE` の有無で「アーカイブ成功/失敗」を判定する。

### 出力（検査レポート）
- `BATCH_DIR\\checks\\sweep_completeness.csv`
  - `case_id`, `expected_dir`, `found_local`, `found_archive`, `missing_files`, `status`
- `BATCH_DIR\\checks\\sweep_completeness.json`
  - `expected_cases`, `found_cases`, `missing_cases`, `missing_files_total`, `archive_failures`

### 実行タイミング
- **並列実行時**: `:wait_all` 後に 1 回だけ実行（親プロセスのみ）
- **逐次実行時**: main loop 完了後に 1 回実行
- 失敗時は `exit /b 1` を返せる `--strict` オプションを用意する。

### 実装スケッチ（Python）
```
python scripts/runsets/common/check_sweep_completeness.py ^
  --batch-dir "%BATCH_DIR%" ^
  --sweep-list "%BATCH_DIR%\\checks\\expected_sweep_list.txt" ^
  --archive-dir "%ARCHIVE_DIR%" ^
  --require summary.json run_config.json checks/mass_budget.csv series/run.parquet ^
  --csv "%BATCH_DIR%\\checks\\sweep_completeness.csv" ^
  --json "%BATCH_DIR%\\checks\\sweep_completeness.json" ^
  --strict
```

### 組み込み方針（cmd 側）
- `run_temp_supply_sweep.cmd` で `CHECK_SWEEP=1` をデフォルト化
- `SWEEP_LIST_FILE` を `BATCH_DIR\\checks\\expected_sweep_list.txt` に保存
- `CHECK_SWEEP_STRICT=1` で `--strict` を有効化

---

## 運用上の推奨（並列デフォルト化時）

- **並列数を控えめに設定**: `PARALLEL_JOBS` を CPU とメモリに合わせて調整。
- **スレッド数を明示**: `NUMBA_NUM_THREADS=1` 等で過並列を抑制。
- **依存関係は固定**: `SKIP_PIP=1` を子プロセスに固定して環境更新を防ぐ。
- **出力先を明示**: `BATCH_ROOT` と `io.archive.dir` を分離し、正の保管先を決めておく。
- **フックの失敗を検知**: `HOOKS_STRICT=1` もしくは事後の欠落検査を必須化。

---

## 残課題（検知性の強化）
- [ ] 親プロセスで子の終了コードを集約し、非0なら全体を失敗扱いにする。
- [ ] `check_sweep_completeness.py` を実装し、欠落検査の CSV/JSON を出力する。
- [ ] `run_temp_supply_sweep.cmd` に `CHECK_SWEEP` フラグを追加し、完走後に自動実行する。
- [ ] `ARCHIVE_DONE`/`ARCHIVE_SKIPPED` を集約する簡易チェッカーを統合する。

---

## 関連ドキュメント

| ドキュメント | 役割 |
| --- | --- |
| `docs/plan/20251213_temp_supply_sweep_followup.md` | temp_supply sweep の前提整理 |
| `docs/plan/20251213_run_temp_supply_sweep_current_settings.md` | 既存設定の整理 |
| `docs/plan/20251224_scripts_runsets_organization.md` | runsets 周辺の構成整理 |
