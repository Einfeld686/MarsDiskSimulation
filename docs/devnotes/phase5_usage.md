# フェーズ5（レガシー）単一過程モードと比較枠の使い方

## 単一過程トグル
- 設定キー: `physics_mode ∈ {"default","sublimation_only","collisions_only"}`。既定値 `"default"` は従来の複合モードと同一挙動。
- CLI からは `--physics-mode=<default|sublimation_only|collisions_only>` を渡す。`--override physics_mode=sublimation_only` も可。
- `sublimation_only` は昇華/ガス抗力のみを残し、Wyatt 型衝突項・ブローアウト・表層 ODE を停止する。`collisions_only` は昇華シンクを完全に無効化し、`sinks.enable_sublimation=true` でも質量損失への寄与が0になる。

## 比較ランナー（Phase5）
- 現行バージョンでは Phase5 比較ランナーと `--compare-physics-modes` フラグを廃止した。単一過程の比較が必要な場合は、`physics_mode` を切り替えた個別ランを用意し、post-processing で突き合わせる。

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
```
