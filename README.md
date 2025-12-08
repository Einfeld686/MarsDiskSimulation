# Mars Disk Simulation

> **火星ロッシュ限界内ダスト円盤の衝突・放射圧・昇華過程シミュレーション**

---

## 🌍 このプロジェクトについて

### 科学的背景

火星の衛星フォボス・ダイモスの起源は、巨大衝突による火星周回円盤から形成されたとする説が有力です（Rosenblatt 2011, Canup & Salmon 2018）。本シミュレーションは、ロッシュ限界（~2.4 火星半径）内に形成された高温・高密度ダスト円盤の時間進化を追跡します。

**3つの主要過程をモデル化:**

1. **衝突カスケード** — 粒子同士の衝突による破砕・再分布
2. **放射圧 blow-out** — 火星からの赤外放射による小粒子の吹き飛ばし
3. **昇華** — 高温環境での粒子蒸発

### 主な出力

- 2年間の質量損失履歴と累積質量損失

  $$\large
  \dot{M}_{\rm out}(t),\quad M_{\rm loss}
  $$

- 粒径分布（PSD）の時間発展

- blow-out 境界サイズの動的変化

  $$\large
  a_{\rm blow}
  $$

---

## 📚 ドキュメントガイド

```text
どこから読むべき？

┌─ 初めての方 ────────────────────────────────────────────┐
│   README.md（このファイル）                              │
│       ↓                                               │
│   analysis/config_guide.md ──→ 設定の書き方             │
│   （🚀 クイックスタートから開始）                         │
├─────────────────────────────────────────────────────────┤
│ 設定を詳しく知りたい                                     │
│   analysis/config_guide.md ──→ 全設定キーの解説         │
│   （セクション3以降）                                    │
├─────────────────────────────────────────────────────────┤
│ 物理式を確認したい                                       │
│   analysis/equations.md ──→ 式の一元管理                │
├─────────────────────────────────────────────────────────┤
│ 実行手順・レシピ                                         │
│   analysis/run-recipes.md ──→ モード別手順              │
├─────────────────────────────────────────────────────────┤
│ アーキテクチャ・内部構造                                 │
│   analysis/overview.md ──→ 開発者向け詳細               │
└─────────────────────────────────────────────────────────┘
```

| ドキュメント | 対象読者 | 内容 |
|-------------|---------|------|
| `README.md` | 全員 | プロジェクト概要・クイックスタート |
| `analysis/config_guide.md` | ユーザー | 設定ファイルの書き方・トラブルシューティング |
| `analysis/equations.md` | 研究者 | 物理式の定義（唯一のソース） |
| `analysis/run-recipes.md` | ユーザー | 実行レシピ・感度解析手順 |
| `analysis/overview.md` | 開発者 | アーキテクチャ・データフロー |
| `analysis/literature_map.md` | 研究者 | 文献索引・先行研究との対応 |

---

## 🚀 クイックスタート

### 1. 環境セットアップ

```bash
# 仮想環境（推奨）
python -m venv .venv && source .venv/bin/activate

# 依存パッケージ
pip install -r requirements.txt
```

### 2. 最初の実行

```bash
# 標準シナリオ（gas-poor、衝突＋blow-out＋昇華）
python -m marsdisk.run --config configs/scenarios/fiducial.yml
```

### 3. 結果確認

```bash
ls out/fiducial/
# series/run.parquet  - 時系列データ
# summary.json        - 集計結果（M_loss など）
# checks/             - 質量保存検証ログ
```

> 💡 **詳細なクイックスタート**: `analysis/config_guide.md` の「🚀 クイックスタート」セクションを参照

---

## 📖 基本的な使い方

> **For AI Agents**: 必ず [`analysis/AI_USAGE.md`](analysis/AI_USAGE.md) を読んでから作業してください。

### 前提とルール

- 解析対象は **gas-poor** の火星ロッシュ内ダスト円盤
- Takeuchi & Lin (2003) は既定で無効（`ALLOW_TL2003=false`）
- CLI ドライバは `python -m marsdisk.run --config <yaml>`
- ⟨Q_pr⟩ テーブルが必須（例: `data/qpr_table.csv`）

---

## 🎛️ シナリオ別コマンド例

