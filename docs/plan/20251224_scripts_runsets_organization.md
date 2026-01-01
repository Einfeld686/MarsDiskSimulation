# scripts 整理計画: runsets 方式

**作成日**: 2025-12-24  
**ステータス**: 部分実装完了（2026-01-01更新）  
**対象**: `scripts/` 配下の実行ラッパ整理（1D が主、0D は検証用）

## 実装完了状況

以下の構造が実装済み：

- ✅ `scripts/runsets/` ディレクトリ構造
- ✅ `scripts/runsets/common/` 共通ヘルパー
- ✅ `scripts/runsets/windows/` Windows 用スクリプト
- ✅ `scripts/runsets/mac/` macOS 用スクリプト
- ⚠️ hooks 統合：部分的に実装

---

## 目的

- 実行ラッパを OS/用途で整理し、再現性と運用性を上げる。
- **1D を標準運用**とし、**0D は検証用（短時間チェック/CI）**に限定する。
- 物理設定の単一ソースは `configs/` に残し、`scripts/` は実行条件を担う。

---

## 参照スクリプト（現行）

- `scripts/research/run_temp_supply_sweep.sh`: 環境変数 + `--override` を使ったスイープ実行。
- `scripts/research/run_temp_supply_sweep_1d.sh`: 1D の既定値を付与する薄いラッパー。

上記の「**共通ランナー + 1D ラッパー**」構成を踏襲する。

---

## 方針

1. `scripts/` 直下は増やさず、`runsets/` に実行入口を集約する。
2. **命名は `run_one` / `run_sweep` を統一**し、1D 既定で運用する。
3. OS 依存（.sh/.cmd、環境変数、ストレージ選択）は `runsets/<os>/` に閉じる。
4. `configs/` に物理パラメータを固定し、`runsets` は **実行条件のみ**を上書きする。
5. 分割実行・プロット・評価は **runsets の構成要素として明示**する。

---

## 決定事項（合意）

- `configs/base.yml` は **run_temp_supply_sweep 基準で全面的に寄せる**（後で細部調整）。
- I/O は **runsets/overrides に集約**し、base.yml から外す。
- 温度テーブル（`radiation.mars_temperature_driver.table.*`）は **base.yml で維持**する。
- プロット互換は **専用スクリプトへ分離**し、runsets から呼び出す。
- Windows 並列は **ケース並列（T/EPS/TAU）**と **セル並列（1ケース内部）**を区別して運用する。
- Windows は **セル並列を既定**とし、ケース並列は任意オプションにする（遅延検知の回避）。

---

## 提案ディレクトリ構成

```
scripts/
  runsets/
    mac/
      run_one.sh                # 単発実行（1D 既定）
      run_sweep.sh              # パラメータスタディ（1D 既定）
      overrides.txt             # 共通の --override リスト
    windows/
      run_one.cmd
      run_sweep.cmd
      overrides.txt
    common/
      base.yml                  # 共通コア（1D 既定の基準）
      study_*.yml               # パラメータスタディ定義
      merge_config.py           # base+study+overrides を合成（任意）
      hooks/
        plot_sweep_run.py       # quick-look plot（既存 scripts/research/plot_sweep_run.py の呼び出し）
        evaluate_tau_supply.py  # 供給評価（既存 scripts/research/evaluate_tau_supply.py の呼び出し）
        preflight_streaming.py  # ストリーミング事前チェック（既存 scripts/research/preflight_streaming_check.py の呼び出し）
```

> 既存の `scripts/research/run_temp_supply_sweep*.{sh,cmd}` は「共通ランナー」として残し、
> `runsets/*` から呼び出す形を基本とする。

---

## 実行フロー（想定）

1. `runsets/<os>/run_one.*` が **1D 既定値**を設定  
   - `GEOMETRY_MODE=1D`, `GEOMETRY_NR=...`, `SWEEP_TAG=...` など
2. `runsets/<os>/run_sweep.*` が `scripts/research/run_temp_supply_sweep.*` を呼ぶ  
   - `BASE_CONFIG` は `scripts/runsets/common/base.yml` を参照
