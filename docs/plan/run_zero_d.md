## 0. 目的

現状の外部供給は、設定の組合せ（mode / feedback / transport / headroom / solver など）が多く、式も複雑になりやすい一方で、「外部供給があるかどうか不明だが、もしあるとするなら」という仮定の上では、シミュレーション上の恣意的な挙動（表層を頭打ちにして深部へ戻す等）が混乱を生みます。そこで新規実装では、外部供給の仮定を増やさずに、**光学的厚さが大きくなりすぎると放射圧が届かない**という点だけを軸に、供給と停止条件を整理します。

---

## 1. 用語と基本式

ここで言う「光学的厚さ」は、**表層の面密度 Σ に対して、どれくらい放射が通りにくいか**を表す無次元量です。以後、この無次元量を **光学的厚さ（optical depth） τ** と呼びます。

本実装では、以下の関係を基本に置きます。

* 有効不透明度（「1 kg あたりの遮りやすさ」）
  [
  \kappa_{\mathrm{eff}} = \Phi(\tau),\kappa_{\mathrm{surf}}
  ]
  （(\kappa_{\mathrm{surf}}) は遮蔽なしの不透明度、(\Phi) は自遮蔽係数）

* τ=1 となる表層面密度（「表層として数えられる上限面密度」）
  [
  \Sigma_{\tau=1} = \kappa_{\mathrm{eff}}^{-1}\quad(\kappa_{\mathrm{eff}}>0)
  ]


この (\Sigma_{\tau=1}) は、「表層（放射圧が実効的に届く層）」を定義するための重要量です。現行実装ではクリップに使われていますが、新規実装では **“表層の定義”** と **“停止判定”** のために使います（後述）。

---

## 2. 設計方針

方針は次の3点に絞ります。

1. **外部供給は定常（時間一定）**とし、まずは温度スケール・τフィードバック・有限リザーバなどの追加仮定を入れない。
2. **表層の“頭打ち→溢れを深部へ戻す”をしない**。それを必要とする状況（表層が光学的に厚くなりすぎる状況）に到達したら、モデルの適用範囲外として **シミュレーションを終了**する。
3. **混合効率の表記は `epsilon_mix` に統一**し、供給量パラメータ μ（後述）と混同しない。現状の混乱点（`mu` が混合効率の別名になっている等）は、ここで断ち切る。

---

## 2.1 デフォルト/非推奨方針（全シミュレーション共通）

本ドキュメントの外部供給方針を **0Dシミュレーションのデフォルト**とし、以後の全シミュレーションはこれを前提にする。外部供給のデフォルト参照は `docs/plan/20251220_optical_depth_external_supply_impl_plan.md` と `~/.codex/plans/marsdisk-tau-sweep-phi-off.md` に限定し、それ以外の外部供給スイッチは非推奨・削除候補として扱う。

**デフォルトとして採用する挙動**
- `optical_depth` を有効化し、初期表層を `tau0_target` で規定する。
- 表層の頭打ち/クリップは行わず、`tau_los > tau_stop * (1 + tau_stop_tol)` で停止する。
- 供給は `mu_orbit10pct` を基準とした定常供給のみ（`epsilon_mix` と明確に分離）。
- 供給ゲートは相判定とステップ遅延など最小限の既存ゲートのみ許容。

**非推奨（互換維持のため当面残す）**
- `supply.feedback.*`（τフィードバック）
- `supply.transport.*`（deep_mixing など）
- `supply.headroom_policy`（頭打ち/クリップ）
- `supply.temperature.*`（温度スケール）
- `supply.reservoir.*`（有限リザーバ）
- `init_tau1.scale_to_tau1`（`optical_depth` と排他のため既定では使わない）
- `supply.mode` の非 `const` 設定、および `supply.injection` / `supply.injection.velocity` の**非デフォルト値**（現時点では完全廃止せず、非デフォルト使用時のみ警告）

これらは感度試験・比較用としてのみ使用し、デフォルト系と混同しない。

---

## 3. 光学的厚さの扱い（新規実装の核）

### 3.1 表層の定義（τ0 = 1 を採用）

