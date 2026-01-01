# 目的
- `scripts/runsets/windows/legacy/run_sublim_cooling.cmd` 実行時にメモリが 120 GB 超まで膨張した問題を整理し、再発防止の運用パラメータを決める。

# 背景・現状
- 現行テンプレート `out/<run_id>/config_base_sublimation.yml` は `numerics.dt_init=2.0 s`、`t_end_years=0.5`、`n_bins=40` で走っている。
- 2.45 R_M 付近では `t_blow≈3.7e3 s` となり、`dt_init` が極端に小さいため約 7.9×10^6 ステップ→ `psd_hist` だけで ~3.1×10^8 行となり、Python のリスト保持中に 100 GB 超に達する。
- 24% 進捗時の 120 GB 使用はこのステップ数と行数の規模と一致。

# ChatGPT Pro への提示用メモ
- 軌道条件（代表半径 r≈2.45 R_M）: Ω≈2.73e-4 s^-1、t_blow=1/Ω≈3.66e3 s、T_orb≈2.30e4 s。
- 衝突時間の基準式: Wyatt スケール `t_coll ≈ T_orb / (4π τ)`。本テンプレートは τ を明示していないため、外挿する際は τ=O(0.1–1) を想定して評価してもらう。
- 許容基準: `dt ≤ 0.1 * min(t_blow, t_coll)` を守ること、実行後は `dt_over_t_blow` の中央値≲0.1・最大≲0.2 をチェックする。
- デフォルトの PSD 解像度は `n_bins=40`（下げる場合の下限目安は 30）。`out/<run_id>/series/psd_hist.parquet` は (time, bin_index, s_bin_center, N_bin, Sigma_surf) を全ステップ×全ビンで保持する。

# 課題
- `dt_init` が小さすぎてブローアウト時間に対して過剰解像となり、I/O 用の履歴バッファがメモリを圧迫。
- 衝突カスケードの時間解像度を落としすぎない範囲で、ステップ数を 2 桁以上削減したい。

# 対応方針（短期）
- まずは `dt_init` を `auto` または `t_blow×(0.05–0.1)`（本ケースでは 180–370 s）に引き上げ、ステップ数を ~8.9e4 以下へ削減する。
- 実行前に `python -m tools.utilities.memory_probe --config out/<run_id>/config_base_sublimation.yml --override numerics.dt_init=auto` で行数と概算メモリを確認する。
- それでも厳しければ `sizes.n_bins` を 30 へ下げる（行数を約 25% 削減）。`psd_hist` の保持列は変えない。
- 再実行後は `out/<run_id>/series/run.parquet` の `dt_over_t_blow` を確認し、中央値≲0.1・最大≲0.2 を目安にする。`out/<run_id>/checks/mass_budget.csv` の誤差 0.5% 以内も併せてチェック。

# 非対象
- 衝突解法や I/O レイアウトの抜本的変更、Smol コアのスパース化は本プランの対象外。

# リスクとモニタ
- `dt_init` を大きくしすぎるとブローアウトの指数減衰が粗くなり、表層フラックスが過少/過大になるリスク。上記目安を超えない設定で抑制。
- `n_bins` を減らすことで PSD の波打ち構造が滑らかになりすぎる可能性。検証時に `psd_hist` を簡易プロットして波打ちの有無を確認する。***
