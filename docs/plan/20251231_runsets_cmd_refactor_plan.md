# run_sweep.cmd / run_temp_supply_sweep.cmd 中規模整理プラン

**作成日**: 2025-12-31  
**ステータス**: 完了（2026-01-01更新）  
**対象**: Windows runsets（`.cmd`）と run-one 実行経路

---

## 目的

- `.cmd` の責務を「並列制御・OS依存処理」に限定し、**run-one 実行ロジックを Python に集約**する。
- `run_temp_supply_sweep.cmd --run-one` の互換性を維持しつつ、保守コストと重複ロジックを削減する。
- 既存の環境変数・出力規約・ログの互換性を壊さない。
- **数値・物理モデルの骨子（式・パラメータ・出力解釈）を一切変更しない**。

---

## 背景と課題

- `run_sweep.cmd` と `run_temp_supply_sweep.cmd` の内部で **Python 検出・設定生成・実行コマンド組立が重複**している。
- run-one と sweep の経路が混在し、**単一ケースの実行が `.cmd` の大規模ロジックに依存**している。
- Windows 固有の並列制御（`win_process.py`）とケース実行が密結合になり、**テスト/変更の影響範囲が広い**。

---

## 方針（合意事項）

- **並列の有無・方法は `.cmd` に残す**（`win_process.py`、ジョブ数制御、ウィンドウ制御など）。
- **run-one 実体は Python 側に集約**し、`.cmd` は env と引数を渡す薄いラッパーにする。
- `RUN_ONE_*` / `RUN_TS` / `BATCH_SEED` など **既存の環境変数を維持**する。
- **物理・数学の妥当性は現状維持**（設定値・式・ソルバ・出力スキーマの変更は禁止）。

---

## スコープ（確定）

### 対象（やること）
- `scripts/runsets/common/run_one.py` を新設し、**run-one 実行の中核ロジック**を実装する。
- `run_temp_supply_sweep.cmd --run-one` の実装を **Python 呼び出しに置き換える**。
- `run_sweep.cmd` は **並列制御を維持**しつつ、run-one 実行経路を `run_temp_supply_sweep.cmd` に委譲。

### 非対象（やらないこと）
- 既存の env 名/意味、JOB_CMD 形式、出力ディレクトリ規約、ログ文言の変更。
- `run_temp_supply_sweep.cmd` 全体の完全な再設計（あくまで run-one 部分の集約）。
- `win_process.py` の仕様変更や Windows 並列方式の変更。
- hooks/plot/eval の仕様変更（呼び出しタイミング・引数・出力は既存維持）。
- 物理モデル・数値手法・設定値（YAML/overrides）の変更や再解釈。

---

## 物理・数学の不変条件（厳守）

- **式・係数・物理トグル**は既存の YAML/overrides に従い、run_one.py で再定義しない。
- **overrides の優先順**（base < extra < case）を固定し、順序変更や上書き規則を変更しない。
- **出力スキーマ**（`out/<run_id>/series/run.parquet`, `out/<run_id>/summary.json`, `out/<run_id>/checks/mass_budget.csv` 等）を変更しない。
- **タイムステップや安定化ロジック**に新規介入しない。既存 `.cmd` が出力する
  `numerics.*` / `io.substep_*` の overrides は許容し、run_one.py で追加の自動調整は行わない。
- **再現性（seed）**は既存ルールを維持する（`RUN_ONE_SEED` 優先、未指定時は `next_seed.py`）。
- **run_config.json の記録内容**を欠落させない（`io.outdir` と overrides 伝播を維持）。
- run_one.py は **物理系の既定値を新規に持たない**。`.cmd` 側で設定済みの env/overrides をそのまま使い、
  単独実行時は物理系 env の未設定を警告対象とする（出力/seed 系の自動補完は許容）。

---

## 目標アーキテクチャ

```
run_sweep.cmd
  ├─ (並列/単発の制御)
  └─ call run_temp_supply_sweep.cmd [--run-one]
        ├─ (run-one env の準備)
        └─ python scripts/runsets/common/run_one.py
              ├─ overrides 結合
              ├─ base config 解決
              └─ python -m marsdisk.run 実行
```

---

## 実装方針（中規模）

### 1. run-one 実行コアの Python 化

- 新規: `scripts/runsets/common/run_one.py`
- 入力:  
  - `BASE_CONFIG`（env / 引数）  
  - `BASE_OVERRIDES_FILE` / `EXTRA_OVERRIDES_FILE` / `CASE_OVERRIDES_FILE`  
  - `RUN_ONE_T`, `RUN_ONE_EPS`, `RUN_ONE_TAU`, `RUN_ONE_SEED`（env）  
  - `ENABLE_PROGRESS` / `QUIET_MODE` 等の実行フラグ  
- 処理:
  - overrides の優先順は **base < extra < case** を固定し、既存と一致させる
  - overrides 結合は `build_overrides.py` と同等の挙動を再現（必要なら直接呼び出し）
  - run コマンドを構成し `python -m marsdisk.run` を実行
  - exit code を 그대로返す

