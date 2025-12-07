# フェーズ5 単一過程モードと比較枠の使い方

## 単一過程トグル
- 設定キー: `physics_mode ∈ {"default","sublimation_only","collisions_only"}`。既定値 `"default"` は従来の複合モードと同一挙動。[marsdisk/run.py:845–1180]
- CLI からは `--physics-mode=<default|sublimation_only|collisions_only>` を渡す。`--override physics_mode=sublimation_only` も可。
- `sublimation_only` は昇華/ガス抗力のみを残し、Wyatt 型衝突項・ブローアウト・表層 ODE を停止する。`collisions_only` は昇華シンクを完全に無効化し、`sinks.enable_sublimation=true` でも質量損失への寄与が0になる。[marsdisk/run.py:872–1342]

## 比較ランナー（Phase5）
- 設定: `phase5.compare.enable=true` と `phase5.compare.duration_years`（既定2年）、`mode_a`/`mode_b`（例: `collisions_only` / `sublimation_only`）と `label_a`/`label_b` を指定する。CLI フラグ `--compare-physics-modes` も同等の挙動を強制する。
- ランは `run_phase5_comparison` がまとめて実行し、指定モードの2本を同一初期状態から分岐させる。[marsdisk/run.py:2232–2406]
- それぞれのサブランは `out/variants/variant=<label>/` に通常出力を生成し、最後にベース outdir に集約成果物を再構築する。

- `out/series/*.parquet`（run/diagnostics/psd_hist）は `variant` 列付きの結合テーブルへ差し替えられ、元データは `out/variants/...` に保持される。[marsdisk/run.py:2142–2177]
- `out/series/orbit_rollup_comparison.csv` には `variant,duration_yr,M_loss_total,M_loss_blowout,M_loss_other_sinks,beta_mean,a_blow_mean,s_min_final,tau1_area_final,notes` の2行が並ぶ。`out/orbit_rollup.csv` は衝突モードのログをコピーする。[marsdisk/run.py:2188–2209]
- `out/summary.json` の `phase5.compare` セクションに各 variant の `M_loss`・解析期間・代表半径・`s_min_initial`・`config_hash_sha256` が記録される。`run_config.json` も同様に `phase5_compare` ブロックを持ち、variant ごとの outdir/summary/run_config パスとハッシュを追跡する。[marsdisk/run.py:2211–2270]

## 使用例
```bash
# 標準（総合モード）
python -m marsdisk.run --config configs/base.yml

# 昇華のみ（単一過程）
python -m marsdisk.run --config configs/base.yml \
  --physics-mode=sublimation_only

# 衝突のみ（単一過程）
python -m marsdisk.run --config configs/base.yml \
  --physics-mode=collisions_only

# 比較枠（2年）
python -m marsdisk.run --config configs/base.yml \
  --compare-physics-modes \
  --override phase5.compare.duration_years=2
```
