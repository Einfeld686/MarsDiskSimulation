# marsshearingsheet 取扱説明書

**バージョン情報**

* 対象ブランチ：`main`（ユーザー指定）
* コミット：`9b8bd2e1e622d1e458e7715af55021d1877e5eec / 2025-10-02T20:45:42+09:00`
* 探索範囲：既定ブランチのみ（タグ／Release／LFS／Wiki／Issues 添付は本書では扱わない）

---

## 1. 概要（アップグレード版）

本セクションでは、本コードがどの物理プロセスをどの方程式で記述し、どのモジュールがそれらを実装しているかをまとめる。中心となるのは、火星ロッシュ限界内の薄いダスト円盤で生じる「内部破砕 → sub-blow-out 粒子生成 → 表層供給 → 放射圧剥離」という質量パイプラインであり、全体は `marsdisk.run.run_zero_d` が 0D モデルとして統括する。([marsdisk/run.py:193])

### 1.1 主要方程式と役割
- **ケプラー動力学**：角速度と公転速度からダイナミカルタイムと吹き飛び時間を定義する。[marsdisk/grid.py:19]
  ```math
  \Omega(r)=\sqrt{\frac{G M_{\rm M}}{r^{3}}},\qquad
  v_K=\sqrt{\frac{G M_{\rm M}}{r}},\qquad
  t_{\rm blow}=\frac{1}{\Omega}
  ```
- **放射圧対重力比**：放射圧が重力に対して担う比率からブローアウト粒径を決める。[marsdisk/physics/radiation.py:221]
  ```math
  \beta = \frac{3\,\sigmaa_{\rm SB}\,T_{\rm M}^{4}\,R_{\rm M}^{2}\,\langle Q_{\rm pr}\rangle}{4 G M_{\rm M} c \rho s},\qquad
  s_{\rm blow} = \frac{3\,\sigma_{\rm SB}\,T_{\rm M}^{4}\,R_{\rm M}^{2}\,\langle Q_{\rm pr}\rangle}{2 G M_{\rm M} c \rho}
  ```
- **粒径分布と不透明度**：三勾配 PSD と “wavy” 補正から光学深度を評価する。[marsdisk/physics/psd.py:119]
  ```math
  n(s)\propto\left(\frac{s}{s_{\min}}\right)^{-q},\qquad
  \kappa = \frac{\int \pi s^{2} n(s)\,\mathrm{d}s}{\int \tfrac{4}{3} \pi \rho s^{3} n(s)\,\mathrm{d}s},\qquad
  \tau = \kappa \Sigma_{\rm surf}
  ```
- **自己遮蔽**：多重散乱補正を適用し、光学深度 1 を超える表層面密度をクリップする。[marsdisk/physics/shielding.py:81]
  ```math
  \kappa_{\rm eff} = \Phi(\tau,\omega_0,g)\,\kappa,\qquad
  \Sigma_{\tau=1}=\frac{1}{\kappa_{\rm eff}}
  ```
- **表層 ODE**：放射圧剥離・Wyatt 衝突寿命・追加シンクを同時に扱う。外向面フラックスは表層面密度と角速度から得る。[marsdisk/physics/surface.py:138]
  ```math
  \frac{\mathrm{d}\Sigma_{\rm surf}}{\mathrm{d}t} = P - \frac{\Sigma_{\rm surf}}{t_{\rm blow}} - \frac{\Sigma_{\rm surf}}{t_{\rm coll}} - \frac{\Sigma_{\rm surf}}{t_{\rm sink}},\qquad
  t_{\rm coll}=\frac{1}{2\,\Omega\,\tau},\qquad
  \Sigma_{\rm out}=\Sigma_{\rm surf}\,\Omega
  ```
- **衝突破砕**：相対速度・衝突カーネル・破砕エネルギーから sub-blow-out 粒子生成率を得る。[marsdisk/physics/collide.py:18]
  ```math
  v_{ij}=v_K \sqrt{1.25 e^{2} + i^{2}},\qquad
  Q_R=\frac{0.5\,\mu v^{2}}{m_{1}+m_{2}},\qquad
  \frac{M_{\rm LR}}{M_{\rm tot}}=0.5\left(2-\frac{Q_R}{Q_{\rm RD}^*}\right)
  ```
- **Smoluchowski IMEX-BDF(1)**：内部 PSD の数密発展を解き、質量保存を監視する。[marsdisk/physics/smol.py:18]
  ```math
  N^{n+1}=\frac{N^{n}+\Delta t\,(\mathrm{gain}-S)}{1+\Delta t\,\mathrm{loss}},\qquad
  \varepsilon_{\rm mass}=\frac{\lvert M^{n+1}+\Delta t\,\dot{M}_{\rm prod}-M^{n}\rvert}{M^{n}}
  ```
- **昇華・ガス抗力**：昇華・ガス抗力からシンク時間を決める。[marsdisk/physics/sublimation.py:85]
  ```math
  J=\alpha (P_{\rm sat}-P_{\rm gas})\sqrt{\frac{\mu}{2\pi R T}},\qquad
  s_{\rm sink}=\frac{\eta t_{\rm ref} J}{\rho},\qquad
  t_{\rm drag}=\frac{\rho_p s}{\rho_g c_s}
  ```
- **供給と出力換算**：外部供給律をテーブルまたは解析式で与え、外向質量流束と累積損失を更新する。[marsdisk/physics/supply.py:69][marsdisk/run.py:352]
  ```math
  P(t)=A\bigl((t-t_0)+\varepsilon\bigr)^{\text{index}},\qquad
  \dot{M}_{\rm out} = \frac{\Sigma_{\rm surf} \Omega \cdot A_{\rm disk}}{M_{\rm M}},\qquad
  M_{\rm loss}^{\rm cum}(t+\Delta t)=M_{\rm loss}^{\rm cum}(t)+\dot{M}_{\rm out}\,\Delta t
  ```

