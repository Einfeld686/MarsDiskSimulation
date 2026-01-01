# 光学的厚さ-タイムスケール可視化プラン（昇華/衝突/放射圧）

目的と背景
----------
- 光学的厚さ（縦軸）に対して、昇華・衝突（t_coll）・放射圧（t_blow）のタイムスケールを同一図に重ね、支配的な時間スケール領域の移り変わりを把握する。
- 既存のシミュレーション出力（`out/<run_id>/series/run.parquet`）に記録済みの列を優先し、新規の物理式は導入しない。
- シミュレーションと可視化は Windows 機での実行を想定し、.cmd ランナーの作成を完了条件に含める（動的に CPU/メモリを取得して最適値を選択）。

対象・非対象
------------
- 対象: 0D/1D 実行の `out/<run_id>/series/run.parquet`（または streaming の `out/<run_id>/series/run_chunk_*.parquet`）。
- 対象: Windows 向け .cmd 実行スクリプト（動的リソース検出つき）。
- 非対象: 新しい物理式の導入、analysis/ の更新、TL2003 の新規適用。

入力データと使用カラム
----------------------
- 基本入力:
  - `out/<run_id>/series/run.parquet` または `out/<run_id>/series/run_chunk_*.parquet`
- 必須列（原則）:
  - `tau`（縦軸の光学的厚さ）
  - `t_coll`（衝突タイムスケール）
  - `t_blow_s` または `t_blow`（放射圧ブローアウト時間）
  - `s_min` または `s_min_effective`
  - `ds_dt_sublimation`（昇華でのサイズ変化速度）
  - `time`, `dt`（必要なら点の間引き/色分け）
  - 1D 用: `cell_index`, `cell_active`（セル集約のため）
- 補助列（存在すれば使用）:
  - `Omega_s`（t_coll が欠損した場合に `surface.wyatt_tcoll_S1` で補完する用途）

タイムスケール定義（既存列の利用）
--------------------------------
- 衝突: `t_coll` 列をそのまま使用。欠損時は `surface.wyatt_tcoll_S1(tau, Omega_s)` を呼び出して補完（同じ実装を利用）。
- 放射圧: `t_blow_s` または `t_blow` を優先使用。欠損時はスキップ。
- 昇華: `ds_dt_sublimation < 0` のとき `t_sub = s_min / |ds_dt_sublimation|` を算出（昇華が無効・ゼロの場合は NaN）。

可視化仕様（初期案）
--------------------
- 図種別:
  1) 基本図: x=タイムスケール[s]（対数軸）、y=光学的厚さ（`tau`、線形 or 対数はオプション）
  2) オプション: 時刻で色分けした散布図（進化の方向を可視化）
- 表示:
  - `t_sub`, `t_coll`, `t_blow` を色や線種で区別
  - 欠損の系列は自動で非表示
  - 1D の場合は `cell_active` を優先し、集約方法（median/mean）を選べるようにする

実装方針
--------
- 追加スクリプト: `scripts/plots/plot_tau_timescales.py`（既存 `plot_from_runs.py` と同様の構成）。
- 入力: `--run out/<run_id>`、複数 run の重ね描きにも対応可能にする。
- streaming 対応:
  - `out/<run_id>/series/run.parquet` が無い場合は `out/<run_id>/series/run_chunk_*.parquet` を `pyarrow.dataset` で読み込む。
  - 必要列のみを読み、メモリ使用量を抑える。
- 1D 集約:
  - `--reduce cell_median` / `cell_mean` のオプションを用意し、`cell_active` をフィルタ可能にする。
- Windows 実行:
  - `scripts/plots/windows/plot_tau_timescales.cmd` を新設し、`.venv` 作成・依存導入・実行までを一括化。
  - PowerShell 経由で論理 CPU 数と搭載メモリを取得し、`STREAM_MEM_GB`（または plot 用メモリ上限）を自動設定する。
  - 引数なし実行時は `out/<run_id>` 配下の最新 run を自動選択して可視化を実行する。
  - 既存の `.cmd` 運用ルール（`scripts/README.md`）に従ってパスと `OUTDIR` を扱う。

実装ステップ
------------
- [x] 仕様確定: 使用カラムと優先順位を固定（推奨: `t_blow_s` > `t_blow`, `s_min_effective` > `s_min`, `tau` > `tau_los_mars` > `tau_mars_line_of_sight`, `t_coll` 欠損時のみ `Omega_s` で補完）。
- [x] データローダ作成: parquet / chunked 両対応の読み込みを用意（推奨: 列射影は `time,tau,t_coll,t_blow_s,t_blow,s_min_effective,s_min,ds_dt_sublimation,Omega_s,cell_index,cell_active` の最小セット。chunked は `pyarrow.dataset` + `to_batches(batch_size=200000)`）。
- [x] タイムスケール算出: `t_sub`, `t_coll`, `t_blow` を列として追加し、NaN を除外（推奨: `t_sub=s_min_effective/abs(ds_dt_sublimation)` を既定、`ds_dt_sublimation>=0` は NaN、`t_*` は `finite & >0` のみ採用）。
- [x] 1D 集約: `cell_active` フィルタ + 時刻ごと集約を選択可能にする（推奨: `cell_active==True` を既定、集約は `cell_median` をデフォルト）。
- [x] プロット実装: matplotlib で `tau` vs timescale を描画、軸スケールと凡例を整理（推奨: x=log, y=log, `alpha=0.25`, `s=6`, `figsize=(7,4)`, `dpi=150`）。
- [x] 出力: `out/<run_id>/figures/tau_timescales.png`（または `--output-dir` 指定）（推奨: 既定出力先は `out/<run_id>/figures`、ファイル名は `tau_timescales.png` 固定）。
- [x] Windows .cmd: `scripts/plots/windows/plot_tau_timescales.cmd` を作成し、CPU/メモリ自動検出を組み込む（推奨: PowerShell で `TotalPhysicalMemory` と `NumberOfLogicalProcessors` を取得し、`MEM_GB=min(max(8, total_gb*0.6), total_gb-4)` を `STREAM_MEM_GB` に設定、`total_gb`/`logical_processors`/`MEM_GB` をログ出力）。
- [x] `scripts/README.md` の表に新しい .cmd の用途を追記（推奨: "tau timescale plot (Windows) / scripts/plots/windows/plot_tau_timescales.cmd" の 1 行追加）。

確認ポイント
------------
- [ ] 0D と 1D の両方で実行でき、欠損列があってもクラッシュしない。
- [ ] `t_sub` が 0/負値で無効化されるケースは NaN になり、プロットから除外される。
- [ ] streaming 出力（chunked）でも同じ図が作成できる。
- [ ] .cmd 実行時に CPU/メモリが自動検出され、計算されたメモリ上限がログに表示される。

完了条件
--------
- [ ] 1 run で `tau` vs `t_sub`/`t_coll`/`t_blow` の図を生成できる。
- [ ] 1D ケースでセル集約オプションが動作し、`cell_active` をフィルタできる。
- [ ] 出力図に軸ラベルと単位が明記される。
- [ ] Windows .cmd から可視化が完走し、動的メモリ設定が反映される。