### 2. `run_temp_supply_sweep.cmd` の run-one 置換

- `--run-one` ルートの実体を `run_one.py` 呼び出しへ置換。
- `JOB_CMD` の構造は維持し、**並列 launch での互換性を担保**する。
- `RUN_ONE_*` の解釈は Python 側で行い、`.cmd` は設定のみ担当。

### 3. `run_sweep.cmd` の責務整理

- 並列制御と runset 全体の起点は維持。
- run-one は `run_temp_supply_sweep.cmd` に集約し、重複ロジックを削減。

---

## run_one.py 設計詳細（確定）

### 目的と役割
- run-one の「1ケース実行フロー」を Python に集約し、`.cmd` は env 準備と起動に限定する。
- 供給・遮蔽・輸送などの設定は **既存の env を `write_base_overrides.py` が読む**前提で維持する。

### 入力と優先順位
- 入力源: CLI引数（任意） / 環境変数 / `.cmd` の既定値（run_one.py は最小限）
- 優先順位: **CLI > env > 既定**

### 必須入力（P0）
- `RUN_ONE_T`, `RUN_ONE_EPS`, `RUN_ONE_TAU`（または CLI で同等指定）

### 省略可だが自動補完される既定（既存互換）
- `RUN_TS`: 未指定なら `scripts/runsets/common/timestamp.py` 相当で補完
- `BATCH_SEED`: 未指定なら `scripts/runsets/common/next_seed.py` 相当で補完
- `SWEEP_TAG`: 未指定なら `temp_supply_sweep` を使用
- `BASE_CONFIG`: 未指定なら `configs/sweep_temp_supply/temp_supply_T4000_eps1.yml`
- overrides ファイル: 未指定なら `TMP_ROOT`（なければ `TEMP` か `./tmp`）配下で
  `marsdisk_overrides_{base,case,merged}_<RUN_TS>_<BATCH_SEED>.txt` を生成
  （上記以外の物理系既定は run_one.py で補完しない）

### 任意 env（互換維持）
- `RUN_ONE_SEED`（未指定時は `next_seed.py` を使用）
- `GIT_SHA`（未指定時は `git rev-parse --short HEAD` を試行）
- `ENABLE_PROGRESS`, `QUIET_MODE`, `PLOT_ENABLE`, `HOOKS_ENABLE`, `HOOKS_STRICT`
- `PYTHON_EXE`, `PYTHON_ARGS`, `PYTHON_ALLOW_LAUNCHER`

### 出力ディレクトリ規約
- `BATCH_DIR = <BATCH_ROOT or OUT_ROOT or "out">/<SWEEP_TAG>/<RUN_TS>__<GIT_SHA>__seed<BATCH_SEED>`
- `TITLE = T{T}_eps{EPS_TITLE}_tau{TAU_TITLE}`  
  (`EPS_TITLE`/`TAU_TITLE` は `.cmd` と同じ置換: `0.` -> `0p`, `.` -> `p`)
- `OUTDIR = <BATCH_DIR>/<TITLE>` を作成し、`series/` と `checks/` を保証する。

### overrides 生成
- base overrides: `write_base_overrides.py --out <BASE_OVERRIDES_FILE>`
- case overrides は `.cmd` と同一のキーと条件で出力:
  - `io.outdir`, `dynamics.rng_seed`, `radiation.TM_K`, `supply.mixing.epsilon_mix`, `optical_depth.tau0_target`
  - `radiation.mars_temperature_driver.table.path`（`COOL_MODE != "hyodo"`）
  - `numerics.t_end_until_temperature_K`, `numerics.t_end_temperature_margin_years`,
    `numerics.t_end_temperature_search_years`（`COOL_TO_K` 指定時）
  - `io.substep_fast_blowout`, `io.substep_max_ratio`（`SUBSTEP_FAST_BLOWOUT != 0`）
  - `io.streaming.memory_limit_gb`（`STREAM_MEM_GB` 指定時）
- merge: **base < extra < case** を厳守

### 実行コマンド
- `python -m marsdisk.run --config <BASE_CONFIG> --quiet --overrides-file <MERGED_OVERRIDES_FILE>`
- `ENABLE_PROGRESS=1` の場合は `--progress` を追加
- Python 実行は `PYTHON_EXE`/`PYTHON_ARGS` を尊重し、未指定時は `sys.executable`

### hooks/plot
- `.cmd` と同一の `PLOT_ENABLE` / `HOOKS_ENABLE` / `HOOKS_STRICT` 条件で
  `scripts/runsets/common/hooks/*` を呼び出す（引数は `--run-dir <OUTDIR>`）

### 終了コード方針
- 前提チェック失敗（必須 env 欠損・ファイル生成失敗）は非ゼロで終了。
- run 本体の失敗は warn を出しつつ継続（既存互換を優先）。
- `HOOKS_STRICT=1` の場合のみ hooks 失敗を非ゼロとする。