#### 1.1.A 放射・光学
- 放射圧とブローアウト境界の判定。[marsdisk/physics/radiation.py:229]
  ```math
  \beta = \frac{3\,\sigma_{\rm SB} T_{\rm M}^{4} R_{\rm M}^{2} \langle Q_{\rm pr}\rangle}{4 G M_{\rm M} c \rho s},\qquad
  s_{\rm blow} = \frac{3\,\sigma_{\rm SB} T_{\rm M}^{4} R_{\rm M}^{2} \langle Q_{\rm pr}\rangle}{2 G M_{\rm M} c \rho}
  ```
- 三勾配 PSD と “wavy” 補正の形。[marsdisk/physics/psd.py:80]
  ```math
  n(s) \propto \left(\frac{s}{s_{\min}}\right)^{-q}\Bigl[1 + A_{\rm w} \sin\Bigl(\frac{2\pi \ln(s/s_{\min})}{\ln(s_{\max}/s_{\min})}\Bigr)\Bigr]
  ```
- 光学的不透明度と自己遮蔽クリップの評価。[marsdisk/physics/psd.py:119][marsdisk/physics/shielding.py:123]
  ```math
  \kappa = \frac{\int \pi s^{2} n(s)\,\mathrm{d}s}{\int \tfrac{4}{3}\pi \rho s^{3} n(s)\,\mathrm{d}s},\qquad
  \kappa_{\rm eff} = \Phi(\tau,\omega_0,g)\,\kappa,\qquad
  \Sigma_{\tau=1} = \frac{1}{\kappa_{\rm eff}}
  ```

#### 1.1.B 表層とアウトフロー
- 表層 ODE と関連タイムスケール。[marsdisk/physics/surface.py:13]
  ```math
  \frac{\mathrm{d}\Sigma_{\rm surf}}{\mathrm{d}t} = P - \frac{\Sigma_{\rm surf}}{t_{\rm blow}} - \frac{\Sigma_{\rm surf}}{t_{\rm coll}} - \frac{\Sigma_{\rm surf}}{t_{\rm sink}},
  \qquad t_{\rm blow} = \frac{1}{\Omega(r)},\qquad t_{\rm coll} = \frac{1}{2\,\Omega\,\tau}
  ```
- 表層フラックスと総質量流束の換算。[marsdisk/physics/surface.py:151][marsdisk/run.py:352]
  ```math
  \Sigma_{\rm out} = \Sigma_{\rm surf} \Omega,\qquad
  \dot{M}_{\rm out} = \frac{\Sigma_{\rm surf} \Omega \cdot A_{\rm disk}}{M_{\rm Mars}}
  ```

#### 1.1.C 衝突破砕と PSD 進化
- 双対衝突カーネルと粒子数密の更新。[marsdisk/physics/collide.py:69][marsdisk/physics/smol.py:87]
  ```math
  C_{ij} = \frac{N_i N_j}{1+\delta_{ij}}\frac{\pi (s_i + s_j)^2 v_{ij}}{\sqrt{2\pi} H_{ij}},\qquad
  N^{n+1} = \frac{N^n + \Delta t (\mathrm{gain} - S)}{1 + \Delta t \cdot \mathrm{loss}}
  ```
- ゲイン項と質量監査指標。[marsdisk/physics/smol.py:84][marsdisk/physics/smol.py:118]
  ```math
  \mathrm{gain}_k = \tfrac{1}{2} \sum_{ij} C_{ij} Y_{kij},\qquad
  \varepsilon_{\rm mass} = \frac{\lvert M^{n+1} + \Delta t \dot{M}_{\rm prod} - M^n\rvert}{M^n}
  ```
- 衝突エネルギーと最大残骸の質量分率。[marsdisk/physics/fragments.py:32][marsdisk/physics/fragments.py:68]
  ```math
  Q_R = \frac{0.5\,\mu v^2}{m_1+m_2},\qquad
  \frac{M_{\rm LR}}{M_{\rm tot}} = 0.5\left(2 - \frac{Q_R}{Q_{\rm RD}^*}\right)
  ```

#### 1.1.D 動力学と励起
- ケプラー角速度と公転速度。[marsdisk/grid.py:30]
  ```math
  \Omega(r) = \sqrt{\frac{G M_{\rm Mars}}{r^3}},\qquad
  v_K(r) = \sqrt{\frac{G M_{\rm Mars}}{r}}
  ```
- 相対速度と乱流速度分散の推定。[marsdisk/physics/dynamics.py:18][marsdisk/physics/dynamics.py:96]
  ```math
  v_{ij} = v_K \sqrt{1.25 e^2 + i^2},\qquad
  c_{\rm eq} = \sqrt{\frac{f_{\rm wake} \tau}{1 - \varepsilon^2}}
  ```
- 離心率の指数緩和。[marsdisk/physics/dynamics.py:128]
  ```math
  e_{n+1} = e_{\rm eq} + (e_n - e_{\rm eq}) \exp\left(-\frac{\Delta t}{t_{\rm damp}}\right)
  ```

#### 1.1.E 昇華とガスシンク
- 飽和蒸気圧と質量フラックスの計算。[marsdisk/physics/sublimation.py:69]
  ```math
  \log_{10}\left(\frac{P_{\rm sat}}{\rm Pa}\right) = A - \frac{B}{T},\qquad
  J = \alpha (P_{\rm sat} - P_{\rm gas}) \sqrt{ \frac{ \mu }{ 2\pi R T } }
  ```