初期状態で「表層として数える質量」を決めるため、遮蔽後の実効光学的厚さを

* 初期実効光学的厚さ：(\tau_0 = 1)

と置きます。ユーザ提案の通り、

[
\tau_0 = \kappa_{\mathrm{eff,0}},\Sigma_{\mathrm{surf,0}},\qquad
\kappa_{\mathrm{eff,0}} = \Phi_0,\kappa_{\mathrm{surf,0}}
]

なので、

[
\Sigma_{\mathrm{surf,0}}=\frac{\tau_0}{\kappa_{\mathrm{eff,0}}}
=\frac{1}{\Phi_0,\kappa_{\mathrm{surf,0}}}
]

で **初期表層面密度**が決まります。

* (\Phi_0) は「パラメータスタディで決める（あるいは Φ テーブルから τ=1 の値を採用する）」
* (\kappa_{\mathrm{surf,0}}) は「初期 PSD と不透明度評価ロジックから決める」

という役割分担にします。

> 補足
> 現行コードでも (\kappa_{\mathrm{eff}}) と (\Sigma_{\tau=1}) を計算する枠組み（E.015–E.017, E.016）が既にあり、ここは流用できます。

---

### 3.2 終了条件（「もはや表層ではない」判定）

新規実装では、**表層面密度が (\Sigma_{\tau=1}) を超える状況**を、モデルの適用範囲外と定義します。

* 現行のように (\Sigma_{\mathrm{surf}}) を (\Sigma_{\tau=1}) に“押し戻す”のではなく、
* (\Sigma_{\mathrm{surf}} > \Sigma_{\tau=1})（同値に (\tau>1)）が起きたら終了

とします。

実装上は、毎ステップの更新後（供給・衝突・昇華・ブローアウト適用後）に

* [
  \tau_{\mathrm{los}} = \kappa_{\mathrm{eff}},\Sigma_{\mathrm{surf}}
  ]
  を評価し、
* (\tau_{\mathrm{los}} > \tau_{\mathrm{stop}})（基本は (\tau_{\mathrm{stop}}=1)、数値誤差用に `1 + tol` を許容）なら停止

とします。

デフォルトの停止閾値は **透過率 10%** を基準に `tau_stop = ln(10)` とする。

こうすると、「放射圧が届く前提の表層モデル」を破る状況に入った時点で計算を止められ、**表層の頭打ち操作**や**深部へ戻す操作**を設計から排除できます。

---

## 4. 外部供給（定常）の定義：μ=1 を「1公転で初期表層の10%」に固定

### 4.1 μの定義（解析しやすさを優先）

ユーザ方針に合わせ、供給量パラメータ μ は次の意味に固定します。

* **μ=1：1公転あたり、初期表層面密度 (\Sigma_{\mathrm{surf,0}}) の 10% を供給する**

公転周期を (T_{\mathrm{orb}} = 2\pi/\Omega) とすると、μ=1 の供給率（面密度率）は

[
\dot{\Sigma}*{\mathrm{prod}}(\mu=1)
= 0.1,\frac{\Sigma*{\mathrm{surf,0}}}{T_{\mathrm{orb}}}
= 0.1,\Sigma_{\mathrm{surf,0}},\frac{\Omega}{2\pi}
]

一般の μ では

[
\dot{\Sigma}*{\mathrm{prod}}(\mu)
= \mu \times \dot{\Sigma}*{\mathrm{prod}}(\mu=1)
]

です。

ここで重要なのは、**μの基準を “初期表層” に固定する**点です。これにより、κ や Φ が時間で変わっても、μの解釈がぶれません。

---

### 4.2 `epsilon_mix` との関係（混同を完全に避ける）

供給計算の内部式は、既存の定義（E.027）を踏襲して

[
\dot{\Sigma}*{\mathrm{prod}} = \max!\left(\epsilon*{\mathrm{mix}},R_{\mathrm{base}},,0\right)
]

とします（ここで `epsilon_mix` が混合効率）。

したがって、上の μ定義を満たすためには、

[
R_{\mathrm{base}} = \frac{\dot{\Sigma}*{\mathrm{prod}}(\mu)}{\epsilon*{\mathrm{mix}}}
]