| シナリオ | コマンド例 |
| --- | --- |
| ベースライン（昇華OFF） | `python -m marsdisk.run --config configs/base.yml` |
| 昇華 ON | `python -m marsdisk.run --config configs/base_sublimation.yml` |
| 標準シナリオ | `python -m marsdisk.run --config configs/scenarios/fiducial.yml` |
| 高温シナリオ | `python -m marsdisk.run --config configs/scenarios/high_temp.yml` |
| 質量損失スイープベース | `python -m marsdisk.run --config _configs/05_massloss_base.yml` |
| サブリメーション+冷却（Windows向け） | `scripts/run_sublim_cooling_win.cmd` / `scripts/run_sublim_cooling.cmd` ※ストリーミング出力ON（io.streaming.*, merge_at_end=true） |

> 💡 設定の上書き: `--override radiation.TM_K=5000`

---

## 📊 出力チェック

| 出力ファイル | 確認項目 |
|-------------|---------|
| `series/run.parquet` | `M_out_dot`, `mass_lost_by_blowout`, `mass_lost_by_sinks` |
| `summary.json` | `case_status`, `mass_budget_max_error_percent`（≤0.5%） |
| `checks/mass_budget.csv` | 質量収支の検証ログ |

---

## 📖 さらに詳しく

| 目的 | 参照先 |
|------|--------|
| 設定キーの詳細解説 | `analysis/config_guide.md` |
| モード別の詳細手順 | `analysis/run-recipes.md` |
| 数式・物理 | `analysis/equations.md` |
| アーキテクチャ | `analysis/overview.md` |
| 文献索引 | `analysis/literature_map.md` |

---

## 🎛️ 物理パラメータ一覧（概要）

シミュレーションで指定可能な主要物理パラメータの概要です。詳細は `analysis/config_guide.md` を参照してください。

### 放射・温度関連 (`radiation`)

| パラメータ | 説明 | 典型値 |
|-----------|------|--------|
| `radiation.TM_K` | 火星表面温度 [K] | 4000 |
| `radiation.source` | 放射源（`"mars"` / `"off"`） | `"mars"` |
| `radiation.qpr_table_path` | ⟨Q_pr⟩テーブルのパス | `"data/qpr_table.csv"` |

### 時変温度ドライバ (`radiation.mars_temperature_driver`)

| パラメータ | 説明 | 典型値 |
|-----------|------|--------|
| `.enabled` | 時変温度ドライバの有効化 | `true` |
| `.mode` | `"constant"` / `"table"` | `"table"` |
| `.table.path` | 温度テーブルCSVのパス | `"data/mars_temperature_T4000p0K.csv"` |

### 昇華関連 (`sinks`)

| パラメータ | 説明 | 典型値 |
|-----------|------|--------|
| `sinks.mode` | シンク有効化（`"none"` / `"sublimation"`） | `"sublimation"` |
| `sinks.sub_params.mode` | 昇華モデル（`"logistic"` / `"hkl"`） | `"hkl"` |
| `sinks.sub_params.alpha_evap` | 蒸発係数 | 0.007 |
| `sinks.sub_params.mu` | 分子量 [kg/mol] | 0.044 |
| `sinks.sub_params.A` / `.B` | Clausius-Clapeyron係数 | 13.613 / 17850 |

### 円盤ジオメトリ (`disk.geometry`)

| パラメータ | 説明 | 典型値 |
|-----------|------|--------|
| `r_in_RM` | 内縁半径 [Mars半径] | 2.2 |
| `r_out_RM` | 外縁半径 [Mars半径] | 2.7 |

### その他の主要パラメータ

| カテゴリ | パラメータ | 説明 | 典型値 |
|---------|-----------|------|--------|
| 物質 | `material.rho` | バルク密度 [kg/m³] | 3000 |
| サイズ | `sizes.s_min` / `s_max` | 粒径範囲 [m] | 1e-6 / 3.0 |
| サイズ | `sizes.n_bins` | 対数ビン数 | 40 |
| PSD | `psd.alpha` | べき指数 | 1.83 |
| 力学 | `dynamics.e0` / `i0` | 離心率・傾斜角 | 0.5 / 0.05 |
| 数値 | `numerics.t_end_years` | シミュレーション期間 [yr] | 2.0 |

> 📖 **完全なパラメータ一覧**: [`analysis/config_guide.md`](analysis/config_guide.md) のセクション3以降を参照