- 粒径シンクとガス抗力時間。[marsdisk/physics/sublimation.py:116][marsdisk/physics/sinks.py:46]
  ```math
  s_{\rm sink} = \frac{\eta t_{\rm ref} J}{\rho},\qquad
  t_{\rm drag} \approx \frac{\rho_p s}{\rho_g c_s},\qquad
  t_{\rm sink} = \min(t_{\rm sub}, t_{\rm drag}, \ldots)
  ```

#### 1.1.F 初期条件と供給
- パワー則面密度と特別解。[marsdisk/physics/initfields.py:33]
  ```math
  \Sigma(r) = C r^{-p},\qquad
  C = \frac{M_{\rm in} (2 - p)}{2\pi (r_{\rm out}^{2-p} - r_{\rm in}^{2-p})},\qquad
  \Sigma = \frac{M_{\rm in}}{\pi (r_{\rm out}^{2} - r_{\rm in}^{2})}\ \text{(for }p\approx 0\text{)}
  ```
- 表層初期化と供給律。[marsdisk/physics/initfields.py:75][marsdisk/physics/supply.py:73]
  ```math
  \Sigma_{\rm surf,0} = \min(f_{\rm surf} \Sigma, 1/\kappa_{\rm eff}),\qquad
  P(t) = A \bigl((t - t_0)+\varepsilon\bigr)^{\text{index}},\qquad
  P(t,r) = \sum_{ij} w_{ij} f_{ij}(t,r)
  ```

### 1.2 実装モジュール
これらの方程式は以下のモジュールで連鎖している。
- `marsdisk.run`: 設定読込・PSD 初期化・遮蔽適用・表層 ODE 解・質量収支出力。
- `marsdisk/physics/radiation|psd|shielding|surface|collide|smol|fragments|sinks|dynamics`: 各式の実装。
- `marsdisk/io.writer|tables`: Q_pr/Phi テーブル補間と出力書き出し。

### 1.3 モデル範囲
自己重力ポアソン解、Toomre Q、角運動量輸送解析などは未実装であり、0D 表層モデルと内部破砕–放射圧連成に焦点を絞っている。追加プロセスを利用する場合は拡張実装が必要である。

**章末出典（リポジトリ一次情報）**：[`marsdisk/run.py`], [`marsdisk/physics/`], [`marsdisk/io/`]

---

## 2. 動作環境と依存関係

* **OS／ランタイム／パッケージ**：Python 3.11+、`numpy`、`pandas`、`ruamel.yaml`、`pydantic`、`pyarrow` が必須で、`h5py` は Q_pr テーブル入出力時に必要、`matplotlib`・`xarray`・`numba` は任意。([marsdisk/run.py], [marsdisk/schema.py], [marsdisk/io/writer.py], [marsdisk/io/tables.py], [AGENTS.md])
* **外部データ**：`data/qpr_planck.h5`（Planck 平均 Q_pr）や `data/phi_tau.csv`（自遮蔽係数 Phi）のテーブルを参照する。未配置の場合は近似式で警告を出してフォールバックする。([marsdisk/io/tables.py], [marsdisk/physics/shielding.py])
* **インストール手順（番号付き）**：
  1. 仮想環境を作成：`python -m venv .venv && source .venv/bin/activate`
  2. 依存関係をインストール：`pip install numpy pandas ruamel.yaml pydantic pyarrow h5py`（必要に応じて `matplotlib` などを追加）
  3. C 実装を利用する場合は `make` で `bin/problem` をビルド（任意）。([Makefile])
* **小結**：依存は上記で完結し、GPU や C++ 拡張は必須ではない（任意利用は不明）。

**章末出典**：[`marsdisk/run.py`], [`marsdisk/io/tables.py`], [`Makefile`], [`AGENTS.md`]

---

## 3. 実行ガイド（コマンドと設定フルリファレンス）

### 3.1 典型的な実行コマンド