3. **ポスト処理フック**（任意）  
   - streaming chunk を使う場合は `preflight_streaming_check.py` を先に実行  
   - quick-look plot: `plot_sweep_run.py`  
   - 供給評価: `evaluate_tau_supply.py`  
4. 0D 検証は **`run_one.*` 内の明示フラグ**でのみ実行  
   - 1D を壊さないため、0D 実行は手動指定に限定

---

## 具体的な役割分担（例）

- **共通ランナー**: `scripts/research/run_temp_supply_sweep.sh`
  - sweep ループ、環境変数解釈、出力ディレクトリ規約
- **1D ラッパー**: `scripts/runsets/mac/run_sweep.sh`
  - 1D 既定値、OS 依存の I/O 設定（外部 SSD、streaming）
- **ポスト処理**: `scripts/runsets/common/hooks/*`
  - 事前チェック/可視化/評価の呼び出しを共通化
- **0D 検証**: `scripts/runsets/mac/run_one.sh` の明示フラグ
  - `GEOMETRY_MODE=0D` + 短時間 `T_END_SHORT_YEARS` など最小限

---

## run_temp_supply_sweep.sh に含まれる要素（共通ランナーの責務）

- **実行準備**: venv 作成、依存導入、出力ディレクトリ命名（timestamp + git sha + seed）。
- **スイープ定義**: T/EPS/TAU の配列指定、短縮ラン (`T_END_SHORT_YEARS`)。
- **冷却停止条件**: `COOL_TO_K`, `COOL_MODE`, `COOL_MARGIN_YEARS`, `COOL_SEARCH_YEARS`。
- **streaming**: `io.streaming.*` の既定 ON、`STREAM_MEM_GB`/`STREAM_STEP_INTERVAL`。
- **分割実行**: `numerics.checkpoint.*` の有効化（interval/keep/format）。
- **サブステップ**: `io.substep_fast_blowout`, `io.substep_max_ratio`。
- **供給・遮蔽・輸送**: supply/feedback/temperature/transport の env による一括設定。
- **診断**: stop_reason の表示、quick-look plot、`evaluate_tau_supply.py` の実行。

> これらは runsets の構成要素として可視化し、`run_one/run_sweep` から制御できるようにする。

---

## Windows .cmd の現行要素（参考に反映）

`scripts/research/run_temp_supply_sweep.cmd` と `run_temp_supply_sweep_1d.cmd` から、
Windows 固有の運用設計を runsets に移植する。

- **実行ディレクトリ固定**: `out/<run_id>/` を強制 root にする。
- **auto jobs**: `AUTO_JOBS=1` で CPU/メモリを PowerShell から取得し、
  `PARALLEL_JOBS` と `STREAM_MEM_GB` を自動決定。
- **並列実行（ケース並列）**: `PARALLEL_JOBS>1` の場合、`--run-one` で子プロセス起動。
- **run-one モード**: `RUN_ONE_T/EPS/TAU` 指定で単発ケースを実行。
- **ウィンドウ制御**: `PARALLEL_WINDOW_STYLE` で起動ウィンドウを調整。
- **1D 既定**: `run_temp_supply_sweep_1d.cmd` が 1D/並列/セル並列の既定値を付与。
- **quicklook**: Windows 版は一時 Python スクリプトで `quicklook.png` を生成。

> runsets/windows の `run_one.cmd` / `run_sweep.cmd` でこれらを踏襲する。
> なお Windows 並列は **ケース並列**であり、`MARSDISK_CELL_*` の **セル並列**とは別軸である。
> 既定は **セル並列のみ**（`PARALLEL_JOBS=1`、`MARSDISK_CELL_PARALLEL=1`）。ケース並列は明示指定時のみ有効。

---

## 分割実行（checkpoint）と再開

`run_temp_supply_sweep.sh` と同様に、以下の分割実行オプションを **runsets 側で可視化**する。

- `CHECKPOINT_ENABLE` / `CHECKPOINT_INTERVAL_YEARS` / `CHECKPOINT_KEEP` / `CHECKPOINT_FORMAT`
- 1D sweep では既定 ON、0D 検証は既定 OFF を推奨
- 再開が必要な場合は `numerics.resume.*` を `overrides.txt` で明示