### CLI オプション（最小）
```
python scripts/runsets/common/run_one.py
  [--base-config PATH]
  [--t VAL] [--eps VAL] [--tau VAL] [--seed VAL]
  [--run-ts STR] [--batch-seed STR] [--git-sha STR] [--sweep-tag STR]
  [--base-overrides PATH] [--extra-overrides PATH]
  [--case-overrides PATH] [--merged-overrides PATH]
  [--python-exe PATH] [--python-args "…"]
  [--dry-run]
```

---

## 互換性要件（優先度確定）

### P0: 絶対互換
- `run_temp_supply_sweep.cmd --run-one` の CLI 動作は維持。
- `RUN_ONE_*` の必須条件と `RUN_TS` / `BATCH_SEED` / `SWEEP_TAG` / `BASE_CONFIG` / `*_OVERRIDES_FILE` の
  **意味・既定値・補完ルール**は既存互換。
- `RUN_ONE_SEED` と `dynamics.rng_seed` の関係（未指定時は `next_seed.py`）を維持。
- 出力ディレクトリ規約（run_id は `<SWEEP_TAG>/<RUN_TS>__<sha>__seed<batch>/<case>`）を維持。
- `scripts/tests/test_run_one_direct.cmd` の前提（JOB_CMD 形式）を維持。
- exit code の伝播（run-one 失敗時の rc）を維持。

### P1: 高優先
- `PYTHON_EXE` / `PYTHON_ARGS` / `PYTHON_ALLOW_LAUNCHER` の取り扱いは既存互換。
- `ENABLE_PROGRESS` / `QUIET_MODE` / `SKIP_PIP` / `DEBUG` / `TRACE_*` の挙動は既存互換。
- `PLOT_ENABLE` / `HOOKS_ENABLE` / `HOOKS_STRICT` の挙動は既存互換。

### P2: できるだけ維持
- ログ文言・`[DEBUG]/[trace]` 出力の細部は best-effort。

---

## テスト/検証

- `scripts/tests/test_run_one_direct.cmd` の再実行（Windows 実機）。
- `scripts/tests/test_job_launch_detailed.cmd` の run-one 部分（JOB_CMD 互換確認）。
- `scripts/runsets/windows/preflight_checks.py`（simulate-windows を含む lint）。
- 既存の `run_temp_supply_sweep.cmd --run-one` の出力一致確認（`out/<run_id>/series/run.parquet` 生成）。
- 同一ケースでの `out/<run_id>/summary.json` と `out/<run_id>/run_config.json` の差分確認（物理入力が一致するか）。
- `out/<run_id>/checks/mass_budget.csv` が生成され、列構成が維持されていることを確認。

---

## 実装タスク分割（Issue案）

- [x] Issue 1: `run_one.py` の骨格と CLI/env 取り込み（P0 必須入力の検証、`--dry-run`）。
- [x] Issue 2: 出力パス生成（`SWEEP_TAG`/`RUN_TS` サニタイズ、`BATCH_DIR`/`TITLE`/`OUTDIR`）。
- [x] Issue 3: overrides 生成（base/case の出力、`build_overrides.py` 相当の merge）。
- [x] Issue 4: `marsdisk.run` 実行（`--quiet`/`--progress`、rc の扱いを既存互換に）。
- [x] Issue 5: hooks/plot 呼び出しの互換実装（`HOOKS_*`/`PLOT_ENABLE`）。
- [x] Issue 6: `run_temp_supply_sweep.cmd --run-one` を `run_one.py` 委譲に置換。
- [x] Issue 7: `run_sweep.cmd` の run-one 経路を簡素化（run-one 経路が存在しないため変更不要）。
- [x] Issue 8a: 非Windows環境での検証（simulate-windows preflight / pytest）。
- [x] Issue 9: 物理互換チェック（`out/<run_id>/summary.json`/`out/<run_id>/run_config.json`/`out/<run_id>/checks/mass_budget.csv` の一致確認）。

---

## リスクと対策

- **リスク**: env 解析の取りこぼしで従来のケース設定が変わる  
  **対策**: Python 側で `RUN_ONE_*` を必須チェックし、欠損時は明示エラー。
- **リスク**: overrides の優先順序が変わる  
  **対策**: 既存順序（base < extra < case）を固定し、テストで確認。
- **リスク**: 並列時の `JOB_CMD` 互換が崩れる  
  **対策**: `JOB_CMD` は変更せず、run-one の実体のみ差し替え。

---

## 完了条件（DoD）

- `run_temp_supply_sweep.cmd --run-one` が Python 実装を通じて動作し、`out/<run_id>/series/run.parquet` が生成される。
- `run_sweep.cmd` の並列/逐次フローが維持される。
- `scripts/tests/test_run_one_direct.cmd` が通る。
- `preflight_checks.py` の lint で新規エラーが発生しない。

---

## 想定ファイル変更

- 追加: `scripts/runsets/common/run_one.py`
- 更新: `scripts/research/run_temp_supply_sweep.cmd`
- （必要なら）更新: `scripts/runsets/windows/run_sweep.cmd`（run-one 経路の簡素化のみ）