---

---

## 🔬 物理モデルの詳細

本シミュレーションは、火星ロッシュ限界内（~2.4 火星半径）の高温ダスト円盤を対象に、**3つの主要物理過程**をカップリングして時間発展を追跡します。

### 計算フローの全体像

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    各タイムステップの計算順序                          │
├─────────────────────────────────────────────────────────────────────┤
│  ① 温度評価 → ② 放射圧パラメータ → ③ 昇華フラックス                    │
│       ↓              ↓                    ↓                         │
│     T_M(t)      ⟨Q_pr⟩, β, a_blow        J(T)                       │
│                      ↓                    ↓                         │
│              ④ 光学深度 & 自遮蔽     ⑤ シンク時間                     │
│                   τ, Φ(τ)              t_sink                       │
│                      ↓                    ↓                         │
│              ⑥ 表層質量フラックス評価                                  │
│                 Σ_surf, Ṁ_out, Φ_sink                               │
│                      ↓                                              │
│              ⑦ IMEX-BDF(1) 時間積分                                  │
│                      ↓                                              │
│              ⑧ 質量収支検査 & 診断記録                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

### 1. 放射圧ブローアウト（Radiation Pressure Blow-out）

火星からの赤外放射が小粒子に作用し、放射圧が重力を上回ると粒子は円盤外へ吹き飛ばされます。

#### 背景と仮定
巨大衝突直後の火星表面は数千ケルビンまで加熱され、ロッシュ限界付近の粒子は火星表面温度 T_M≃2000 K の黒体放射から ~1.6×10^5 W m⁻²（火星軌道の太陽光束の数百倍）に相当する赤外フラックスを受けると見積もられます。このとき、サブミクロン〜ミクロンサイズの粒子では、放射圧と重力の比 β が 0.5 を超え、軌道に束縛されない軌道に遷移します。

本コードでは、火星を黒体とみなして表面温度 radiation.TM_K から放射束を計算し、粒径と Planck 平均放射圧効率から β を評価します。β > 0.5 をブローアウト条件とし、この条件を満たす粒子が表層に供給された分だけ、表層外向きフラックス Ṁ_out として質量を円盤系から取り除きます。

本モデルでは粒子温度と放射圧を火星からの赤外放射のみで評価し、太陽放射や粒子間の相互放射は無視しています。

#### 概念

- 火星表面温度 T_M からの黒体放射が粒子を加熱
- 粒子サイズが小さいほど軽さ指標 β（放射圧/重力比）が大きくなる
- 脱出条件

  $$\large
  \beta > 0.5
  $$

#### 代表式

**放射圧/重力比 β** (E.013):

$$\large
\beta = \frac{3\,\sigma_{\rm SB}\,T_{\rm M}^{4}\,R_{\rm M}^{2}\,\langle Q_{\rm pr}\rangle}{4\,G\,M_{\rm M}\,c\,\rho\,s}
$$

**ブローアウト境界サイズ a_blow** (E.014, β = 0.5 となるサイズ):

$$\large
a_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_{\rm M}^{4}\,R_{\rm M}^{2}\,\langle Q_{\rm pr}\rangle}{2\,G\,M_{\rm M}\,c\,\rho}
$$

**表層外向きフラックス** (E.009):

$$\large
\dot{M}_{\rm out} = \Sigma_{\rm surf}\,\Omega
$$

| 記号 | 意味 | 単位 | 典型値 |
|------|------|------|--------|
| σ_SB | Stefan-Boltzmann 定数 | W m⁻² K⁻⁴ | 5.67e-8 |
| T_M | 火星表面温度 | K | 2000–6000 |
| R_M | 火星半径 | m | 3.39e6 |
| ⟨Q_pr⟩ | Planck平均放射圧効率 | — | 0.5–1.5 |
| ρ | 粒子密度 | kg m⁻³ | 3000 |
| s | 粒子半径 | m | 1e-6–3 |
| Ω | ケプラー角速度 | rad s⁻¹ | 下記参照 |

ケプラー角速度の定義:

$$\large
\Omega = \sqrt{\frac{G\,M_{\rm M}}{r^{3}}}
$$

#### 重要なパラメータ

