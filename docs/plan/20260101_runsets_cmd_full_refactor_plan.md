# run_sweep.cmd / run_temp_supply_sweep.cmd フル構造化プラン

**作成日**: 2026-01-01  
**ステータス**: 実装完了（Windows関連の未完了項目は削除）（2026-01-01更新）  
**対象**: Windows runsets（.cmd）と Python 呼び出し共通化

---

## 目的

- Python 解決と実行の流れを**共通ヘルパーに集約**し、二重クォートや環境ズレによる失敗を再発させない。
- `RUN_TS` / `SWEEP_TAG` などの**トークン妥当性チェックを統一**して、壊れた実行名を排除する。
- `run_sweep.cmd` / `run_temp_supply_sweep.cmd` の**重複ロジックを削減**し、保守性を上げる。
- 物理・数値ロジック、出力スキーマ、既存の環境変数互換は**一切変えない**。

---

## 背景と課題

- `PYTHON_CMD` が「文字列コマンド」になっており、**二重クォートや PATH 変化に弱い**。
- venv 有効化後に `PYTHON_CMD` が更新されず、**古い Python が使われる**ケースがある。
- `RUN_TS` に異常値が混入すると `==` などの壊れた run 名になり、**出力と一時ファイルが破綻**する。
- Python 解決ロジックが複数箇所にあり、**差分やバグが生まれやすい**。

---

## 方針（合意事項）

- Python 解決は `scripts/runsets/common/resolve_python.cmd` に集約する。
- 実行時は `PYTHON_EXE`（絶対パス・非クォート）を主とし、`PYTHON_CMD` は**ログ用途のみに限定**する。
- `run_sweep.cmd` / `run_temp_supply_sweep.cmd` は**共通ヘルパーを呼ぶだけ**にする。
- `RUN_TS` / `SWEEP_TAG` / `RUN_ONE_*` などの env 名・意味・既定値は**既存互換**。
- 物理モデル、YAML、overrides、出力規約は変更しない。

---

## スコープ

### 対象（やること）
- Python 解決ロジックを共通化した `resolve_python.cmd` を新設。
- Python 実行のラッパー `python_exec.cmd` を新設。
- `RUN_TS` の妥当性チェック / 再生成を共通化（`sanitize_token.cmd` など）。
- `run_sweep.cmd` / `run_temp_supply_sweep.cmd` を共通ヘルパーに移行。
- テスト cmd（`scripts/tests/*`）を新構造に追随させる。

### 非対象（やらないこと）
- 物理モデル / 数値処理 / outputs の変更。
- overrides の優先順・キー定義の変更。
- `win_process.py` の仕様変更。
- hooks/plot/eval の挙動変更。

---

## 目標アーキテクチャ

```
run_sweep.cmd
  ├─ call resolve_python.cmd
  ├─ call run_temp_supply_sweep.cmd
  │     ├─ call resolve_python.cmd (再利用)
  │     ├─ call sanitize_token.cmd (RUN_TS/SWEEP_TAG)
  │     └─ call python_exec.cmd ...
  └─ (並列制御はそのまま)

python_exec.cmd
  └─ call "%PYTHON_EXE%" %PYTHON_ARGS% <args>
```

---

## 共通ヘルパー設計

### 1) resolve_python.cmd
- 入力: `PYTHON_EXE`, `PYTHON_ARGS`, `PYTHON_ALLOW_LAUNCHER`
- 出力: `PYTHON_EXE`（絶対パス・非クォート）, `PYTHON_ARGS`, `PYTHON_CMD`（ログ用）
- 仕様:
  - Python 3.11+ を保証
  - `py` launcher が許容される条件は既存互換
  - venv の Python を使う場合も、**必ず絶対パスへ正規化**

### 2) python_exec.cmd
- 役割: `PYTHON_EXE` + `PYTHON_ARGS` で Python を実行
- 仕様:
  - `call "%PYTHON_EXE%" %PYTHON_ARGS% %*` を単一の実行経路にする
  - stdout/stderr は素通し（for /f の capture 用途に使用可）

### 3) sanitize_token.cmd
- 役割: `RUN_TS` / `SWEEP_TAG` の安全化
- 仕様:
  - 禁止文字（`= ! & | < > ? *` など）があれば再生成
  - 再生成は `timestamp.py` で実施
  - 正規化済みの場合は noop

---

## 具体的な差分計画

### run_sweep.cmd

- [x] Python 解決ロジックを `resolve_python.cmd` に置換し、`PYTHON_EXE` の絶対パス化を単一経路に統一
- [x] `PYTHON_CMD` を「ログ用途のみ」に限定し、実行は `python_exec.cmd` 経由に統一
- [x] 既存の `PYTHON_CMD_ABS` / `PYTHON_EXE_ABS` 生成ブロックは撤去し、`resolve_python.cmd` 呼び出しへ置換
- [x] `preflight_checks.py` / `read_overrides_cmd.py` / `calc_*` 等の呼び出しを `python_exec.cmd` へ寄せる
- [x] 子スクリプト起動前の `PYTHON_EXE` エクスポートは維持し、`PYTHON_CMD` は参照しない

