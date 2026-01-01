# plots再設計: 1D前提の時空間ヒートマップ

作成日: 2025-12-27  
ステータス: 確定

## 目的
- 本番は 1D、0D は検証用という方針に合わせて、plots を 1D 既定の表現へ寄せる。
- 横軸は時間 [yr]、縦軸は火星距離（r/R_Mars）とし、各種パラメータはヒートマップで表現する。
- 0D は互換性のために「単一半径の 1 行ヒートマップ」として扱う。

## 基本方針
- **X 軸**: 時間 [yr]。`time [s] / sec_per_year` で変換。
- **Y 軸**: 火星距離。`r_RM` があればそれを使い、なければ `r_m / R_Mars` を計算。
- **Z（色）**: パラメータ量。各量はヒートマップ化。
- **供給 headroom** はプロット対象外（方針により不要）。

## 図構成（1図に複数パラメータ）
- 「1図 = 1つの時空間キャンバス」を維持し、**小パネル複数枚（small multiples）**でパラメータを並べる。
  - 例: 2×2 / 2×3 のグリッドで共通の X/Y。
  - 各パネルに独立したカラーバー（単位込み）を付与。
- 0D の場合は縦軸が 1 行になるが、同じ描画ルーチンを使用する。

## データ入力と整形
- 入力: `out/<run_id>/series/run.parquet`（無い場合は `out/<run_id>/series/run_chunk_*.parquet` を読む）。
- 1D では `time` × `r_RM`（または `r_m`）で 2D 配列を構成。
  - 1ステップで同一 `(time, r_RM)` が複数存在する場合は **median** で集約。
- 列の優先順位:
  - 光学的厚さ: `tau_los_mars` → `tau_mars_line_of_sight` → `tau`
  - 半径: `r_RM` → `r_m / R_Mars`
- Downsample を許可する:
  - `--time-stride` / `--radius-stride`
  - `--max-rows`（自動間引き）

## 実データ観察（temp_supply_sweep_1d の例）
対象: `out/<run_id>`

- `out/<run_id>/series/run.parquet` は約 4.5GB、行数は約 5.1e7。
- `r_RM` は 32セルで等間隔（例: 1.0266–2.6734）。
- 時刻は `time`（秒）で、最終時刻は約 3.2e7 s（≒1.02 yr）。
- `tau_los_mars`, `r_RM`, `cell_index` が揃っており、**Y軸は r_RM をそのまま使用可能**。
- 1行のヒートマップを作るには **時間方向のダウンサンプリング必須**（全時刻×32セルで 1600万点超）。

反映すべき改善:
- [ ] **time binning** を既定にする（例: `max_time_bins=2000`）。
- [ ] r方向は 32セルなので既定は **stride=1**（全セル）。
- [ ] 計算は `pyarrow.dataset` でバッチ読み込みし、2D グリッドへ集約（mean/median）。

## 代表パラメータ（初期セット）
※ headroom は除外。

| 分類 | パラメータ | 表示名 | スケール | colormap |
| --- | --- | --- | --- | --- |
| 光学的厚さ | `tau`/`tau_los_mars` | τ | log10 | cividis |
| 表層量 | `Sigma_surf` | Σ_surf | log10 | cividis |
| ブローアウト | `M_out_dot` | M_out_dot | log10 | cividis |
| PSD 下限 | `s_min_effective` | s_min | log10 | cividis |
| 時間尺度 | `t_coll` | t_coll | log10 | cividis |
| 時間尺度 | `t_blow` | t_blow | log10 | cividis |
| 収支チェック | `smol_mass_budget_delta` | ΔΣ_budget | 線形 | RdBu_r（0中心） |

補足:
- 符号付き量（例: 収支残差）は **diverging** を使用。
- それ以外は **perceptually uniform**（cividis/viridis 系）を既定。

## UI/可視化ルール
- X 軸ラベル: `time [yr]`
- Y 軸ラベル: `r/R_Mars`
- colorbar に **単位** を必ず記載。
- 欠損値は薄いグレーで塗る（視認性優先）。
- **スケール自動判定**: `p95/p5 > 10` の場合は log10、そうでなければ線形。

## 確定事項
- **対象パラメータの優先度**  
  初期セットは表の順序（τ → Σ_surf → M_out_dot → s_min → t_coll → t_blow）を上位6枠とする。`smol_mass_budget_delta` は別ページまたはオプション扱い。
- **集約ルール（同一 time×r の重複）**  
  既定は median。加算量（例: M_out_dot）は sum に置換し、CLI で明示指定できるようにする。
- **色スケールの下限/上限**  
  log10 指標は panel ごとに 1–99% の分位クリップ。符号付き量は 99% 絶対値で対称クリップ。
- **0D の扱い**  
  r/R_Mars=一定の1行ヒートマップとして描画し、図タイトルに「0D」注記を付ける。
- **colormap**  
  sequential は `cividis`、diverging は `RdBu_r`（0中心）を既定とする。
- **出力先の既定**  
  `run_dir/figures/` を既定に統一し、`--out` で上書き可能とする。
- **パネル数の上限**  
  1図あたり最大6パネル（2×3）。超過時は自動分割で複数ページにする。

## 実装案（スクリプト構成）
- [ ] `scripts/plots/plot_time_radius_heatmap.py` を新設  
  - `--run-dir` / `--metrics` / `--out` / `--time-stride` / `--radius-stride`
  - 1D を既定として設計
- [ ] 既存 `plot_*` は **legacy** として残置し、README に 1D/0D 対応を明記
- [ ] `plot_from_runs.py` は 1D 既定の panels を呼ぶフロントに再構成

## 受け入れ基準
- すべての plot が **時間 [yr]** と **r/R_Mars** の軸を持つ。
- 各パラメータは **ヒートマップ**として描画される。
- headroom は一切出力しない。
- 1D での出力が既定となる（0D は補助扱い）。