---

## プロット/評価の統合方針

`run_temp_supply_sweep.sh` 内に埋め込まれている quick-look プロットと評価を、
**runsets/common/hooks 経由の共通呼び出し**に寄せる。

- quick-look plots: `scripts/research/plot_sweep_run.py` を呼び出す
- 供給評価: `scripts/research/evaluate_tau_supply.py` を呼び出す
- streaming チェック: `scripts/research/preflight_streaming_check.py` を必要時に実行

> 既存の inline プロットは段階的に移行し、**専用の共通プロットスクリプト**へ統一する。
> 推奨: `scripts/runsets/common/hooks/plot_sweep_run.py`。

---

## 追加で詰めるべき要素（既存実装の確認チェックリスト）

> 本節は既存コードの運用ルールを整理したもの（新規実装ではない）。

- **設定の優先順位**: CLI > overrides.txt > env > study.yml > base.yml の順に適用。
- **環境変数の命名**: 既存互換を維持しつつ、runsets 専用は `RUNSET_` 接頭辞で衝突を回避。
- **出力の命名/再現性**: `out/<ts>__<sha>__seed<batch>/<case>` 形式を維持し、`out/<run_id>/run_config.json` と `out/<run_id>/summary.json` の記録を必須化。
- **失敗時の挙動**: run 本体が失敗しても plot/eval を「可能な範囲で実行」し、exit code は `HOOKS_STRICT` で制御。
- **OS 差異の最小化**: Windows 固有の `AUTO_JOBS/parallel` は runsets/windows に閉じる。
- **1D/0D の境界**: 0D 実行は `--0d` の明示指定のみ許可。

---

## 既存実装の遵守ポイント（追加）

- **環境変数の互換維持**: `run_temp_supply_sweep.*` で使う変数名と意味を変更しない。
- **出力ディレクトリ規約**: `timestamp + git sha + seed` の命名を維持（Windows は `out/<run_id>/` 固定）。
- **Windows 並列運用**: `AUTO_JOBS` / `PARALLEL_JOBS` / `RUN_ONE_*` / `PARALLEL_WINDOW_STYLE` の挙動を再現。
- **セル並列の引き継ぎ**: `run_temp_supply_sweep_1d.cmd` の `MARSDISK_CELL_*` 既定値を runsets/windows に反映。
- **progress/quiet の互換**: `--quiet` と `ENABLE_PROGRESS` の扱いを維持。
- **簡易プロット互換**: `overview.png` / `supply_surface.png` / `optical_depth.png` と `quicklook.png` の両系統を維持。
- **chunk 対応**: `out/<run_id>/series/run.parquet` 不在時に `out/<run_id>/series/run_chunk_*.parquet` を読む経路を必須化。
- **merge フロー**: `merge_at_end` 既定 ON + `preflight_streaming_check.py` + `merge_streaming_chunks.py` を前提にする。
- **評価出力の互換**: `evaluate_tau_supply.py` の出力先と CLI 引数を変更しない。

---

## 拡張性・保守性の実装方針（既存実装の整理）

- **共通ランナーを一本化**: `run_temp_supply_sweep.*` のロジックは維持し、runsets は薄いラッパーに徹する。
- **重複排除**: plot/eval/preflight は `hooks/` 経由で呼び出し、OS 側に同一ロジックを複製しない。
- **責務分離**: runsets は「設定・実行」、hooks は「診断・可視化」、tools は「後処理（merge）」。
- **小さな関数/小さなスクリプト**: 1つの責務に限定し、既存スクリプトへの委譲を優先。
- **エラー扱い統一**: warn/skip/abort を `HOOKS_STRICT` で切替可能にする。

---

## 簡易プロットの互換性要件（既存実装の整理）

- **必須出力**: `overview.png`, `supply_surface.png`, `optical_depth.png`（既存の quick-look を維持）。
- **入力互換**: `out/<run_id>/series/run.parquet` が無い場合は `out/<run_id>/series/run_chunk_*.parquet` を自動で読む。
- **列不足の扱い**: 欠損列は NaN で埋め、プロットから除外（警告のみ）。
- **大規模データ対応**: downsample を既定で有効化し、`PLOT_MAX_ROWS` で制御。
- **1D/0D 両対応**: `cell_index` がある場合はセル集約 or 重み平均で可視化。