を用いて `R_base`（定常供給の生の率）を決めます。

> 注意
> 現状の整理メモにもある通り、既存設定では `supply.mixing.mu` が混合効率の別名になっており、μ（供給量パラメータ）と衝突しやすい状態です。新規実装では、混合効率は `epsilon_mix` のみを受け付け、μは別キー（例：`supply.const.mu_orbit10pct`）として分離します。

---

## 5. 実装フロー（1ステップ）

1ステップでの処理順は、現行のメインループ構造に沿わせつつ、**τ=1 クリップを停止判定へ置換**します。

1. 温度・放射圧係数などを更新（既存どおり）
2. PSD から (\kappa_{\mathrm{surf}}) を評価し、(\Phi) を適用して (\kappa_{\mathrm{eff}}) を得る（E.015–E.017）
3. (\Sigma_{\tau=1}=1/\kappa_{\mathrm{eff}}) を計算（E.016）
4. μと (\Sigma_{\mathrm{surf,0}}) から (\dot{\Sigma}_{\mathrm{prod}}) を計算し、`epsilon_mix` を使って `R_base` に落とす（E.027 の形を維持）
5. 供給・衝突・昇華・ブローアウトを適用して PSD/Σ を更新（既存ソルバを流用）
6. 更新後に (\tau_{\mathrm{los}}=\kappa_{\mathrm{eff}}\Sigma_{\mathrm{surf}}) を評価し、(\tau_{\mathrm{los}} > \tau_{\mathrm{stop}}) なら「表層モデル破綻」として終了（**クリップはしない**）

---

## 6. 設定（YAML案）

キー名は現行実装に合わせる。重要なのは、**μと `epsilon_mix` を別の概念として分離**することです。

```yaml
optical_depth:
  # 「表層として数える」初期基準
  tau0_target: 1.0
  # 表層モデルの適用範囲上限（透過率10%を基準）
  tau_stop: 2.302585092994046
  tau_stop_tol: 1.0e-6
  tau_field: tau_los   # 放射圧の到達に使う方向

shielding:
  mode: off

supply:
  mode: const
  const:
    # μ=1 → 1公転で初期表層の10%供給、という定義
    mu_orbit10pct: 1.0
    mu_reference_tau: 1.0
    orbit_fraction_at_mu1: 0.10
  mixing:
    epsilon_mix: 0.3     # 混合効率（表記固定）
  # 非推奨（legacy）: 温度スケール、τフィードバック、有限リザーバ、輸送モデル
  temperature:
    enabled: false
  feedback:
    enabled: false
  reservoir:
    enabled: false
  transport:
    mode: direct
```

---

## 7. 診断出力（最低限）

解析時に迷子にならないよう、次は必ず時系列に出します。

* `tau_los`（停止判定に使った τ）
* `kappa_surf`, `phi_used`, `kappa_eff`, `sigma_tau1`
* `Sigma_surf`, `Sigma_surf0`
* `mu_orbit10pct`, `epsilon_mix`, `dotSigma_prod`

停止した場合は `summary.json` に `stop_reason="tau_exceeded"` と最終 `tau_los` を記録します。

---

## 8. テスト（最小）

テストは「意味が固定されたこと」を確認するだけに絞ります。

* **μスケールのテスト**：衝突・昇華・ブローアウトを全部切った簡単系で、1公転後の増分が
  (\Delta\Sigma = 0.1,\mu,\Sigma_{\mathrm{surf,0}})
  になっていることを確認する。
* **停止条件のテスト**：供給だけを大きくして、(\tau_{\mathrm{los}}>\tau_{\mathrm{stop}}) で必ず止まり、クリップしていないことを確認する。

---

## 参照（この計画が依拠している現行仕様）

* 供給経路の整理メモ（分岐点と混同点の確認）
* 数式仕様（E.015–E.017: 遮蔽、E.016: (\Sigma_{\tau=1})、E.027: 供給定義）
* 手法・フロー（0Dの標準ループと各モジュールの位置づけ）
* 背景（gas-poor前提と放射圧・遮蔽の位置づけ）