- `radiation.TM_K`: 火星表面温度（高いほど a_blow が大きくなる）
- `blowout.enabled`: ブローアウト損失の有効/無効
- `blowout.chi_blow`: ブローアウト滞在時間係数

  $$\large
  t_{\rm blow} = \frac{\chi}{\Omega}
  $$

---

### 2. 昇華（Sublimation）

高温環境では粒子表面からの蒸発が進み、質量損失の原因となります。

#### 背景と仮定
巨大衝突後の円盤は、高温の溶融物とそれに由来する蒸気が共存する状態から冷却していくと考えられます。このとき、ガス相から直接凝縮した微小ダストは、溶融物から固化した粗い粒子よりも典型サイズが小さく、表面積が大きいため、昇華と再凝縮のサイクルに最も敏感な成分になります。

本コードでは、昇華フラックスの形を粒子表面からの分子の飛び出し速度を表す式（Hertz–Knudsen–Langmuir, HKL 式）で与え、主成分として SiO を仮定して飽和蒸気圧 P_sat(T) を評価します。飽和蒸気圧は、Clausius–Clapeyron 型の近似式か、外部から与えたテーブルデータから取得できます。周囲蒸気圧 P_gas は局所ガス分圧を表す自由パラメータとし、既定値は gas-poor 条件を表す P_gas = 0 です。

Hyodo et al. (2017, 2018) が報告する蒸気分率≲数 % の gas-poor 円盤を first-order 近似するため、既定では P_gas=0 を採用しています。

昇華による侵食の強さは、「基準時間 t_ref のあいだに完全に失われる粒径」 s_sink で測り、その粒径から逆算したシンク時間 t_sink を表層の追加損失項として使います。これにより、昇華が衝突やブローアウトと同じ枠組みで質量収支に入ります。

#### 昇華の概念

- 粒子温度が蒸発温度を超えると表面から物質が蒸発
- Hertz–Knudsen–Langmuir (HKL) 式で質量フラックスを評価
- 主成分 SiO の蒸気圧で支配（gas-poor 条件では P_gas ≈ 0）

#### 昇華の代表式

**HKL 質量フラックス** (E.018):

$$\large
J(T) = \alpha_{\rm evap}\left(P_{\rm sat}(T) - P_{\rm gas}\right)\sqrt{\frac{\mu}{2\pi R T}}
$$

**Clausius-Clapeyron 型蒸気圧** (E.036):

$$\large
P_{\rm sat}(T) = 10^{A - B/T}
$$

**昇華による損失粒径スケール** (E.019):

$$\large
s_{\rm sink} = \frac{\eta_{\rm instant}\,t_{\rm ref}\,J(T)}{\rho}
$$

| 記号 | 意味 | 単位 | 典型値 |
|------|------|------|--------|
| alpha_evap | 蒸発係数 | — | 0.007 |
| P_sat | 飽和蒸気圧 | Pa | 温度依存 |
| P_gas | 周囲蒸気圧 | Pa | 0（gas-poor） |
| mu | 分子量 | kg mol⁻¹ | 0.044 (SiO) |
| R | 気体定数 | J mol⁻¹ K⁻¹ | 8.314 |
| A, B | Clausius係数 | —, K | 13.613, 17850 |
| eta_instant | 即時蒸発閾値 | — | 0.1 |

#### 昇華の重要なパラメータ

- `sinks.mode`: `"sublimation"` で昇華を有効化
- `sinks.sub_params.mode`: `"hkl"`（物理的）or `"logistic"`（簡易）
- `sinks.sub_params.psat_model`: `"clausius"` or `"tabulated"`

---

### 3. 衝突カスケード（Collision Cascade）

粒子同士の衝突により破砕が進み、大きな粒子から小さな粒子が生成されます。

#### 背景と仮定
巨大衝突後の円盤では、初期の粒子は高い離心率を持つ軌道で周回し、火星の扁平性による歳差運動により軌道面がランダム化されたのち、1–5 km/s 程度の高速度衝突を繰り返すと見積もられています。その結果、メートルスケールの塊が 100 µm スケールの粒子へと破砕され、その後は通常のデブリ円盤と同様の衝突カスケードが支配的になります。