---

## run.parquet の分割出力と統合（既存実装の整理）

**出力パターン**

- streaming 有効: `out/<run_id>/series/run_chunk_*.parquet` を随時書き出し、`merge_at_end=true` なら終了時に `out/<run_id>/series/run.parquet` を生成。
- streaming 無効: 直接 `out/<run_id>/series/run.parquet` を生成。

**統合フロー**

1. `merge_at_end=true` の場合、実行終了時に自動 merge（`marsdisk/io/streaming.py`）。
2. `out/<run_id>/series/run.parquet` が無い場合は `tools/merge_streaming_chunks.py` を使用して後処理 merge。
3. merge 前に `scripts/research/preflight_streaming_check.py` でスキーマ整合を確認。

**運用規約（runsets に反映）**

- `merge_at_end` は既定 ON（Windows/Mac ともに一致させる）。
- merge 失敗時は `hooks/preflight_streaming.py` の warn を許容し、plot 側は chunk を読む。
- `tools/merge_streaming_chunks.py --force` は最終手段として明示利用する。

---

## hooks の具体 API（現状準拠）

**共通方針**

- hooks は `scripts/runsets/common/hooks/*.py` の薄いラッパーとして提供する。
- 入力は **run_dir を必須**にし、追加オプションは環境変数で上書き可能とする。
- exit code は原則 pass-through（0=OK, 1=warn, 2=error）。`HOOKS_STRICT=1` の場合は warn も失敗扱い。

**CLI 形**

```
python scripts/runsets/common/hooks/preflight_streaming.py --run-dir <path>
python scripts/runsets/common/hooks/plot_sweep_run.py --run-dir <path>
python scripts/runsets/common/hooks/evaluate_tau_supply.py --run-dir <path>
```

**環境変数（標準）**

- `RUN_DIR`（必須、CLI 未指定時に使用）
- `HOOKS_ENABLE`（例: `preflight,plot,eval`。既定: `plot,eval`）
- `HOOKS_STRICT`（0/1。既定: 0）
- `PLOT_MAX_ROWS`, `PLOT_BATCH_SIZE`（plot 側に 전달）
- `EVAL_WINDOW_SPANS`, `EVAL_MIN_DURATION_DAYS`, `EVAL_THRESHOLD_FACTOR`（evaluate 側に 전달）

**出力先の扱い**

- plot: `<run_dir>/plots/*.png`
- eval: `<run_dir>/checks/tau_supply_eval.json`（既存スクリプトの出力先に従う）
- preflight: 標準出力に診断、exit code で成否を返す

---

## run_one/run_sweep の引数規約（現状準拠）

**共通**

- CLI は最小限、詳細は環境変数で指定する（既存 `run_temp_supply_sweep` と互換）。
- `--config` は `scripts/runsets/common/base.yml` を既定。
- `--overrides` は `scripts/runsets/<os>/overrides.txt` を既定。
- `--dry-run` はコマンド生成のみで実行しない（Windows の現行挙動に合わせる）。
- `--no-plot` / `--no-eval` / `--no-preflight` で hooks を無効化可能。

**run_one**

```
run_one.{sh,cmd} --t <K> --eps <float> --tau <float> [--seed <int>]
                [--config <path>] [--overrides <path>] [--out-root <path>]
                [--0d] [--dry-run] [--no-plot] [--no-eval] [--no-preflight]
```

- `--t/--eps/--tau` は必須。内部では `RUN_ONE_T/EPS/TAU` に変換して共通ランナーへ渡す。
- `--0d` のときのみ 0D を許可。既定は 1D。

**run_sweep**

```
run_sweep.{sh,cmd} [--study <path>] [--config <path>] [--overrides <path>]
                  [--out-root <path>] [--dry-run] [--no-plot] [--no-eval] [--no-preflight]
```