1. 依存パッケージを整える（例）：

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt  # 無い場合は numpy pandas pyarrow ruamel.yaml pydantic などを個別導入
   ```

2. シミュレーションを走らせる：

   ```bash
   python -m marsdisk.run --config configs/base.yml
   ```

   `--config` に任意の YAML を渡すことで、下記の全パラメータを切り替えられる。

3. 主な生成物：`out/series/run.parquet`（時系列）、`out/summary.json`（累積量とダイアグ）、`out/checks/mass_budget.csv`（質量収支ログ）、`out/run_config.json`（使用式と Git 情報）。

### 3.2 YAML で指定できる物理量

| YAML パス | 物理量・役割 | 単位 / 想定範囲 | 主な実装箇所 |
| --- | --- | --- | --- |
| `geometry.mode` | 計算ドメイン（現状 `"0D"`） | – | `marsdisk/schema.py:11` |
| `geometry.r` | 代表半径。0D 計算では必須 | m | `marsdisk/run.py:213` |
| `material.rho` | 固体粒子のバルク密度 | kg m⁻³（1000–5000） | `marsdisk/schema.py:63` |
| `temps.T_M` / `radiation.TM_K` | 火星の放射温度（Planck 平均計算に使用） | K（1000–6000） | `marsdisk/physics/radiation.py:221` |
| `sizes.s_min`, `sizes.s_max`, `sizes.n_bins` | PSD の最小粒径・最大粒径・ビン数 | m, – | `marsdisk/physics/psd.py:28` |
| `initial.mass_total` | 初期総質量（火星質量比） | Mₘ | `marsdisk/run.py:391` |
| `initial.s0_mode` | 初期 PSD モード（`"upper"`/`"mono"`） | – | `marsdisk/physics/initfields.py:47` |
| `dynamics.e0`, `dynamics.i0` | 初期離心率・傾斜 | 無次元 | `marsdisk/physics/dynamics.py:18` |
| `dynamics.t_damp_orbits` | 離心率の減衰タイムスケール | 軌道数 | `marsdisk/physics/dynamics.py:109` |
| `dynamics.f_wake` | 自己重力ウェイク倍率 | >= 1 | `marsdisk/physics/dynamics.py:96` |
| `psd.alpha`, `psd.wavy_strength` | PSD 基本勾配と “wavy” 振幅 | – | `marsdisk/physics/psd.py:28` |
| `qstar.(Qs,a_s,B,b_g,v_ref_kms)` | 破砕強度モデル係数 | – | `marsdisk/physics/qstar.py:11` |
| `disk.geometry.(r_in_RM,r_out_RM,r_profile,p_index)` | 内側リングの面密度分布 | 火星半径単位 / 指数 | `marsdisk/physics/initfields.py:17` |
| `inner_disk_mass.(use_Mmars_ratio,M_in_ratio,map_to_sigma)` | 内側リングの総質量スケール | – | 同上 |
| `surface.init_policy`, `surface.sigma_surf_init_override`, `surface.use_tcoll` | 表層初期化と Wyatt 衝突寿命スイッチ | – | `marsdisk/physics/surface.py:178` |
| `supply.mode` | 表層供給モデル（`const`/`powerlaw`/`table`/`piecewise`） | – | `marsdisk/physics/supply.py:69` |
| `supply.const.prod_area_rate_kg_m2_s` | 定数供給フラックス | kg m⁻² s⁻¹ | 同上 |
| `supply.powerlaw.(A_kg_m2_s,t0_s,index)` | 時間パワー則供給 | SI | `marsdisk/physics/supply.py:73` |
| `supply.table.path` / `supply.table.interp` | 時間×半径テーブルと補間法 | – | `marsdisk/physics/supply.py:48` |
| `supply.mixing.epsilon_mix` | 光学的薄層への混合効率 | 0–1 | `marsdisk/physics/supply.py:93` |
| `sinks.enable_sublimation`, `sinks.T_sub`, `sinks.sub_params.*` | 昇華シンクの有効化と HKL パラメータ | SI | `marsdisk/physics/sublimation.py:27`, `marsdisk/physics/sinks.py:76` |
| `sinks.enable_gas_drag`, `sinks.rho_g` | ガス抗力シンクの有効化と背景密度 | kg m⁻³ | `marsdisk/physics/sinks.py:46` |
| `radiation.Q_pr`, `radiation.qpr_table` | 灰色体 ⟨Q_pr⟩ またはテーブル指定 | – | `marsdisk/physics/radiation.py:120` |
| `shielding.phi_table` | Phi(tau, omega0, g) テーブルへのパス | – | `marsdisk/physics/shielding.py:52` |
| `numerics.(t_end_years,dt_init,safety,atol,rtol)` | 積分終了時刻・初期Δt・IMEX 安全係数・許容誤差 | SI / 無次元 | `marsdisk/run.py:320`, `marsdisk/physics/smol.py:18` |
| `io.outdir` | 出力先ディレクトリ | パス | `marsdisk/io/writer.py:25` |

### 3.3 物理量を全指定した YAML 例

```yaml
# configs/demo_full.yml
geometry:
  mode: "0D"
  r: 1.45e7
material:
  rho: 2800.0
temps:
  T_M: 2300.0
sizes:
  s_min: 5.0e-7
  s_max: 3.0
  n_bins: 48
initial:
  mass_total: 2.0e-5
  s0_mode: "upper"
dynamics:
  e0: 0.3
  i0: 0.02
  t_damp_orbits: 50.0
  f_wake: 1.5
psd:
  alpha: 1.9
  wavy_strength: 0.25
qstar:
  Qs: 3.5e7
  a_s: 0.38
  B: 0.3
  b_g: 1.36
  v_ref_kms: [3.0, 5.0]
disk:
  geometry:
    r_in_RM: 2.0
    r_out_RM: 2.8
    r_profile: "powerlaw"
    p_index: 1.0
inner_disk_mass:
  use_Mmars_ratio: true
  M_in_ratio: 4.0e-5
  map_to_sigma: "analytic"
surface:
  init_policy: "clip_by_tau1"
  sigma_surf_init_override: null
  use_tcoll: true
supply:
  mode: "piecewise"
  mixing:
    epsilon_mix: 0.8
  piecewise:
    - t_start_s: 0.0
      t_end_s: 5.0e6
      mode: "const"
      const:
        prod_area_rate_kg_m2_s: 2.0e-8
    - t_start_s: 5.0e6
      t_end_s: 6.3e7
      mode: "powerlaw"
      powerlaw:
        A_kg_m2_s: 1.0e-5
        t0_s: 5.0e6
        index: -1.2
sinks:
  enable_sublimation: true
  T_sub: 1350.0
  sub_params:
    mode: "hkl"
    alpha_evap: 0.5
    mu: 0.04
    A: 9.2
    B: 3.1e4
    dT: 60.0
    eta_instant: 0.08
    P_gas: 0.0
  enable_gas_drag: true
  rho_g: 1.0e-10
radiation:
  TM_K: 2300.0
  qpr_table: "data/qpr_planck.h5"
  Q_pr: null