本コードでは、粒径分布の時間発展を表す方程式（Smoluchowski 方程式）をサイズビンごとに解き、衝突カーネル K_ij に粒径、相対速度、円盤の鉛直スケール高を用います。表層の有効衝突寿命は、デブリ円盤の解析モデルで広く用いられている近似 t_{\rm coll} = 1 / (\Omega \tau_{\perp}) に従って定義し、Wyatt 型の衝突寿命スケーリングと整合するようになっています。衝突で生じた破片のうち、サイズが a_blow 未満の粒子は、直ちに放射圧ブローアウトの表層フラックスに供給されます。

#### 衝突の概念

- 大粒子同士の衝突で破片が生成される（Smoluchowski 方程式）
- 衝突により生成された小粒子がブローアウトサイズ以下なら即座に失われる

#### 衝突の代表式

**Smoluchowski 方程式** (E.010):

$$\large
\dot{N}_k = \frac{1}{2}\sum_{i,j} K_{ij}\,N_i N_j\,Y_{kij} - N_k\sum_j K_{kj}N_j + f_k
$$

**衝突カーネル** (E.024):

$$\large
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,\frac{\pi(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}}
$$

**衝突寿命（Wyatt スケーリング）** (E.006):

$$\large
t_{\rm coll} = \frac{1}{\Omega\,\tau_{\perp}}
$$

**IMEX-BDF(1) 時間積分** (E.010):

$$\large
N_i^{n+1} = \frac{N_i^{n} + \Delta t(G_i - S_i)}{1 + \Delta t\,\Lambda_i}
$$

| 記号 | 意味 | 単位 |
|------|------|------|
| N_k | ビン k の数密度 | m⁻² |
| K_ij | 衝突カーネル | s⁻¹ |
| Y_kij | 破片分配係数 | — |
| f_k | ソース/シンク項 | m⁻² s⁻¹ |
| v_ij | 相対速度 | m s⁻¹ |
| H_ij | 鉛直スケール高 | m |
| tau_perp | 鉛直光学深度 | — |

> **K_ij と C_ij の使い分け**  
> (E.010) の $K_{ij}$ は文献表記どおり「幾何＋速度」だけの係数を指しますが、実装の (E.024) `compute_collision_kernel_C1` は $N_i N_j/(1+\delta_{ij})$ まで掛け込んだ $C_{ij}$ 行列を返します（`marsdisk/physics/collide.py:18-77`）。Smol ステップではこの $C_{ij}$ をそのまま損失・生成項に使い、数密度を重ねて乗じる操作は行いません（`marsdisk/physics/smol.py:244-275`）。

#### 衝突の重要なパラメータ

- `sizes.n_bins`: 粒径ビン数（30–60、デフォルト40）
- `psd.alpha`: 破片分布のべき指数
- `dynamics.e0`, `dynamics.i0`: 離心率・傾斜角（相対速度に影響）

---

### 物理過程の相互作用

3つの過程は密接に結合しています：

```text
     ┌──────────────────────────────────────────────────────────┐
     │                    衝突カスケード                         │
     │   大粒子 → 破砕 → 小粒子生成（prod_subblow_area_rate）     │
     └────────────────────────┬─────────────────────────────────┘
                              │
                              ▼
     ┌──────────────────────────────────────────────────────────┐
     │              表層への小粒子供給                            │
     │        s < a_blow の粒子が表層に蓄積                       │
     └──────┬─────────────────────────────┬─────────────────────┘
            │                             │
            ▼                             ▼
┌───────────────────────┐     ┌───────────────────────────────┐
│   放射圧ブローアウト    │     │          昇華                   │
│   β > 0.5 で吹き飛び   │     │   高温で蒸発 (HKL フラックス)    │
│   Ṁ_out = Σ_surf × Ω  │     │   Φ_sink = Σ_surf / t_sink     │
└───────────────────────┘     └───────────────────────────────┘
            │                             │
            └──────────────┬──────────────┘
                           ▼
              ┌────────────────────────┐
              │     総質量損失率        │
              │  M_loss = M_out + M_sink│
              └────────────────────────┘
```

ここで M_loss は表層面密度基準の総質量損失率で、単位は kg m⁻² s⁻¹ です。

### 自遮蔽効果（Self-Shielding）

光学的に厚い円盤では、表層のみが放射を受けます：

**有効不透明度** (E.015):

$$\large
\kappa_{\rm eff} = \Phi(\tau)\,\kappa_{\rm surf}
$$

**τ=1 表層質量** (E.016):