- `--study` が無い場合は `T_LIST_RAW/EPS_LIST_RAW/TAU_LIST_RAW` を利用。
- `--study` ありの場合は `study_*.yml` から sweep 変数を読み、
  `T_LIST_RAW/EPS_LIST_RAW/TAU_LIST_RAW` と `SWEEP_TAG` を上書きする。

---

## overrides.txt の粒度（現状運用）

**原則**

- `overrides.txt` は **実行条件のみ**（I/O・数値・診断・並列）を記述する。
- 物理設定（`material/psd/qstar/radiation/supply` 等）は `common/base.yml` と `study_*.yml` に固定する。

**許可する範囲（例）**

- `io.*`（streaming、outdir など）
- `numerics.*`（checkpoint/resume、dt など）
- `diagnostics.*`
- `phase.*`（実行時スイッチのみ）
- `geometry.Nr`（必要時のみ、原則は base.yml 側）

**禁止/非推奨**

- `material.*`, `psd.*`, `qstar.*`, `radiation.*`, `supply.*` の恒常変更
- 物理モデルの切り替え（`physics_mode` など）

**フォーマット**

```
# overrides.txt (one per OS)
io.streaming.enable=true
io.streaming.memory_limit_gb=10
io.streaming.step_flush_interval=1000
io.streaming.merge_at_end=true
numerics.checkpoint.enabled=true
numerics.checkpoint.interval_years=0.083
```

> 行は `path=value` のみ。空行と `#` コメントは無視する想定。

---

## 移行ステップ（案）

1. **runsets 骨子を追加**（既存スクリプトは維持）
   - `runsets/<os>/run_one`, `run_sweep`, `overrides.txt`, `common/base.yml` を追加。
2. **1D 既定値の移植**
   - `run_temp_supply_sweep_1d.*` の既定値を runsets に反映。
3. **overrides.txt の導入**
   - I/O/数値/診断のみを移動し、物理設定は base/study に残す。
4. **hooks の追加（薄いラッパー）**
   - 既存 `scripts/research/*` を呼ぶだけの共通 hooks を用意。
5. **runsets から既存ランナーを呼ぶ**
   - `runsets` は `run_temp_supply_sweep.*` を呼び出すだけの構造にする。
6. **plot/eval の重複整理（任意）**
   - 既存 inline plot/eval を残すか、hooks で統一するかを選択。
7. **base.yml の整備**
   - `configs/base.yml` を 1D 既定・runsets の標準に合わせて整理。
8. **README 追記**
   - runsets 導線と互換条件のみを明記。

---

## 既存スクリプト削除方針（最終段）

- **削除対象**: runsets に完全移行できた時点で、散在する旧スクリプトを削除。
- **削除条件**:
  - runsets から既存の出力（plots/checks/summary）が再現できる。
  - README と docs/plan の参照先が runsets に置換済み。
  - Windows/Mac の主要経路（run_one/run_sweep）が動作確認済み。
- **削除手順**:
  1. 旧スクリプトを `deprecated` 扱いにし、README から導線を外す。
  2. runsets 側の使用実績を 1 サイクル確保（代表スイープ完走）。
  3. 旧スクリプトを削除し、依存参照の掃除（grep で残存確認）。

---

## base.yml のデフォルト化と整備方針

- **デフォルト指定**: runsets の標準 `--config` は `configs/base.yml` を指す。
- **共通 core の位置づけ**: `runsets/common/base.yml` は `configs/base.yml` のコピー/参照で一致させる。
- **1D 既定**: `geometry.mode=1D` と `geometry.Nr` を base.yml 側で保証する。
- **OS 非依存**: パス依存・デバイス依存（外部 SSD 等）は base.yml に入れない。
- **物理設定の固定**: material/psd/qstar/radiation/supply は base.yml を単一ソースとし、
  overrides.txt には入れない。
- **検証**: `python -m marsdisk.run --config configs/base.yml` が 1D で完走することを必須条件とする。
- **温度テーブル**: `radiation.mars_temperature_driver.table.*` は base.yml に維持する。

---

## base.yml の標準化項目（具体）

**1D 既定（必須）**