### run_temp_supply_sweep.cmd

- [x] 先頭の Python 検出ロジックを `resolve_python.cmd` に移行（`PYTHON_EXE` は絶対パス、非クォート）
- [x] venv 有効化後に `resolve_python.cmd` を再実行し、`PYTHON_EXE`/`PYTHON_ARGS` のズレを排除
- [x] `RUN_TS` / `SWEEP_TAG` の正規化を `sanitize_token.cmd` に委譲し、`==` 等の不正値を再生成
- [x] `next_seed.py` / `timestamp.py` などの Python 呼び出しは `python_exec.cmd` に統一
- [x] 並列起動（`win_process.py launch`）は `python_exec.cmd` 経由に統一し、二重クォートを根絶
- [x] `PYTHON_CMD` を利用した `for /f` を整理し、`python_exec.cmd` の stdout を捕捉する形に置換

---

## 差分順序と依存関係

### 実施順序（推奨）

1. 共通ヘルパー追加（`resolve_python.cmd` / `python_exec.cmd` / `sanitize_token.cmd`）
2. preflight 許容（`scripts/runsets/windows/preflight_allowlist.txt` の追記が必要か判定）
3. `run_temp_supply_sweep.cmd` の移行（python 呼び出し経路の統一・RUN_TS 正規化）
4. `run_sweep.cmd` の移行（python 解決ロジックの置換）
5. テスト cmd の更新（`scripts/tests/*`）

### 依存関係

- [x] `run_temp_supply_sweep.cmd` の移行は `resolve_python.cmd` と `python_exec.cmd` 完成が前提
- [x] `run_sweep.cmd` の移行は `resolve_python.cmd` 完成が前提
- [x] `sanitize_token.cmd` は `run_temp_supply_sweep.cmd` の RUN_TS 生成置換に必須
- [x] テスト更新は両スクリプトの移行後に実施

---

## PYTHON_CMD 参照箇所と置換対象

### 置換ルール（共通）

- 実行: `!PYTHON_CMD! <args>` → `call "<runsets_common>\\python_exec.cmd" <args>`
- for /f 取得: `for /f ... in (\`%PYTHON_CMD% <args>\`)` → `for /f ... in (\`call "<runsets_common>\\python_exec.cmd" <args>\`)`
- ログ: `PYTHON_CMD` の表示は維持可（実行には使わない）

### run_sweep.cmd（PYTHON_CMD 参照一覧）

- 定義/正規化: 252-284, 287-362（`resolve_python.cmd` へ置換して削除）
- バージョン確認: 297, 300, 341（`resolve_python.cmd` 側で実施）
- `for /f` 実行:
  - 813（disk_usage の取得）
  - 1744（size probe）
  - 1799 / 1811 / 1823（calc_* 系）
- 直接実行:
  - 1312 / 1314（preflight）
  - 1425（read_overrides_cmd）
- ログ用途:
  - 254 / 1276 / 1308（ログのみ、実行では参照しない）

### run_temp_supply_sweep.cmd（PYTHON_CMD 参照一覧）

- 定義/正規化: 283-312, 447-448（`resolve_python.cmd` へ置換して削除）
- バージョン確認: 315（`resolve_python.cmd` 側で実施）
- `PYTHON_BOOT_CMD`: 328（`PYTHON_EXE` で再構成するか `python_exec.cmd` へ置換）
- `for /f` 実行:
  - 358（timestamp）
  - 394 / 946 / 1118（seed 系）
  - 603 / 632 / 652 / 740 / 775 / 786（calc_* 系）
  - 1187（win_process alive）
- 直接実行:
  - 454 / 455（pip）
  - 691（read_study_overrides）
  - 849 / 874 / 889（run_one / overrides / sweep list）
  - 988 / 990（override builder）
  - 1018 / 1066 / 1070 / 1074 / 1078（hooks）
  - 1144（win_process launch）
- ログ用途:
  - 491 / 999 / 1111 / 1115（ログのみ、実行では参照しない）

---

## 互換性要件

### P0
- `run_temp_supply_sweep.cmd --run-one` の挙動維持
- `RUN_ONE_*` / `RUN_TS` / `BATCH_SEED` / `SWEEP_TAG` の意味と既定値維持
- 出力ディレクトリ規約の完全維持
- overrides の優先順（base < extra < case）維持

### P1
- `PYTHON_ALLOW_LAUNCHER` / `PYTHON_ARGS` の扱い維持
- `TRACE_*`, `DEBUG`, `QUIET_MODE` の出力挙動維持

---

## 変更対象（予定ファイル）

- [x] `scripts/runsets/common/resolve_python.cmd`（新規）
- [x] `scripts/runsets/common/python_exec.cmd`（新規）
- [x] `scripts/runsets/common/sanitize_token.cmd`（新規）
- [x] `scripts/runsets/common/sanitize_token.py`（新規）
- [x] `scripts/runsets/windows/run_sweep.cmd`
- [x] `scripts/research/run_temp_supply_sweep.cmd`
- [x] `scripts/tests/test_parallel_launch.cmd`
- [x] `scripts/tests/test_job_launch_detailed.cmd`

