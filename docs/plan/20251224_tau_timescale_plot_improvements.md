# τ-timescale プロット改善案 (1D 可視化対応)

## 目的
- 1D 出力の可視化で「半径依存」「時間推移」「τ 定義」を読み取りやすくする。
- 既存の `scripts/plot_tau_timescales.py` を拡張し、最小限のオプション追加で比較性を高める。

## 背景・現状
- 現行の散布図は τ と timescale の相関は把握できるが、1D の半径依存が色以外に表現されず読み取りづらい。
- τ の定義（`tau_los_mars` / `tau_mars_line_of_sight` / `tau`）が軸ラベルで判別しづらい。
- 時間推移の可視化が散布のみで、開始/終了の境界が読み取りにくい。

## 改善方針
1. **半径情報の表現強化**
   - `--color-by radius` を 기본としつつ、`cell_index` ごとの **細線トラック**（同一セルの時間推移）を追加する。
   - `--reduce none` が有効な場合のみトラック描画を許可し、`cell_median`/`cell_mean` では無効。

2. **τ 定義の明示**
   - 実際に使用した τ カラム名を y 軸ラベルに反映する。
   - 例: `tau (los to Mars)` / `tau (vertical)` / `tau`。

3. **時間情報の視認性向上**
   - `--color-by time` の場合、カラーバーの `vmin/vmax` を凡例注記として表示（開始/終了時刻）。
   - 可能なら軽量なサブタイトルに `t_start`/`t_end` を追加。

4. **代表線の併記（トレンド可視化）**
   - `--reduce cell_median` 時に、中央値の timescale を線で上書き。
   - `t_sub`/`t_coll`/`t_blow` それぞれ細線で追加。

5. **ダイナミックレンジの調整**
   - log スケール時の極端な外れ値を抑制するため、`--clip-timescale-min` を追加。
   - クリップ値はデフォルト無効（None）。

6. **1D 専用インセット（任意）**
   - 右上に `r/R_M` vs `tau` の小プロットを入れ、半径依存の方向性を可視化。
   - これはオプション `--with-inset` で有効化。

## 実装タスク
- [x] `scripts/plot_tau_timescales.py`: y 軸ラベルに `used['tau']` を反映。
- [x] `scripts/plot_tau_timescales.py`: `--reduce none` の場合にセル別トラック描画を追加。
- [x] `scripts/plot_tau_timescales.py`: `--reduce cell_median` の場合は中央値トレンド線を追加。
- [x] `scripts/plot_tau_timescales.py`: `--color-by time` のとき開始/終了時刻の注記を追加。
- [x] `scripts/plot_tau_timescales.py`: `--clip-timescale-min` を追加（log スケール時の下限クリップ）。
- [x] `scripts/plot_tau_timescales.py`: `--with-inset` を追加（`r/R_M` vs `tau` インセット）。
- [x] `scripts/README.md`: 新オプションの使い方を追記。

## 受入基準
- 1D 出力で `--color-by radius --reduce none` を使ったとき、同一セルの時間推移が視認できる。
- `--color-by time` 使用時に開始/終了時刻が凡例またはサブタイトルで確認できる。
- y 軸ラベルが τ の採用カラム名を明示している。
- 新オプションを使わない場合、既存出力と同等の図が生成される。

## 決定事項
- `--color-by radius` は 1D 実行のみで有効化する。
- インセットは固定位置・固定サイズで実装する。
- `cell_active` のみを描画対象とする。
- τ ラベルは日本語表記に統一する。

## メモ
- 既存の `docs/plan/20251223_tau_timescale_plot_plan.md` を破壊せず、追補として位置付ける。
- `--with-inset` は matplotlib 依存が増えるため軽量化を維持する。