$$\large
\Sigma_{\tau=1} = \kappa_{\rm eff}^{-1}
$$

- Φ(τ): 自遮蔽係数（テーブル補間）
- 表層密度のクリップ条件

  $$\large
  \Sigma_{\rm surf,clip} = \min(\Sigma_{\rm surf}, \Sigma_{\tau=1})
  $$

---

### 質量収支の検証

シミュレーションは質量保存を常時監視します (E.011):

$$\large
\epsilon_{\rm mass} = \frac{|M^{n+1} + \Delta t\,\dot{m}_{<a_{\rm blow}} - M^{n}|}{M^{n}} < 0.5\%
$$

出力ファイル `checks/mass_budget.csv` に各ステップの誤差を記録。

---

### 出力される主要な物理量

| カラム名 | 意味 | 単位 |
|----------|------|------|
| `a_blow` | ブローアウト境界サイズ | m |
| `beta_at_smin` | 最小粒径での β | — |
| `prod_subblow_area_rate` | サブブローアウト生成率 | kg m⁻² s⁻¹ |
| `M_out_dot` | 表層外向きフラックス | kg m⁻² s⁻¹ |
| `mass_lost_by_blowout` | ブローアウト累積損失 | kg |
| `mass_lost_by_sinks` | 昇華累積損失 | kg |
| `tau_eff` | 有効光学深度 | — |
| `kappa_Planck` | Planck平均不透明度 | m² kg⁻¹ |

> 📐 **詳細な式定義**: [`analysis/equations.md`](analysis/equations.md)  
> 🔄 **計算フロー図**: [`analysis/physics_flow.md`](analysis/physics_flow.md)  
> 📚 **文献との対応**: [`analysis/literature_map.md`](analysis/literature_map.md)
>

### 先行研究との対応
- 円盤の初期温度 ~2000 K、蒸気分率≲数 %、メートル級ドロップレットが 1–5 km/s の衝突で再溶融し、∼100 µm 級の液滴へ細分化される、という描像は Hyodo et al. (2017 I) の SPH 計算と衝突後進化に基づいています。:contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}  
- 気相からの凝縮で ~0.1 µm スケールの微小ダストが自然に生じること、溶融物から固化した粒子は 0.1–1 mm 程度の粗い粒子になることは Ronnet et al. (2016) の凝縮モデルから取っています。:contentReference[oaicite:3]{index=3}  
- T≈2000 K, P≈10⁻⁴ bar 程度の条件で溶融物と蒸気が共存する円盤を想定し、そこからの化学組成・揮発性の扱いを決める、という考え方は Pignatale et al. (2018) に揃えています。:contentReference[oaicite:5]{index=5}  
- 放射圧の β の定義と β>0.5 を境界にしたブローアウト条件は、Burns et al. (1979) および Strubbe & Chiang (2006) に従っており、AU Mic デブリ円盤の「衝突カスケード + 表層外流」モデルと同じスケーリングを採用しています。:contentReference[oaicite:6]{index=6}:contentReference[oaicite:7]{index=7}  
- 衝突寿命 `t_{\rm coll} = 1/(\Omega\tau_\perp)` の形は、Wyatt (2008) のデブリ円盤レビューで使われている標準的なスケーリングをそのまま取り入れ、Smoluchowski 解との整合確認用にも使っています。:contentReference[oaicite:9]{index=9}  
- gas-poor 円盤を標準とすること、および初期質量の上限を抑えることは、Hyodo et al. (2017, 2018) の蒸気分率・放射圧評価と、Canup & Salmon (2018) や Kuramoto (2024) の起源レビューに整合するように選んでいます。:contentReference[oaicite:11]{index=11}:contentReference[oaicite:12]{index=12}  

---

## 📐 式番号と物理過程の対応

各物理過程がどの式で表現されているかを整理します。式番号は `analysis/equations.md` の定義に対応しています。

---

### 1. 火星からの放射圧によるブローアウト

「火星の放射圧が重力を打ち消して、小さい粒が軌道から吹き飛ばされる」という物理を直接表しているのは、β とブローアウト径の式です。

#### ブローアウトの中心式

##### β の定義 (E.013)

火星の放射圧と重力の比を与える式で、放射圧ブローアウトの基礎になっています：