- `geometry.mode=1D`
- `geometry.Nr=<default>`（例: 32）
- `disk.geometry.r_in_RM`, `disk.geometry.r_out_RM`, `disk.geometry.r_profile`, `disk.geometry.p_index`
- `geometry.r_in/r_out` は未設定（`disk.geometry` を優先）

**テーブルパス（統一）**

- `radiation.qpr_table_path`:
  - 既定: `marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv`
  - 旧 `data/qpr_table.csv` は legacy とし、必要時のみ study 側で明示。
- `radiation.mars_temperature_driver.table.path`:
  - 既定: `data/mars_temperature_T4000p0K.csv`
  - 併せて `time_unit=day`, `column_time=time_day`, `column_temperature=T_K` を固定。
- `shielding.table_path`:
  - 既定: `marsdisk/io/data/phi.csv`（shielding 有効時の標準）

**1D 標準の物理/数値（揃えるべきキー）**

- `sizes.s_min/s_max/n_bins`（1D 標準の bin 設計）
- `psd.alpha`, `psd.wavy_strength`, `psd.floor.mode`
- `qstar.coeff_units=ba99_cgs`（既存 sweep と合わせる）
- `radiation.source/mars_temperature_driver.enabled/mode`
- `numerics.t_end_years`, `numerics.dt_init`, `numerics.dt_over_t_blow_max`

**supply/sinks の既定**

- `supply.mode=const` と `supply.const.*` の既定値を base.yml に固定
- `sinks.mode` と `sinks.sub_params` は base.yml に固定（study 側での切替を許可）

**I/O は base.yml に置かない**

- `io.outdir` や `io.streaming.*` は runsets/overrides で統一

---

## base.yml 整備差分（run_temp_supply_sweep を基準）

**base.yml へ寄せる項目（run_temp_supply_sweep デフォルトの反映）**

- `disk.geometry.r_out_RM: 2.7`（内側円盤外縁の基準）
- `dynamics.dr_min_m: 1.2e6`, `dynamics.dr_max_m: 4.0e6`
- `initial.s0_mode: melt_lognormal_mixture` + `initial.melt_psd` ブロック追加
- `psd.floor.mode: none`
- `qstar.v_ref_kms: [1.5, 7.0]`
- `supply.injection.mode: powerlaw_bins`, `supply.injection.q: 3.5`
- `numerics.stop_on_blowout_below_smin: true`
- `phase.tau_field: los`（`temperature_input` と `q_abs_mean` は既に一致）
- `shielding.table_path: marsdisk/io/data/phi.csv`（mode=off でも標準を明示）
- `shielding.mode: "off"`（文字列で固定）

**runsets/overrides で上書きする項目（OS/運用差）**

- `numerics.dt_init`（mac: 20, windows: 2 の差分があるため）
- `numerics.t_end_until_temperature_K` / `t_end_temperature_margin_years`（COOL_* による）
- `radiation.mars_temperature_driver.table.path`（T に応じて切替）
- `initial.mass_total`（`INIT_MASS_TOTAL` で運用上決める）
- `io.outdir` / `io.streaming.*` / `ENABLE_PROGRESS`

> `psd.alpha_mode` は sweep YAML に存在するが schema には未定義のため、追加する場合は
> 「互換維持目的（無害）」として扱う。

---

## base.yml 具体修正案（現状 → 変更点一覧）

**値の置換・追加**

- `disk.geometry.r_out_RM`: `2.5` → `2.7`
- `dynamics.dr_min_m`: `7.5e5` → `1.2e6`
- `dynamics.dr_max_m`: `3.3e6` → `4.0e6`
- `initial.s0_mode`: `upper` → `melt_lognormal_mixture`
- `initial.melt_psd`: 追加（`f_fine=0.25`, `s_fine=1.0e-4`, `s_meter=1.5`, `width_dex=0.3`,
  `s_cut_condensation=1.0e-6`, `s_min_solid=1.0e-4`, `s_max_solid=3.0`, `alpha_solid=3.5`）
