# 現行物性セットの整理（SiO₂光学 × 玄武岩密度 × SiO蒸気）

**作成日**: 2025-12-26  
**ステータス**: 調査・整理  
**関連ファイル**: [`configs/base.yml`](file:///Users/daichi/marsshearingsheet/configs/base.yml), [`analysis/AI_USAGE.md`](file:///Users/daichi/marsshearingsheet/analysis/AI_USAGE.md)

---

## 背景：火星ダスト円盤シミュレーションとは

本プロジェクトは、**火星のロッシュ限界内に形成される高密度ダスト円盤**の進化をシミュレーションするものです。巨大衝突によって生成されたデブリが火星周回軌道上で円盤を形成し、以下のプロセスを経て質量を失っていく過程を追跡します：

1. **粒子衝突による破砕**：大きな粒子が衝突で細かく砕かれる
2. **放射圧によるブローアウト**：光（太陽光・火星からの熱放射）を受けた微小粒子が軌道から吹き飛ばされる
3. **昇華による蒸発**：高温環境下で固体粒子が蒸発する

シミュレーションの正確性は、**使用する物質の物性値**（密度、光学特性、蒸発特性など）に大きく依存します。

---

## 用語解説

| 用語 | 説明 |
|------|------|
| **SiO₂（二酸化ケイ素）** | 石英・シリカ。透明〜半透明で光学特性が比較的よく研究されている物質 |
| **玄武岩** | 火山岩の一種。火星表面の主要構成物質で、密度は約 2900–3200 kg/m³ |
| **SiO（一酸化ケイ素）** | 高温環境下で SiO₂ が分解して生成される蒸気種 |
| **⟨Q_pr⟩** | Planck 平均した放射圧効率因子。光がどれだけ粒子を押すかを表す無次元量 |
| **β（ベータ）** | 放射圧と重力の比。β ≥ 0.5 なら粒子は軌道から吹き飛ばされる |
| **a_blow** | ブローアウト半径。β = 0.5 となる粒径で、これより小さい粒子は即座に失われる |
| **Q\*** | 衝突破壊強度。粒子を完全に破壊するのに必要なエネルギー指標 |
| **ρ（rho）** | バルク密度（単位: kg/m³）|
| **HKL 式** | Hertz–Knudsen–Langmuir 式。蒸発速度を計算するための古典的な式 |

---

## 目的

`configs/base.yml`（0D 標準設定）で実際に用いている物性値を一箇所にまとめ、**玄武岩 vs SiO₂ の混在状況を可視化**する。計算結果の解釈や今後の材質統一（純玄武岩・純 SiO₂ など）の議論の土台とする。

---

## 1. デフォルト値と出典
- バルク密度: `material.rho=3000.0` kg/m³（玄武岩寄り）。検証レンジは [1000,5000] kg/m³（`configs/base.yml:11-13`, `marsdisk/schema.py:526-538`）。
- 放射物性（⟨Q_pr⟩）: `radiation.qpr_table_path="marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv"` を参照し、`Q_pr` 明示値は未設定 → SiO₂ キャリブレーション表を使用（`configs/base.yml:105-112`）。
- 相変化/フェーズ判定: SiO₂ 冷却マップを entrypoint にし、凝縮/蒸発閾値は 1700/2000 K（`configs/base.yml:142-151`）。
- 昇華（HKL）: 蒸気種を SiO とみなした μ=0.0440849 kg/mol, A/B=13.613/17850、液相枝 A_liq/B_liq=13.203/25898.9、α=0.007、valid_K=(1270,1600)、液相スイッチ 1900 K（`configs/base.yml:81-99`, `marsdisk/schema.py:845-904`, `marsdisk/physics/sublimation.py:606-682`）。`mass_conserving=true`。
- 衝突強度 Q*: BA99 cgs 系の係数セット（Qs=3.5e7, a_s=0.38, B=0.3, b_g=1.36, v_ref=[3,5] km/s）で石質（玄武岩系）を想定（`configs/base.yml:43-47`）。
- ブローアウト/β: 上記 ρ と SiO₂ ⟨Q_pr⟩ テーブルを組み合わせて a_blow を計算し、`blowout.enabled=true` で表層 τ≤1 に適用（`configs/base.yml:138-141`）。ρ を上げると a_blow が縮み、Q_pr が高いほど a_blow が小さくなるため、光学と密度の組み合わせが重要。

## 2. 観察される混在

現在の設定では、**異なる物質の物性値が混在**しています。これは歴史的経緯と利用可能なデータの制約によるものです。

### 物性値の出典マトリクス

| 物性カテゴリ | 現在の設定値 | 想定物質 | 影響する計算 |
|-------------|-------------|---------|-------------|
| バルク密度 ρ | 3000 kg/m³ | **玄武岩** | β計算、a_blow |
| 衝突強度 Q* | BA99 石質係数 | **玄武岩** | 破砕確率 |
| 光学効率 ⟨Q_pr⟩ | SiO₂ テーブル | **SiO₂** | β計算、放射圧 |
| 相変化閾値 | 1700/2000 K | **SiO₂** | 凝縮/蒸発判定 |
| 吸収効率 q_abs | 0.4 | **SiO₂** | 粒子加熱 |
| 昇華パラメータ μ, A, B | SiO 蒸気値 | **SiO** | 蒸発速度 |

### なぜこれが問題か？

```
┌─────────────────────────────────────────────────────────────┐
│  現在のハイブリッド設定                                      │
│                                                             │
│   密度 ρ ─────┬──→ β = f(ρ, Q_pr) ──→ ブローアウト判定     │
│   (玄武岩)     │                                            │
│               │                                             │
│   Q_pr ───────┘                                             │
│   (SiO₂)          ↑ 物質が一致していない                    │
│                                                             │
│   昇華速度 ←── μ, A, B (SiO 蒸気)                          │
│                   ↑ 蒸気種も別物質                          │
└─────────────────────────────────────────────────────────────┘
```

**結論**: 「玄武岩密度 × SiO₂ 光学 × SiO 蒸気」という**異種混成セット**になっており、物理的一貫性が保証されていない。

> [!WARNING]
> この混在は計算結果の定量的な精度に影響する可能性があります。ただし、現状では利用可能な実験データと理論値の制約から、この設定がプロジェクトの標準となっています。

---

## 3. 今後の検討軸

材質を統一する場合（例：純玄武岩）、以下の項目を更新する必要があります：

### 3.1 光学特性の更新
```yaml
# configs/base.yml での変更例
radiation:
  qpr_table_path: "marsdisk/io/data/qpr_planck_basalt_<source>.csv"  # 要生成
```
- 玄武岩の複素屈折率データから Mie 計算を実行し、新しい ⟨Q_pr⟩ テーブルを生成する

### 3.2 昇華パラメータの更新
```yaml
# configs/base.yml での変更例
sinks:
  sub_params:
    mu: <basalt_vapor_mu>       # 玄武岩蒸気の分子量
    A: <basalt_A>               # Clausius-Clapeyron 係数
    B: <basalt_B>
```

### 3.3 相変化閾値の更新
```yaml
# configs/base.yml での変更例
phase:
  thresholds:
    T_condense_K: <basalt_solidus>
    T_vaporize_K: <basalt_liquidus>
```

### 3.4 一貫性検証
統一後は以下のテストを実行して妥当性を確認：

```bash
# 短時間の質量収支テスト
python -m marsdisk.run --config configs/base.yml \
    --override material.rho=3000.0 \
    --override numerics.t_end_years=0.1
```

---

## 4. 検証と調査の手引き

### すぐに試せる感度テスト

| テスト内容 | コマンド例 |
|-----------|-----------|
| 密度だけ変更 | `--override material.rho=2500.0` |
| Q_pr テーブル差替 | `--override radiation.qpr_table_path="path/to/new_table.csv"` |
| 昇華オフ | `--override sinks.mode="none"` |

### 出力ファイルの確認ポイント

| ファイル | 確認すべき列 | 意味 |
|----------|-------------|------|
| `out/series/run.parquet` | `a_blow` | ブローアウト粒径 |
| 同上 | `beta_at_smin_*` | 最小粒径での β 値 |
| 同上 | `M_sink_dot` | 昇華による質量損失率 |
| `out/summary.json` | `case_status` | "blowout" / "ok" の判定 |
| `out/checks/mass_budget.csv` | `error_percent` | 質量保存誤差（< 0.5% が目標）|

### 参考ドキュメント

- 質量収支の検証手順 → [`analysis/AI_USAGE.md`](file:///Users/daichi/marsshearingsheet/analysis/AI_USAGE.md)
- 設定スキーマの詳細 → [`marsdisk/schema.py`](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py)
- 放射圧計算の実装 → [`marsdisk/physics/radiation.py`](file:///Users/daichi/marsshearingsheet/marsdisk/physics/radiation.py)
- 昇華計算の実装 → [`marsdisk/physics/sublimation.py`](file:///Users/daichi/marsshearingsheet/marsdisk/physics/sublimation.py)

---

## 5. 変更履歴

| 日付 | 内容 |
|------|------|
| 2025-12-26 | 初版作成 |
| 2025-12-18 | 外部読者向けに背景・用語解説・詳細説明を追加 |
