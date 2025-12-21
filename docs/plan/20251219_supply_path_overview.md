# 外部供給経路の整理（0D / run_zero_d）

**作成日**: 2025-12-19  
**ステータス**: 整理メモ  
**対象**: `supply.*` の経路、表層（surface_ode）と Smol（smol）への注入

---

## 目的

外部供給の「どこで率が変わり、どの経路に流れ、どこで抑制されるか」を可視化し、
設定の複雑さ（mode/feedback/transport/headroom/solver）の整理に使う。

---

## 供給フロー（全体像）

1) **基礎供給率を決定**  
   `mode=const/powerlaw/table/piecewise` で `R_base` を決定し、混合効率を掛ける。  
   参考: E.027, `analysis/equations.md`  

2) **任意のスケーリング層**  
   温度スケール / τフィードバック / 有限リザーバで供給率を調整。  
   実装: `evaluate_supply`  
   参照: [marsdisk/physics/supply.py:287–379]

3) **供給ゲート（run_zero_d の条件）**  
   - `step_no > 0`  
   - 相が `solid` かつ `liquid_dominated` でない  
   これを満たさない場合、供給は 0 扱い。  
   参照: [marsdisk/run_zero_d.py:1768–1771]

4) **供給の分配（surface vs deep）**  
   `transport=direct/deep_mixing` と `headroom_policy=clip/spill` で表層・深部への振り分けを決定。  
   参照: [marsdisk/physics/supply.py:383–493]

5) **注入先の分岐（solver）**  
   - `surface_ode`: 表層 ODE に直接注入（E.007）  
     参照: [marsdisk/physics/surface.py:107–187]  
   - `smol`: PSD のソース `F_k` に変換して注入（E.045）  
     参照: [marsdisk/physics/collisions_smol.py:764–1110]

---

## 数式マップ（analysis/equations.md を参照）

> 物理式の本文は `analysis/equations.md` が唯一のソース。ここでは ID と適用箇所のみ整理する。

- **E.027: 外部供給率の定義**  
  `mode` から `R_base` を作り、`epsilon_mix` を掛けた供給率を定義。  
  参照: `analysis/equations.md` / [marsdisk/physics/supply.py:287–379]

- **E.027a: μ から `R_base` を復元**  
  供給パラメータ μ を用いた定数供給率の復元式。  
  参照: `analysis/equations.md` / [tools/derive_supply_rate.py:75–118]

- **E.007: 表層 ODE の更新式（surface_ode）**  
  `surface_ode` のときの表層更新と外向流束の定義。  
  参照: `analysis/equations.md` / [marsdisk/physics/surface.py:107–187]

- **E.045: 供給質量 → PSD ソース `F_k`**  
  Smol 解法で `prod_rate` をサイズビンへ配分するソース項。  
  参照: `analysis/equations.md` / [marsdisk/physics/collisions_smol.py:1075–1109]

- **E.031: τ=1 クリップ**  
  有効不透明度から `Sigma_tau1` を決める上限処理。  
  参照: `analysis/equations.md` / [marsdisk/physics/shielding.py:220–262]

---

## 分岐ポイント（どこで経路が変わるか）

### 供給率の生成
- `supply.mode`（const/powerlaw/table/piecewise）  
- `supply.mixing.epsilon_mix`（`mu` は別名だが意味は混合効率）  
  参照: [marsdisk/schema.py:145–168]

### 供給率のスケーリング
- `supply.temperature.*`（温度スケール or テーブル）  
- `supply.feedback.*`（τ誤差の比例制御）  
- `supply.reservoir.*`（有限リザーバ／枯渇・テーパ）  
  実装: [marsdisk/physics/supply.py:287–379]

### 供給の経路
- `supply.transport.mode`  
  - `direct`: 表層へ直行  
  - `deep_mixing`: 深部に貯蔵して `t_mix` で表層へ
- `supply.headroom_policy`  
  - `clip`: τ=1 の headroom で注入を抑制  
  - `spill`: 一旦注入してから τ=1 を超えた分を削る  
  実装: [marsdisk/physics/supply.py:383–493]

### τ=1 上限の適用条件
- `blowout.layer == "surface_tau_le_1"` かつ `collisions_active` のときのみ、
  `sigma_tau1_active` が supply に適用される。  
  参照: [marsdisk/run_zero_d.py:2229–2233]
- `shielding.mode` により `sigma_tau1_limit` が `inf` / fixed / kappa_eff 依存で変わる。  
  参考: E.031, `analysis/equations.md`

### solver 分岐
- `surface.collision_solver`  
  - `surface_ode`: 表層 ODE（E.007）  
  - `smol`: Smoluchowski（E.045）

---

## 注意点（混乱しやすい箇所）

1) **`supply.mixing.mu` は「供給パラメータ μ」ではなく混合効率**  
   `mu` は `epsilon_mix` の別名で [0,1] 制限がある。  
   参照: [marsdisk/schema.py:145–168]

2) **供給は「定常 mode」でも run 内で 0 になる条件がある**  
   相・ステップ 0 遅延・液相ブロックで供給が 0 になる。  
   参照: [marsdisk/run_zero_d.py:1768–1771]

3) **τ>1 を完全に避けるには設定の組合せが必要**  
   `sigma_tau1_active` が付く条件を満たさないと `clip/spill` が効かない。  
   参照: [marsdisk/run_zero_d.py:2229–2233], [marsdisk/physics/collisions_smol.py:764–1110]

---

## 0D シミュレーションフロー（供給関連）

```
for each step:
  compute tau/kappa and sigma_tau1_limit
  allow_supply = (step_no > 0) and solid phase and not liquid dominated
  supply_rate = evaluate_supply(...)
  prod_rate_applied = split_supply_with_deep_buffer(...)
  if surface_ode:
     step_surface(...)
  else:  # smol
     step_collisions(..., prod_rate_applied, sigma_tau1_active, headroom_policy)
```

**対応するコード経路**
- `sigma_tau1_limit` の計算と遮蔽分岐: [marsdisk/run_zero_d.py:2032–2062]  
- 供給ゲート条件: [marsdisk/run_zero_d.py:1768–1771]  
- `evaluate_supply`（温度/τフィードバック/リザーバ）: [marsdisk/physics/supply.py:287–379]  
- `split_supply_with_deep_buffer`（direct/deep_mixing と headroom）: [marsdisk/physics/supply.py:383–493]  
- `surface_ode` 経路: [marsdisk/physics/surface.py:107–187]  
- `smol` 経路（headroom clip/spill と PSD 注入）: [marsdisk/physics/collisions_smol.py:764–1110]

---

## 供給経路の出力（確認ポイント）

以下の列で供給の流れを追跡できる（`series/run.parquet`）。

- `prod_rate_raw` / `prod_rate_applied_to_surf`  
- `prod_rate_diverted_to_deep` / `deep_to_surf_flux`  
- `headroom` / `supply_tau_clip_spill_rate`  
  参照: [marsdisk/io/writer.py:158–166]

---

## 最小構成（単一路化したい場合の目安）

- `supply.mode="const"`  
- `supply.temperature.enabled=false`  
- `supply.feedback.enabled=false`  
- `supply.reservoir.enabled=false`  
- `supply.transport.mode="direct"`  
- `supply.headroom_policy="clip"`  
- `blowout.layer="surface_tau_le_1"`  
- `surface.collision_solver="smol"`

※ τ=1 を厳格に守りたい場合は、`shielding.mode` の設定も合わせて確認する。