- `psd.floor.mode`: `fixed` → `none`
- `qstar.v_ref_kms`: `[3.0, 5.0]` → `[1.5, 7.0]`
- `supply.injection.mode`: **未設定** → `powerlaw_bins`
- `supply.injection.q`: **未設定** → `3.5`
- `numerics.stop_on_blowout_below_smin`: **未設定** → `true`
- `phase.tau_field`: **未設定** → `los`（明示）
- `shielding.table_path`: **未設定** → `marsdisk/io/data/phi.csv`
- `shielding.mode`: `off` → `"off"`（文字列で固定）

**base.yml から外す（runsets/overrides に移動）**

- `io.outdir`
- `io.debug_sinks`
- `io.correct_fast_blowout`
- `io.substep_fast_blowout`
- `io.substep_max_ratio`

**据え置き（run_temp_supply_sweep が上書き）**

- `numerics.dt_init`: `auto` を維持（runsets で上書き）
- `numerics.t_end_until_temperature_K`: 未設定のまま（COOL_* で上書き）
- `initial.mass_total`: `1.0e-5` を維持（`INIT_MASS_TOTAL` で上書き）
- `radiation.mars_temperature_driver.table.path`: `data/mars_temperature_T4000p0K.csv` を維持（T に応じて上書き）

---

## 非スコープ

- 物理モデル・式の変更
- `configs/` の大規模再配置
- `analysis/` の更新

---

## パターン別の運用

1. **完成済み YAML を使う運用**
   - `configs/base.yml` をコピーして `run.yml` などを作る
   - OS ごとの差分は `run.yml` に直接反映（merge 不要）
2. **共通 base + override をスクリプトで合成**
   - `overrides.txt` を読み込み、`--override` を並べて実行
   - 例: `python -m marsdisk.run --config configs/base.yml --override io.streaming.enable=true ...`
3. **小さな merge ツールを `merge_config.py` に置く**
   - `base.yml + study.yml + overrides.txt` を一時 YAML にしてから run
  - 生成物は `out/<run_id>/` か `scripts/runsets/<os>/_generated/` に置く

---

## 完了条件

- 1D 実行は `scripts/runsets/<os>/run_*` から完走できる
- 0D は `run_one.*` の明示フラグでのみ実行され、運用上の誤使用が減る
- 既存の `run_temp_supply_sweep*` は「共通ランナー」として機能し続ける
- quick-look plot と供給評価が runsets から呼び出せる
- checkpoint/run の分割実行が runsets の設定で明示できる
- Windows の `AUTO_JOBS` / `PARALLEL_JOBS` / `RUN_ONE` 運用が runsets で再現できる
- run.parquet の chunk/merge フローが runsets で統一される
- `configs/base.yml` が runsets のデフォルトとして安定して使用できる
- 旧スクリプト削除の前提条件が満たされている

---

## 実装チェックリスト

- [x] `scripts/runsets/` の骨子を追加（`common/`, `mac/`, `windows/`）
- [x] `scripts/runsets/common/base.yml` を `configs/base.yml` と整合させる
- [x] `scripts/runsets/<os>/run_one.*` を追加（`--t/--eps/--tau` 対応）
- [x] `scripts/runsets/<os>/run_sweep.*` を追加（`study_*.yml` と環境変数の両対応）
- [x] `scripts/runsets/<os>/overrides.txt` を追加（I/O・数値のみ）
- [x] `scripts/runsets/common/hooks/` を追加（plot/eval/preflight の薄いラッパー）
- [x] hooks の既定 ON/OFF と `HOOKS_*` 環境変数を整理
- [x] `configs/base.yml` の差分修正（run_temp_supply_sweep 基準）
- [x] `shielding.table_path` を base.yml へ追加
- [x] `io.*` を base.yml から外し、runsets 側に移す
- [x] Windows 並列 (`AUTO_JOBS`/`PARALLEL_JOBS`) を runsets/windows に移植
- [x] Windows 既定はセル並列（`PARALLEL_JOBS=1`, `MARSDISK_CELL_PARALLEL=1`）
- [x] 既存の簡易プロットが runsets でも出力できることを確認
- [x] chunk/merge の後処理（preflight + merge tool）動線を明記
- [x] `scripts/README.md` に runsets 導線を追記