shielding:
  phi_table: "data/phi_tau.csv"
numerics:
  t_end_years: 2.0
  dt_init: 5.0
  safety: 0.1
  atol: 1.0e-10
  rtol: 1.0e-6
io:
  outdir: "out/demo_full"
```

実行例：

```bash
python -m marsdisk.run --config configs/demo_full.yml
```

テーブル `data/qpr_planck.h5` と `data/phi_tau.csv` が存在すれば、それぞれ放射圧係数と自己遮蔽係数の補間が自動で有効になる。完了後は `out/demo_full` 配下に Parquet・JSON・CSV・`run_config.json` が揃い、各ステップの質量収支誤差は `checks/mass_budget.csv` に記録される。

### 3.4 可視化と後処理ワークフロー

感度掃引とヒートマップ作成には `scripts/` 配下のユーティリティを用いる。

1. **掃引実行（CSV 生成）** – `scripts/sweep_heatmaps.py` はマップIDごとに YAML を自動生成し、`python -m marsdisk.run` を多数回実行して結果を `results/map*.csv` と `sweeps/` 以下に保存する。

   ```bash
   # 例: Map-1 (r_RM × T_M) を4並列で実行し、結果を sweeps/map1/ に格納
   python scripts/sweep_heatmaps.py --map 1 --jobs 4 --outdir sweeps
   ```

   - 利用可能な `--map` 値は `1`, `1b`, `2`, `3`。Map-3 では `--num-parts` / `--part-index` による分割実行も可能。  
   - 各ケースの `summary.json`・`series/run.parquet` が `sweeps/<map>/<case_id>/out/` に書き込まれ、集約 CSV は `results/<map>.csv` として更新される。  
   - 追加指標（質量損失、beta、s_min など）は CSV の列として出力されるため任意の解析ツールで再利用できる。

2. **可視化（ヒートマップ出力）** – `scripts/plot_heatmaps.py` は `results/map*.csv` を読み込み、`figures/map*_*.png` として可視化を作成する。

   ```bash
   # 累積質量損失 (total_mass_lost_Mmars) のヒートマップを描画
   python scripts/plot_heatmaps.py --map 1 --metric total_mass_lost_Mmars

   # beta 閾値比を可視化する場合
   python scripts/plot_heatmaps.py --map 1 --metric beta_at_smin
   ```

   - `--metric` には CSV に存在する任意列を指定可能。欠損値はグレー、`case_status≠"blowout"` は自動的にマスクされる。  
   - 出力先は既定で `figures/`。カラーマップは log10 スケール（有効値のみ）で正規化される。  
   - 低温失敗帯や質量損失の r² スケーリング検証結果は `results/map*_validation.json` に保存される（Map-1 系列のみ）。

3. **追加解析** – `results/*.csv` は Pandas 互換のロングテーブル形式であり、Jupyter/Matplotlib/Seaborn 等での再可視化や統計解析に直接利用できる。未実装項目は含めていないため、必要に応じてスクリプトを拡張する際は教授との合意後に行うこと。

**章末出典**：[`configs/base.yml`], [`marsdisk/run.py`], [`marsdisk/schema.py`], [`marsdisk/io/writer.py`]

---

## 4. 全体フロー（矢印のみの地図）

```
configs/*.yml → marsdisk.schema.Config → marsdisk.run.run_zero_d → marsdisk.physics (radiation/psd/shielding/surface/…)
              → marsdisk.io.writer (parquet/json/csv) → out/
```

**注**：`marsdisk/schema.py` が YAML を構造化し、`marsdisk/run.py` が表層 ODE・Smoluchowski カーネルを統括、`marsdisk/io/writer.py` が成果物を書き出す。([marsdisk/schema.py], [marsdisk/run.py], [marsdisk/io/writer.py])

---

## 5. シミュレーション別の使い方

各シミュレーションの目的／入力／主要パラメータ／実行例／出力物／フローを最短で示す。

### 5.1 0D 表層ベースライン（`configs/mars_0d_baseline.yaml`）

* 目的：放射圧・Wyatt 衝突寿命付き 0D 表層モデルの基本挙動を確認する。([configs/mars_0d_baseline.yaml])
* 入力：`configs/mars_0d_baseline.yaml`（M_in 比・PSD・表層初期化が既定値）。
* 主要パラメータ：`psd.alpha=1.83`（PSD 3スロープ）、`surface.use_tcoll=true`、`numerics.t_end_years=2.0`。([configs/mars_0d_baseline.yaml])
* 実行例：

  ```bash
  python -m marsdisk.run --config configs/mars_0d_baseline.yaml
  ```

* 出力：`out/series/run.parquet`（時間発展）、`out/summary.json`（M_loss, beta 等）、`out/checks/mass_budget.csv`（質量差ログ。`error_percent` < 0.5% の判定は自動化されていないため手動確認が必要）。([marsdisk/run.py])

**詳細フロー図（矢印のみ）**

```
configs/mars_0d_baseline.yaml → marsdisk.schema.Config → marsdisk.run.run_zero_d → marsdisk.physics.surface.step_surface_density_S1 → marsdisk.io.writer
```

### 5.2 供給モード掃引（`configs/mars_0d_supply_sweep.yaml`）

* 目的：定数・冪法則・テーブル供給の感度を比較する。([configs/mars_0d_supply_sweep.yaml])
* 入力：`configs/mars_0d_supply_sweep.yaml`（`supply.mode` を切替えながら使用）。
* 主要パラメータ：`supply.const.prod_area_rate_kg_m2_s=5e-7`、`supply.powerlaw.A_kg_m2_s=1e-5`。([configs/mars_0d_supply_sweep.yaml], [marsdisk/physics/supply.py])
* 実行例：

  ```bash
  python -m marsdisk.run --config configs/mars_0d_supply_sweep.yaml
  ```

* 出力：供給モードごとの `summary.json` と `series/run.parquet` を比較し、`prod_subblow_area_rate` 列の差異を解析。([marsdisk/run.py])

**詳細フロー**

```
configs/mars_0d_supply_sweep.yaml → marsdisk.physics.supply.get_prod_area_rate → marsdisk.physics.surface.step_surface_density_S1 → marsdisk.io.writer
```

### 5.3 Phi テーブル適用テスト（`configs/min_sweep_phi.yml`）

* 目的：自遮蔽テーブル `phi_table` の適用効果と Sigma_tau=1 クリップを検証する。([configs/min_sweep_phi.yml])
* 入力：`configs/min_sweep_phi.yml` と `data/phi_tau.csv`（Phi テーブル）。
* 主要パラメータ：`shielding.phi_table` のパス、`surface.init_policy="clip_by_tau1"`。([marsdisk/physics/shielding.py])
* 実行例：

  ```bash
  python -m marsdisk.run --config configs/min_sweep_phi.yml
  ```

* 出力：`Sigma_tau1` 列が Phi テーブル適用前後で変化することを確認。

**詳細フロー**

```
configs/min_sweep_phi.yml → marsdisk.physics.shielding.load_phi_table → marsdisk.physics.shielding.apply_shielding → marsdisk.physics.surface.step_surface_density_S1
```

### 5.4 Q_pr テーブル適用（`configs/tm_qpr.yml`）

* 目的：Planck 平均 Q_pr テーブルの読み込みとブローアウトサイズ計算を確認する。([configs/tm_qpr.yml])
* 入力：`configs/tm_qpr.yml` と `data/qpr_planck.h5`（`tools/make_qpr_table.py` で生成）。
* 主要パラメータ：`radiation.qpr_table`、`temps.T_M`。([marsdisk/physics/radiation.py], [tools/make_qpr_table.py])
* 実行例：

  ```bash
  python -m marsdisk.run --config configs/tm_qpr.yml
  ```

* 出力：`summary.json` の `Q_pr_used` がテーブル値で更新され、`run_config.json` に使用テーブル情報が記録される。

**詳細フロー**

```
configs/tm_qpr.yml → marsdisk.io.tables.load_qpr_table → marsdisk.physics.radiation.blowout_radius / planck_mean_qpr → marsdisk.run.run_zero_d
```

### 5.5 半径依存供給テーブル（`configs/table_supply_R_sweep.yml`）

* 目的：時間×半径グリッドの供給テーブルを双線形補間し、局所前処理を評価する。([configs/table_supply_R_sweep.yml])
* 入力：`configs/table_supply_R_sweep.yml` と `data/supply_rate_R_template.csv`。
* 主要パラメータ：`supply.table.path`、`geometry.mode="0D"`（局所半径を `disk.geometry` から取得）。([marsdisk/physics/supply.py])
* 実行例：

  ```bash
  python -m marsdisk.run --config configs/table_supply_R_sweep.yml
  ```

* 出力：`prod_subblow_area_rate` がテーブル値で変化し、`series/run.parquet` に半径依存の供給応答が残る。

**詳細フロー**

```
configs/table_supply_R_sweep.yml → marsdisk.physics.supply._TableData.load/interp → marsdisk.run.run_zero_d → marsdisk.io.writer
```

> **5.2 / 5.3 …** 以降、同形式で追加のシナリオを拡張可能。

**章末出典**：[`configs/`], [`marsdisk/physics/`]

---

## 6. 依存関係マップ（内部）

```
src/smoluchowski.c → src/smoluchowski.h → tests/test_smol.c
src/hybrid.c → rebound/src/… (プレースホルダ)
marsdisk/run.py → marsdisk/physics/* → marsdisk/io/writer.py → out/
marsdisk/schema.py → marsdisk/constants.py
scripts/plot_heatmaps.py, scripts/sweep_heatmaps.py → pandas/matplotlib (解析用)
```

* 外部ライブラリ名とバージョンは本文 §2 に集約。
* **小結**：現状の Python モジュール間に循環依存は確認されていない。([marsdisk/physics/__init__.py], [src/], [scripts/])

**章末出典**：[`marsdisk/`], [`src/`], [`scripts/`]

---

## 7. 再現実行（論文図・既定実験）

1. データ取得：`data/qpr_planck.h5` を `tools/make_qpr_table.py` で生成、`data/phi_tau.csv` を外部実験値から整備（URL/DOI は未提供）。
2. パラメータ設定：`configs/tm_qpr.yml`・`configs/min_sweep_phi.yml` を使用し、必要に応じて `supply` セクションを調整。
3. 実行：

   ```bash
   python -m marsdisk.run --config configs/tm_qpr.yml
   python -m marsdisk.run --config configs/min_sweep_phi.yml
   ```

4. 産物配置：`out/` 配下（`series/`, `summary.json`, `checks/mass_budget.csv`, `run_config.json`）。
5. 検証：`checks/mass_budget.csv` の `error_percent` 列を目視し（基準 0.5% はドキュメント側の指標で自動判定は実装されていない）、`summary.json` の `case_status` が `blowout` となるかを確認（表層供給がゼロの場合は `failed` となる点に注意）。

**章末出典**：[`tools/make_qpr_table.py`], [`marsdisk/run.py`]

---

## 8. トラブルシューティング

* **欠落データ**：`data/qpr_planck.h5`／`data/phi_tau.csv` が存在しない場合、警告が出て近似式へフォールバックする。テーブルを再生成し、ハッシュ（例：`md5sum data/qpr_planck.h5`）で検証。([marsdisk/io/tables.py])
* **環境差**：依存バージョンが固定されていないため、仮想環境で `pip install …` をやり直す。([AGENTS.md])
* **計算資源不足**：`sizes.n_bins` や `numerics.dt_init` を減らし、`marsdisk.physics.smol.step_imex_bdf1_C3` の安全係数で安定化する。([configs/base.yml], [marsdisk/physics/smol.py])
* **再現ずれ**：乱数シードは `marsdisk/run.py` 冒頭で固定 (`DEFAULT_SEED=12345`)。積分刻みは `dt_init`・`numerics.safety` を合わせ、`surface.use_tcoll` を構成ファイルで一致させる。([marsdisk/run.py])

**章末出典**：[`marsdisk/io/tables.py`], [`marsdisk/physics/smol.py`], [`marsdisk/run.py`]

---

## 9. FAQ（事実ベース）

* Q. **最小実行に必須の外部データは何か。**  
  A. 0D ベースラインはテーブル未配置でも近似式で走るが、`data/qpr_planck.h5` と `data/phi_tau.csv` を置くと物理量がテーブル値で再現される。([marsdisk/io/tables.py])
* Q. **所要時間の目安は。**  
  A. 既定の 0D 計算は数十秒で終了するが、正式なベンチマーク値はリポジトリ内に記載がなく不明。

---

## 10. 既知の制約・未解決事項

1. **（優先度 高）** `Step1/extended_static_map.py` などテストが参照する補助スクリプトが現行ツリーに含まれておらず、`tests/test_mass_tau.py` が失敗する。([tests/test_mass_tau.py])
2. **（中）** ガス抗力スイッチは `sinks.enable_gas_drag` で用意されているが、実測に基づく係数や検証例が未提供。([marsdisk/physics/sinks.py])
3. **（低）** C 実装 `src/hybrid.c` はプレースホルダで、REBOUND 結合ハイブリッド計算が未完成。([src/hybrid.c])

---

## 11. ライセンス・引用・連絡先

* ライセンス：リポジトリに SPDX／LICENSE ファイルが存在せず不明。
* 引用方法：`CITATION.cff` や `references.bib` は未収録で不明。
* 連絡先：メンテナ連絡先情報は未記載。

---

# 付録A：実装済み支配方程式と記号表

本付録では、リポジトリ内で実装され実際に数値計算へ組み込まれている式のみを整理する。番号は本文と対応しない。

### A.1 ケプラー運動（`marsdisk/grid.py`）

```math
\Omega(r)=\sqrt{\frac{G M_{\rm Mars}}{r^{3}}},\qquad v_{K}(r)=\sqrt{\frac{G M_{\rm Mars}}{r}}.
```

### A.2 放射圧とブローアウト（`marsdisk/physics/radiation.py`）

```math
\beta(s)=\frac{3\,\sigma_{\rm SB}\,T_{M}^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle}{4 G M_{\rm Mars} c\,\rho\,s},\qquad
s_{\rm blow}=\frac{3\,\sigma_{\rm SB}\,T_{M}^{4}\,R_{\rm Mars}^{2}\,\langle Q_{\rm pr}\rangle}{2 G M_{\rm Mars} c\,\rho}.
```

### A.3 粒径分布と不透明度（`marsdisk/physics/psd.py`）

```math
n(s)\propto\left(\frac{s}{s_{\min}}\right)^{-q(s)}\Bigl[1+A_{\rm w}\sin\Bigl(\frac{2\pi\ln(s/s_{\min})}{\ln(s_{\max}/s_{\min})}\Bigr)\Bigr],
```
```math
\kappa=\frac{\int \pi s^{2} n(s)\,ds}{\int \tfrac{4}{3}\pi\rho s^{3} n(s)\,ds}.
```

### A.4 自遮蔽補正（`marsdisk/physics/shielding.py`）

```math
\kappa_{\rm eff}=\Phi(\tau,w_{0},g)\,\kappa,\qquad \Sigma_{\tau=1}=\frac{1}{\kappa_{\rm eff}},\qquad \tau=\kappa\,\Sigma_{\rm surf}.
```

### A.5 表層質量収支（`marsdisk/physics/surface.py`）

```math
\frac{d\Sigma_{\rm surf}}{dt}=P-\frac{\Sigma_{\rm surf}}{t_{\rm blow}}-\frac{\Sigma_{\rm surf}}{t_{\rm coll}}-\frac{\Sigma_{\rm surf}}{t_{\rm sink}},
```
```math
t_{\rm blow}=\frac{1}{\Omega},\qquad t_{\rm coll}=\frac{1}{2\,\Omega\,\tau},\qquad \dot{M}_{\rm out}=\frac{\Sigma_{\rm surf}\,\Omega\,A}{M_{\rm Mars}}.
```

### A.6 衝突カーネルと IMEX 更新（`marsdisk/physics/collide.py`, `marsdisk/physics/smol.py`）

```math
C_{ij}=\frac{N_{i}N_{j}}{1+\delta_{ij}}\frac{\pi (s_{i}+s_{j})^{2} v_{ij}}{\sqrt{2\pi}\,H_{ij}},
```
```math
N_{k}^{n+1}=\frac{N_{k}^{n}+\Delta t\,(\text{gain}_{k}-S_{k})}{1+\Delta t\,\text{loss}_{k}},\qquad
\text{gain}_{k}=\tfrac{1}{2}\sum_{ij}C_{ij}Y_{kij},
```
```math
\varepsilon_{\rm mass}=\frac{\bigl|M^{n+1}+\Delta t\,\dot{M}_{\rm prod}-M^{n}\bigr|}{M^{n}},\qquad M^{n}=\sum_{k}m_{k}N_{k}^{n}.
```

### A.7 破砕エネルギーと最大残骸（`marsdisk/physics/fragments.py`, `marsdisk/physics/qstar.py`）

```math
Q_{R}=\frac{0.5\,\mu v^{2}}{m_{1}+m_{2}},\qquad \frac{M_{\rm LR}}{M_{\rm tot}}=0.5\left(2-\frac{Q_{R}}{Q_{RD}^{\ast}}\right),
```
```math
Q_{D}^{\ast}(s,\rho,v)=Q_{s}\left(\frac{s}{1\,\rm m}\right)^{-a_{s}}+B\,\rho\left(\frac{s}{1\,\rm m}\right)^{b_{g}}.
```

### A.8 動力学補助式（`marsdisk/physics/dynamics.py`）

```math
v_{ij}=v_{K}\sqrt{1.25\,e^{2}+i^{2}},\qquad c_{\rm eq}=\sqrt{\frac{f_{\rm wake}\,\tau}{1-\varepsilon^{2}}},
```
```math
e(t+\Delta t)=e_{\rm eq}+(e(t)-e_{\rm eq})\,\exp\left(-\frac{\Delta t}{t_{\rm damp}}\right).
```

### A.9 昇華とガスシンク（`marsdisk/physics/sublimation.py`, `marsdisk/physics/sinks.py`）

```math
\log_{10}\!\left(\frac{P_{\rm sat}}{\rm Pa}\right)=A-\frac{B}{T},\qquad
J=\alpha_{\rm evap}\,(P_{\rm sat}-P_{\rm gas})\sqrt{\frac{\mu}{2\pi R T}},
```
```math
s_{\rm sink}=\eta_{\rm instant}\,t_{\rm ref}\,\frac{J}{\rho},\qquad t_{\rm drag}\approx\frac{\rho_{p}\,s}{\rho_{g} c_{s}},\qquad t_{\rm sink}=\min(t_{\rm sub},t_{\rm drag},\ldots).
```

### A.10 初期場と外部供給（`marsdisk/physics/initfields.py`, `marsdisk/physics/supply.py`）

```math
\Sigma(r)=\begin{cases}
\dfrac{M_{\rm in}}{\pi (r_{\rm out}^{2}-r_{\rm in}^{2})} & (p\approx 0),\\[0.75em]
\dfrac{M_{\rm in}(2-p)}{2\pi\bigl(r_{\rm out}^{2-p}-r_{\rm in}^{2-p}\bigr)}\,r^{-p} & (\text{otherwise}),
\end{cases}
```
```math
\Sigma_{\rm surf,0}=\min(f_{\rm surf}\,\Sigma,1/\kappa_{\rm eff}),\qquad P(t)=A\bigl((t-t_{0})+\varepsilon\bigr)^{\rm index},
```
```math
P(t,r)=\sum_{i,j}w_{ij}(t,r)\,P_{ij},\qquad \dot{M}_{\rm out}^{\rm area}=P(t,r). 
```

**記号**：主要定数（G：重力定数、c：光速、sigma_SB：ステファン=ボルツマン定数）は `marsdisk/constants.py` を参照。

---

# 付録B：全体フロー・依存マップ・詳細フロー（最終形）

**全体フロー（再掲）**

```
入力（configs/*.yml, data/*.csv/h5） → marsdisk.schema → marsdisk.run.run_zero_d → marsdisk.physics.* → marsdisk.io.writer → out/*
```

**依存関係マップ（例）**

```
marsdisk/run.py → marsdisk/physics/radiation.py → marsdisk/io/tables.py → data/qpr_planck.h5
                                     ↓
                                   shielding.py → data/phi_tau.csv
                                   surface.py → sinks.py / fragments.py / psd.py → smol.py → collide.py
scripts/*.py → marsdisk/physics.*（解析用）
src/*.c → tests/test_smol.c（C テスト）
```

**シミュレーション詳細（例）**

```
Sim-Base: configs/base.yml → marsdisk.run → surface.step_surface_density_S1 → writer.write_parquet/json
Sim-Supply: configs/mars_0d_supply_sweep.yaml → supply.get_prod_area_rate → run_zero_d → writer
Sim-Qpr: configs/tm_qpr.yml → io.tables.load_qpr_table → radiation.planck_mean_qpr → run_zero_d → writer
```

---

# 付録C：記号表（アルファベット順の抜粋）

* a：軌道長半径
* a_blow：ブローアウト境界粒径（`marsdisk/physics/radiation.py`）
* c_s：音速
* kappa：表層質量不透明度（`marsdisk/physics/psd.py`）
* nu：動粘性（未実装）
* Omega：角速度（`marsdisk/grid.py`）
* Sigma：面密度（`marsdisk/physics/initfields.py`）
* beta：放射圧／重力比（`marsdisk/physics/radiation.py`）
* Sigma_surf：表層面密度（`marsdisk/physics/surface.py`）
* t_blow：ブローアウト時間（`marsdisk/physics/surface.py`）
* M_loss：累積質量損失（`marsdisk/run.py` 出力）

---

### 参考（物理背景の一次文献）

* 表層ダストの放射圧駆動外向き輸送とその流束評価：Takeuchi & Lin (2003)
* 火星巨大衝突後の蒸気・凝縮粒子の散逸：Hyodo et al. (2018)