---

## 実装ステップ（チェックリスト）

### 準備・調査
- [x] Python 呼び出し箇所と `PYTHON_CMD` 参照の棚卸し
- [x] `preflight_checks.py` の許容条件（allowlist/探索パス）を確認

### 共通ヘルパー実装
- [x] `resolve_python.cmd` を作成（絶対パス化・3.11+確認・ログ用 `PYTHON_CMD` 生成）
- [x] `python_exec.cmd` を作成（`call "%PYTHON_EXE%" %PYTHON_ARGS% %*` に統一）
- [x] `sanitize_token.cmd` を作成（`RUN_TS` / `SWEEP_TAG` の妥当性検査と再生成）

### 既存 `.cmd` の移行
- [x] `run_temp_supply_sweep.cmd` の Python 実行を `python_exec.cmd` 経由に置換
- [x] `run_temp_supply_sweep.cmd` の `RUN_TS` / `SWEEP_TAG` 生成を `sanitize_token.cmd` に委譲
- [x] `run_sweep.cmd` の Python 解決ロジックを `resolve_python.cmd` に置換
- [x] `run_sweep.cmd` から `PYTHON_CMD` 依存の直接実行を撤去

### テスト更新・整合
- [x] `scripts/tests/test_parallel_launch.cmd` を新ヘルパーで実行可能に更新
- [x] `scripts/tests/test_job_launch_detailed.cmd` を新ヘルパーで実行可能に更新

### 仕上げ
- [x] 旧ロジックが残っていないか（重複 Python 解決）を最終チェック

---

## テスト計画（チェックリスト）

### 単体・構造確認
- [x] `resolve_python.cmd` のみで `PYTHON_EXE` が絶対パス化されることを確認
- [x] `python_exec.cmd` で `-c "import sys; print(sys.executable)"` が通る
- [x] `sanitize_token.cmd` で `RUN_TS==` 等の不正値が再生成される

### Windows 実機
- [x] `scripts\tests\test_parallel_launch.cmd`
- [x] `scripts\tests\test_job_launch_detailed.cmd`

### 非 Windows
- [x] `preflight_checks.py --simulate-windows` で新 .cmd の構文/参照確認

---

## 実装時の注意点（網羅チェック）

### 互換性と動作
- [x] `RUN_TS` / `RUN_ONE_*` / `BATCH_SEED` / `SWEEP_TAG` の既定値と優先順位を崩さない
- [x] overrides の優先順（base < extra < case）を変更しない
- [x] 出力ディレクトリ規約（run_id は `<SWEEP_TAG>/<RUN_TS>__<sha>__seed<batch>/<case>`）を維持
- [x] `PYTHON_ALLOW_LAUNCHER` の許容条件を既存互換に保つ
- [x] `QUIET_MODE` / `DEBUG` / `TRACE_*` のログ挙動を変えない
- [x] hooks/plot/eval の実行条件を変えない

### Python 呼び出しと quoting
- [x] `PYTHON_EXE` は常に絶対パス・非クォートで保持する
- [x] 実行は `python_exec.cmd` 経由に統一し、`PYTHON_CMD` を実行に使わない
- [x] `for /f` で Python 出力を取る箇所は `call python_exec.cmd ...` に統一する
- [x] 二重クォート（`""python""`）が発生しないことを確認
- [x] venv 有効化後に `resolve_python.cmd` を再実行して Python 経路を再解決する

### Windows CMD の罠
- [x] delayed expansion の `!` を含む文字列を扱わない（`RUN_TS` に禁止文字を許さない）
- [x] `for /f` は `usebackq` と `call` の相性に注意してテストする
- [x] UTF-8/CP932 混在で `win_process.py` の cmd-file 読み取りが壊れないようにする
- [x] short path 依存（`~1`）の有無に配慮し、絶対パスを優先する

### preflight / allowlist
- [x] 新規 `.cmd` を `preflight_allowlist.txt` に追加する必要があるか確認する
- [x] `preflight_checks.py` の cmd-root / cmd-exclude との整合を崩さない

### 並列起動・プロセス管理
- [x] `win_process.py launch` の呼び出し方法を維持（`--cmd-file`/`--cwd`/`--window-style`）
- [x] `alive` チェックの出力形式（`pids|count`）に依存するロジックを変えない
- [x] `JOB_SEED` が空にならないことをチェックする（seed 取得失敗時の再試行）

### ログと診断
- [x] debug/trace のログファイル出力パスとファイル名規約を維持
- [x] `PYTHON_CMD` はログ用途に限定し、表示は継続する
- [x] 失敗時の `errorlevel` 伝播を壊さない

---

## リスクと対策

- `for /f` 内で `call` を使う場合の quoting 問題
  - `python_exec.cmd` は stdout のみを返す仕様に固定
- delayed expansion による `!` 破壊
  - `sanitize_token.cmd` で `RUN_TS` に禁止文字を許さない
- 旧ロジックからの移行漏れ
  - 両スクリプトの Python 呼び出しを `python_exec.cmd` 経由に統一

---