$$\large
\beta = \frac{3\,\sigma_{\rm SB}\,T_{\rm M}^{4}\,R_{\rm M}^{2}\,\langle Q_{\rm pr}\rangle}{4\,G\,M_{\rm M}\,c\,\rho\,s}
$$

##### ブローアウト径 s_blow (E.014)

β = 0.5 の閾値を代入した閉じた式で、火星から吹き飛ぶ粒径の境界を与えます：

$$\large
s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_{\rm M}^{4}\,R_{\rm M}^{2}\,\langle Q_{\rm pr}\rangle}{2\,G\,M_{\rm M}\,c\,\rho}
$$

##### 有効最小粒径 s_min,eff (E.008)

粒径分布の下限を「設定した下限」と「ブローアウト径」の大きい方で決める定義です。ブローアウト境界を、そのまま PSD（粒径分布）の実効下限に反映させる役割です：

$$\large
s_{\rm min,eff} = \max\left(s_{\rm min,cfg},\, s_{\rm blow}\right)
$$

#### ブローアウトを支える補助的な式

| 式番号 | 内容 | 役割 |
|--------|------|------|
| **(E.012)** | Planck 平均の放射圧効率 ⟨Q_pr⟩ | Q_pr の表または指定値から ⟨Q_pr⟩ を決めるロジックで、β と s_blow に直接入る |
| **(E.005) / (E.039)** | Q_pr テーブルのローダ | 外部テーブルを読み込んで ⟨Q_pr⟩(s, T_M) を補間するヘルパ。β・s_blow の入力を与える層 |
| **(E.009)** | 表層アウトフロー Ṁ_out = Σ_surf Ω | 吹き飛びで作られる「光学的に薄い流れ」のスケールを評価する近似。ブローアウトで失われる質量流束を表す |
| **(E.035)** | サブブローアウト生成率 ṁ_{<a_blow} | 衝突カーネル C_ij から「ブローアウト領域に落ちる質量」を積算する式。衝突カスケードからブローアウト流へつながるソースを定義 |
| **(E.006) / (E.007)** | 表層 ODE 内の t_blow = 1/Ω | legacy の表層 ODE（S1）で吹き飛びの寿命を定義。Smol 解法が標準なので「補助的な（検算用）ブローアウト表現」という位置付け |

---

### 2. Smoluchowski 衝突カスケード

「粒径 PSD の時間発展を衝突で決める」部分が、Smoluchowski 方程式とそのカーネルです。

#### 衝突カスケードの中心式

##### Smoluchowski 方程式（IMEX-BDF1）(E.010)

粒径ビン k の数面密度 N_k の時間発展を記述し、IMEX-BDF1 で解く標準の衝突解法です。K_ij が衝突カーネル、Y_kij が破片分配、f_k に供給・昇華・追加シンクがまとめられます：

$$\large
\dot{N}_k = \frac{1}{2}\sum_{i,j} K_{ij}\,N_i N_j\,Y_{kij} - N_k\sum_j K_{kj}N_j + f_k
$$

##### 衝突カーネル C_ij（nσv 型）(E.024)

Smol の内部で使う nσv 型カーネルを定義し、サイズビンどうしの衝突頻度を与えます：

$$\large
C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\,\frac{\pi(s_i+s_j)^{2}\,v_{ij}}{\sqrt{2\pi}\,H_{ij}}
$$

#### 衝突カスケードを支える周辺の式

| 式番号 | 内容 | 役割 |
|--------|------|------|
| **(E.020), (E.021), (E.022)** | 力学セット (v_ij, c, e) | 平均相対速度 v_ij = v_K√(1.25e² + i²)、速度分散 c の固定点解、離心率 e の指数減衰を与え、衝突カーネルの入力 v_ij, H_ij を決める。「どのくらい激しくぶつかるか」を決める力学ブロック |
| **(E.032), (E.033), (E.026)** | 破壊スケーリング | 比衝突エネルギー Q_R の定義（E.032）、最大残留分率 f_LR の分岐式（E.033）、破壊閾値 Q_D*(s, ρ, v) の式（E.026）で、衝突一回ごとに「どれだけ細かい破片になるか」を決める |
| **(E.011)** | 質量収支診断 | IMEX 更新前後の総質量差を測る質量収支チェック。衝突カスケードの数値安定性を監視するための式（物理そのものというより診断） |
| **(E.035)** | サブブローアウト生成率 | 衝突カスケードから「ブローアウト領域に入る質量流束」を抜き出す式。衝突カスケード側・ブローアウト側の両方にまたがる役割 |
| **(E.006), (E.007)** | 表層 ODE（Wyatt 型近似） | Type-A/B ディスクの表層衝突時間 t_coll = 1/(Ωτ_⊥) と、それを使って表層面密度 Σ を直接減衰させる ODE。Smol のフル解法に対する「光学的に薄い簡略版（legacy）」 |

