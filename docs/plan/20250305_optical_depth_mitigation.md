# 光学的厚さが高止まりするケースへの対処（遮蔽は維持）

> 作成日: 2025-03-05  
> 区分: 運用ノート（シミュレーション調整ガイド）

---

## 本プロジェクト・ドキュメントについて

### プロジェクト概要

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードを2年間シミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](../../analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](../../analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- **AI向け利用ガイド**: [analysis/AI_USAGE.md](../../analysis/AI_USAGE.md)

### 用語定義

本ドキュメントで使用される主な用語を以下に定義します：

| 用語 | 意味 | 参考 |
|------|------|------|
| $\tau$ (τ) | **光学的厚さ** (optical depth)。円盤の不透明度を表す無次元量。$\tau = \kappa_{\rm eff} \cdot \Sigma_{\rm surf}$ | (E.015)–(E.017) |
| $\tau_{\rm vertical}$ | **鉛直光学的厚さ**。円盤面に垂直な方向での光学的厚さ | — |
| $\tau_{\rm los}$ | **視線方向光学的厚さ**。火星から見た視線方向での光学的厚さ。遮蔽判定に使用 | — |
| $\Sigma_{\tau=1}$ (`sigma_tau1`) | **臨界面密度**。$\tau = 1$ となる表層面密度。$\kappa_{\rm eff}^{-1}$ として計算 | (E.016), (E.017) |
| $\Sigma_{\rm surf}$ | **表層面密度** (surface density)。放射の影響を受ける表層の質量密度 | (E.007) |
| $\Phi(\tau)$ | **自遮蔽係数** (self-shielding factor)。光学的に厚い円盤での放射減衰を表す [0–1] の係数 | (E.015), (E.028) |
| $\kappa_{\rm eff}$ | **有効不透明度** (effective opacity)。$\kappa_{\rm eff} = \Phi(\tau) \cdot \kappa_{\rm surf}$ | (E.015) |
| **headroom** | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$。表層が τ=1 を超えないための「余裕」 | (E.031) |
| **spill** | headroom 超過分を即時除去するモード | [supply_headroom_policy_spill](./20251220_supply_headroom_policy_spill.md) |
| **deep_mixing** | 深部リザーバ→表層への物質輸送モード | [supply.py](../../marsdisk/physics/supply.py) |

### ドキュメントの位置付け

`docs/plan/` 内のドキュメントは開発プラン・イシュー整理・運用ノートを管理します。本メモは **光学的厚さ τ が高止まりするケースの調整方法**を示す運用ガイドです。

関連ドキュメント：
- [20251219_tau_clip_gate_review.md](./20251219_tau_clip_gate_review.md) — τクリップと供給ゲートの現状整理
- [20251220_supply_headroom_policy_spill.md](./20251220_supply_headroom_policy_spill.md) — headroom 処理の spill モード提案
- [20251216_temp_supply_sigma_tau1_headroom.md](./20251216_temp_supply_sigma_tau1_headroom.md) — 供給クリップ事象の報告

---

## 背景

### 問題の概要

シミュレーション実行時に、**光学的厚さ τ が想定より高い値（τ > 1）で推移し続ける**ケースがある。本来、火星からの放射圧が効果的に働くためには τ ≈ 0.5–1.0 程度が望ましい。τ が高すぎると：

1. 自遮蔽により放射圧が表層にしか届かず、ブローアウト効率が低下する
2. 供給が headroom クリップで遮断され、定常状態の比較が困難になる
3. 診断値の解釈が複雑になる

### 前提条件

- Φテーブル（例: Φ = 0.20 / 0.37 / 0.60）と遮蔽モード（`shielding.mode="psitau"`）は**変更しない**
- $\tau_{\rm vertical}$ / $\tau_{\rm los}$ が 1 付近へ下がるよう運用パラメータを調整する

---

## 候補手段

### 1. 初期クリップを弱める (`init_tau1`)

`init_tau1.target_tau` を 0.3–0.5 程度へ下げ、`init_tau1.scale_to_tau1=true` のまま初期 $\Sigma_{\rm surf}$ を抑える。初期質量も自動で縮小される。

```yaml
init_tau1:
  enabled: true
  target_tau: 0.4
  scale_to_tau1: true
```

**コード参照**: [marsdisk/run_zero_d.py#L1599–L1700](../../marsdisk/run.py) — `init_tau1` 処理

### 2. 供給を絞る (`supply.const`)

`supply.const.prod_area_rate_kg_m2_s` を 1 桁以上下げる（例: 1.0 → 0.1 または 0.01）か、`supply.mixing.mu` を < 1 にして表層混合を遅らせる。

```yaml
supply:
  mode: "const"
  const:
    prod_area_rate_kg_m2_s: 0.1  # 1.0 → 0.1
  mixing:
    mu: 0.5  # < 1 で混合を遅延
```

**式参照**: (E.027a) 供給率 $R_{\rm base}$ の定義

### 3. フィードバックで τ を狙う (`supply.feedback`)

`supply.feedback.enabled=true` にして `target_tau ≈ 0.5–1.0` を指定し、`gain` を 1–2 程度、`response_time_years` を 0.3–0.5 に設定して供給を自動減衰させる。

```yaml
supply:
  feedback:
    enabled: true
    target_tau: 0.8
    tau_field: "tau_los"
    gain: 1.5
    response_time_years: 0.4
```

**コード参照**: [marsdisk/physics/supply.py#L147](../../marsdisk/physics/supply.py) — フィードバック制御

### 4. ヘッドルームポリシーを spill に (`supply.headroom_policy`)

`supply.headroom_policy=spill` に変え、τ > 1 で即時に溢れた分を捨てるようにする。

```yaml
supply:
  headroom_policy: spill  # 従来は "clip"
```

> [!WARNING]
> spill モードでは超過質量が系外ロスとして扱われる。質量保存検証時には `supply_tau_clip_spill_rate` カラムに注意。

**詳細**: [20251220_supply_headroom_policy_spill.md](./20251220_supply_headroom_policy_spill.md)

### 5. 深層バッファを使う (`supply.transport.mode`)

`supply.transport.mode=deep_mixing` かつ `t_mix_orbits` を短め（例: 10–30）にし、余剰供給を深層に逃がした上でゆっくり戻す。

```yaml
supply:
  transport:
    mode: "deep_mixing"
    t_mix_orbits: 20
```

**コード参照**: [marsdisk/schema.py#L300–L320](../../marsdisk/schema.py) — `deep_mixing` スキーマ

### 6. 昇華シンクを強める (`sinks.sub_params`)

`sinks.sub_params` の `eta_instant` を上げる、`T_sub` を高めるなどで $t_{\rm sink}$ を短縮し、厚い層を削る。

```yaml
sinks:
  mode: "sublimation"
  sub_params:
    eta_instant: 0.2  # 既定 0.1 → 0.2
    T_sub: 1400       # 既定 1300 → 1400
```

> [!CAUTION]
> 過度にすると blowout と競合するため安定性確認を推奨。

**式参照**: (E.018)–(E.019) 昇華フラックスとシンク時間スケール

---

## 運用メモ

- 上記を組み合わせても τ > 1 に張り付く場合は、まず**供給レートとフィードバックを優先して調整**し、その後 spill / deep_mixing で余剰を逃がすと安定しやすい
- Φテーブルはそのままなので、$\tau_{\rm vertical}$ の目安はおおむね $1/\Phi$ に近い値からのスタートになる。`target_tau` や供給でそれを上書きして下げる発想になる

---

## 参考

### 関連ドキュメント

- 物理式の詳細: [analysis/equations.md](../../analysis/equations.md) — (E.015)–(E.017) 遮蔽、(E.031) τ=1 クリップ
- シミュレーション実行方法: [analysis/run-recipes.md](../../analysis/run-recipes.md)
- 設定ガイド: [analysis/config_guide.md](../../analysis/config_guide.md) — §3.9 shielding、§3.5 supply
- 用語集: [analysis/glossary.md](../../analysis/glossary.md)

### コード参照

| 機能 | ファイル | 備考 |
|------|----------|------|
| 遮蔽係数 Φ 適用 | [shielding.py#effective_kappa](../../marsdisk/physics/shielding.py) | L81–120 |
| Σ_{τ=1} 計算 | [shielding.py#sigma_tau1](../../marsdisk/physics/shielding.py) | L123–130 |
| τ=1 クリップ | [shielding.py#clip_to_tau1](../../marsdisk/physics/shielding.py) | L219–261 |
| 初期 τ クリップ | [run.py](../../marsdisk/run.py) | L1599–1700 (`init_tau1`) |
| 供給フィードバック | [supply.py](../../marsdisk/physics/supply.py) | L147 (`feedback_tau_field`) |
| headroom ポリシー | [collisions_smol.py](../../marsdisk/physics/collisions_smol.py) | L476–480 |