---

### 3. 昇華（サブリメーション）

「高温で固体が気化して質量を失う」部分は、HKL フラックスとその寿命換算で表現されています。

#### 昇華の中心式

##### 昇華フラックス J(T)（HKL）(E.018)

温度 T での質量フラックスを定義し、昇華による質量損失の根幹です：

$$\large
J(T) = \alpha_{\rm evap}\left(P_{\rm sat}(T) - P_{\rm gas}\right)\sqrt{\frac{\mu}{2\pi R T}}
$$

（HKL モードでない場合はロジスティック近似 exp((T - T_sub)/max(dT, 1)) にフォールバック）

##### シンク粒径 s_sink (E.019), (E.038)

J(T) を「参照時間スケール内に消えてしまう粒径」に換算する式で、昇華によって「即時に失われるサイズ境界」を決めます：

$$\large
s_{\rm sink} = \frac{\eta_{\rm instant}\,t_{\rm ref}\,J(T)}{\rho}
$$

#### 昇華を支える周辺の式

| 式番号 | 内容 | 役割 |
|--------|------|------|
| **(E.036), (E.037)** | 飽和蒸気圧 P_sat(T) | HKL フラックスの中で使う飽和蒸気圧を Clausius 型 P_sat = 10^(A - B/T) またはタブレット補間として与える |
| **(E.042)** | 火星温度の時間発展 T_Mars(t) | 火星の放射冷却の解析解 T_Mars(t) = (T₀⁻³ + 3σt/(Dρc_p))^(-1/3) を与える式。昇華フラックス J(T) に入る温度、および β・s_blow に入る T_M の時間変化を決める。昇華・ブローアウト両方の温度ドライバ |
| **(E.043)** | 粒子温度 T_p(r, t) | 粒子の放射平衡温度を決める式で、J(T) の T に直接入る。昇華レートを r・t によって変化させる役割 |
| **s_sub_boundary** | 昇華境界（式番号なし） | s_sink を使って粒径進化フック（ds/dt）の中で「昇華によるカットオフ境界」として扱うヘルパ。PSD の下限ではなく「粒径進化フック専用」 |

---

### 4. 式と物理過程の対応まとめ

| 物理過程 | 中心の式 | 補助・周辺の式 |
|----------|---------|----------------|
| **火星放射圧ブローアウト** | (E.013) β, (E.014) s_blow, (E.008) s_min,eff | (E.012) ⟨Q_pr⟩, (E.005)/(E.039) Q_pr ローダ, (E.009) Ṁ_out, (E.035) サブブローアウト生成, (E.006)/(E.007) 表層ODE |
| **Smol 衝突カスケード** | (E.010) Smoluchowski 方程式, (E.024) 衝突カーネル | (E.020)–(E.022) 力学セット, (E.032)/(E.033)/(E.026) 破壊スケーリング, (E.011) 質量診断, (E.006)/(E.007) 表層ODE |
| **昇華** | (E.018) HKL フラックス, (E.019)/(E.038) s_sink | (E.036)/(E.037) P_sat, (E.042)/(E.043) 温度ドライバ, s_sub_boundary |

> **注**: 遮蔽（E.015–E.017）や初期条件・供給モデル（E.023, E.025, E.027 など）は上記の 3 カテゴリには含めていません。

---

## 📜 参考文献

- Hyodo et al. (2017, 2018): gas-poor 仮定の根拠
- Canup & Salmon (2018): 衛星形成シナリオ
- Leinhardt & Stewart (2012): 破砕強度モデル
- Strubbe & Chiang (2006): 放射圧支配の描像
- Burns et al. (1979): 放射圧 β の定義
- Wyatt (2008): 衝突寿命スケーリング
- Krivov et al. (2006): Smoluchowski 方程式の実装
- Pignatale et al. (2018): HKL 昇華モデル
