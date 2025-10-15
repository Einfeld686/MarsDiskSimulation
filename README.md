# marsshearingsheet 取扱説明書（完成版・差し込み用）

**バージョン情報**

* 対象ブランチ：`main`（ユーザー指定）
* コミット：`9b8bd2e1e622d1e458e7715af55021d1877e5eec / 2025-10-02T20:45:42+09:00`
* 探索範囲：既定ブランチのみ（タグ／Release／LFS／Wiki／Issues 添付は本書では扱わない）

---

## 1. 概要（アップグレード版）

本セクションでは、本コードがどの物理プロセスをどの方程式で記述し、どのモジュールがそれらを実装しているかをまとめる。中心となるのは、火星ロッシュ限界内の薄いダスト円盤で生じる「内部破砕 → sub-blow-out 粒子生成 → 表層供給 → 放射圧剥離」という質量パイプラインであり、全体は `marsdisk.run.run_zero_d` が 0D モデルとして統括する。([marsdisk/run.py:193])

### 1.1 主要方程式と役割
- **ケプラー動力学**：角速度 `Ω(r)=√(G M_M/r³)`・公転速度 `v_K=√(G M_M/r)` がダイナミカルタイムと吹き飛び時間 `t_blow=1/Ω` を定義する。[marsdisk/grid.py:19]
- **放射圧対重力比**：`β=3 σ_SB T_M⁴ R_M² ⟨Q_pr⟩ /(4 G M_M c ρ s)` により `β≥0.5` がブローアウト判定、`s_blow = 3 σ_SB T_M⁴ R_M² ⟨Q_pr⟩ /(2 G M_M c ρ)` が最小粒径を規定する。[marsdisk/physics/radiation.py:221]
- **粒径分布と不透明度**：三勾配 PSD `n(s)∝(s/s_min)^(-q)` と “wavy” 補正に基づき、`κ = ∫ π s² n(s) ds / ∫ (4/3) π ρ s³ n(s) ds` を算出し光学深度 `τ=κ Σ_surf` を得る。[marsdisk/physics/psd.py:119]
- **自己遮蔽**：`κ_eff = Φ(τ,w₀,g) κ` と `Σ_{τ=1}=1/κ_eff` により光学深度 1 を超える表層面密度をクリップする。[marsdisk/physics/shielding.py:81]
- **表層 ODE**：`dΣ_surf/dt = P - Σ/t_blow - Σ/t_coll - Σ/t_sink` が放射圧剥離・Wyatt 衝突寿命 `t_coll=1/(2Ωτ)`・追加シンクを統合し、外向面フラックス `Σ_surf Ω` を生む。[marsdisk/physics/surface.py:138]
- **衝突破砕**：相対速度 `v_{ij}=v_K √(1.25 e² + i²)` ・衝突カーネル `C_{ij}` ・破砕エネルギー `Q_R=0.5 μ v²/(m₁+m₂)` ・残存率 `M_{LR}/M_tot=0.5(2-Q_R/Q_{RD}^*)` を用いて sub-blow-out 粒子生成率 `Σ_{i≤j} C_{ij} m^{sub}_{ij}` を得る。[marsdisk/physics/collide.py:18]
- **Smoluchowski IMEX-BDF(1)**：`N^{n+1}=(N^n+Δt(gain-S))/(1+Δt loss)` が内部 PSD の数密発展を解き、`ε_mass=|M^{n+1}+Δt \.dot{M}_{prod}-M^n|/M^n` で質量保存を監視する。[marsdisk/physics/smol.py:18]
- **昇華・ガス抗力**：ハーツ–クヌーセン–ラングミュア式 `J=α(P_sat-P_gas) √(μ/(2π R T))` から `s_sink=η t_ref J/ρ` を導出し、Epstein 近似 `t_drag=ρ_p s/(ρ_g c_s)` と合わせて `t_sink=min(...)` を設定する。[marsdisk/physics/sublimation.py:85]
- **供給と出力換算**：外部供給律 `P=A((t-t_0)+ε)^{index}`／テーブル補間で `P(t)` を得て、外向質量流束を `\dot{M}_{out} = (Σ_surf Ω · area)/M_M` へ換算し累積損失 `M_{loss}^{cum}` を更新する。[marsdisk/physics/supply.py:69][marsdisk/run.py:352]

### 1.2 実装モジュール
これらの方程式は以下のモジュールで連鎖している。
- `marsdisk.run`: 設定読込・PSD 初期化・遮蔽適用・表層 ODE 解・質量収支出力。
- `marsdisk/physics/radiation|psd|shielding|surface|collide|smol|fragments|sinks|dynamics`: 各式の実装。
- `marsdisk/io.writer|tables`: Q_pr/Φ テーブル補間と出力書き出し。

### 1.3 モデル範囲
自己重力ポアソン解、Toomre Q、角運動量輸送解析などは未実装であり、0D 表層モデルと内部破砕–放射圧連成に焦点を絞っている。追加プロセスを利用する場合は拡張実装が必要である。

**章末出典（リポジトリ一次情報）**：[`marsdisk/run.py`], [`marsdisk/physics/`], [`marsdisk/io/`]

---

## 2. 動作環境と依存関係

* **OS／ランタイム／パッケージ**：Python 3.11+、`numpy`、`pandas`、`ruamel.yaml`、`pydantic`、`pyarrow` が必須で、`h5py` は Q_pr テーブル入出力時に必要、`matplotlib`・`xarray`・`numba` は任意。([marsdisk/run.py], [marsdisk/schema.py], [marsdisk/io/writer.py], [marsdisk/io/tables.py], [AGENTS.md])
* **外部データ**：`data/qpr_planck.h5`（Planck 平均 Q_pr）や `data/phi_tau.csv`（自遮蔽係数 Φ）のテーブルを参照する。未配置の場合は近似式で警告を出してフォールバックする。([marsdisk/io/tables.py], [marsdisk/physics/shielding.py])
* **インストール手順（番号付き）**：
  1. 仮想環境を作成：`python -m venv .venv && source .venv/bin/activate`
  2. 依存関係をインストール：`pip install numpy pandas ruamel.yaml pydantic pyarrow h5py`（必要に応じて `matplotlib` などを追加）
  3. C 実装を利用する場合は `make` で `bin/problem` をビルド（任意）。([Makefile])
* **小結**：依存は上記で完結し、GPU や C++ 拡張は必須ではない（任意利用は不明）。

**章末出典**：[`marsdisk/run.py`], [`marsdisk/io/tables.py`], [`Makefile`], [`AGENTS.md`]

---

## 3. クイックスタート（最小実行）

* **入力→出力の対応（最小例）**

  | 入力 | 出力 |
  | ---- | ---- |
  | `configs/base.yml` | `out/series/run.parquet`, `out/summary.json`, `out/checks/mass_budget.csv` |

* **実コマンド（貼って動く形）**

  ```bash
  # リポジトリ直下で実行
  python -m marsdisk.run --config configs/base.yml
  ```

* **簡易検証**

  ```bash
  test -f out/summary.json
  test -f out/series/run.parquet
  wc -l out/checks/mass_budget.csv
  md5sum out/summary.json out/series/run.parquet
  ```

* **小結**：上記が通れば Python 依存が揃っており、最低限の 0D 表層計算が成功している（所要時間・メモリ要求は不明）。

**章末出典**：[`configs/base.yml`], [`marsdisk/run.py`]

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

* 出力：`out/series/run.parquet`（時間発展）、`out/summary.json`（M_loss, β 等）、`out/checks/mass_budget.csv`（質量差 <0.5% ログ）。([marsdisk/run.py])

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

### 5.3 Φ テーブル適用テスト（`configs/min_sweep_phi.yml`）

* 目的：自遮蔽テーブル `phi_table` の適用効果と Σ_{τ=1} クリップを検証する。([configs/min_sweep_phi.yml])
* 入力：`configs/min_sweep_phi.yml` と `data/phi_tau.csv`（Φ テーブル）。
* 主要パラメータ：`shielding.phi_table` のパス、`surface.init_policy="clip_by_tau1"`。([marsdisk/physics/shielding.py])
* 実行例：

  ```bash
  python -m marsdisk.run --config configs/min_sweep_phi.yml
  ```

* 出力：`Sigma_tau1` 列が Φ テーブル適用前後で変化することを確認。

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
5. 検証：`checks/mass_budget.csv` の `error_percent` < 0.5%、`summary.json` の `case_status` が `blowout` となるかを確認（表層供給がゼロの場合は `failed` となる点に注意）。

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

# 付録A：支配方程式と記号表（リポジトリ内の式と整合）

### (1) 角速度とエピサイクル

```math
\Omega(R)=\sqrt{\frac{GM}{R^{3}}},\qquad\kappa^{2}(R)=R\frac{d\Omega^{2}}{dR}+4\Omega^{2}.
```
**参照**：`marsdisk/grid.py` がケプラー角速度 `omega_kepler` を実装（エピサイクル係数は未使用だがケプラー場では $\kappa=\Omega$。([marsdisk/grid.py])

### (2) 局所せん断シートの運動方程式（圧力・自己重力・粘性を含む）

```math
\frac{d\boldsymbol{u}}{dt}-2\Omega\hat{\boldsymbol{z}}\times\boldsymbol{u}
= 3\Omega^{2}x\hat{\boldsymbol{x}}
-\frac{1}{\rho}\nabla P
-\nabla\Phi_{\mathrm{sg}}
+\nu\nabla^{2}\boldsymbol{u}.
```
**参照**：表層 ODE `marsdisk/physics/surface.step_surface_density_S1` が放射圧・Wyatt 衝突・追加シンクを含む 0D 版を実装し、運動方程式の簡約形として用いている。([marsdisk/physics/surface.py])

### (3) 薄膜ポアソン方程式

```math
\nabla^{2}\Phi_{\mathrm{sg}}=4\pi G\Sigma\,\delta(z).
```
**参照**：現行コードに自己重力ポアソン解は存在せず未実装。([marsdisk/physics/__init__.py])

### (4) Toomre 安定判定

```math
Q=\frac{c_{s}\kappa}{\pi G\Sigma}.
```
**参照**：Toomre Q の計算は未実装。([marsdisk/physics/__init__.py])

### (5) 自重力薄膜の分散関係

```math
\omega^{2}=\kappa^{2}-2\pi G\Sigma|k|+c_{s}^{2}k^{2}.
```
**参照**：分散関係の解析機能は未実装。([marsdisk/physics/__init__.py])

### (6) ロッシュ限界

```math
a_{\mathrm{R}}=\alpha R_{p}\left(\frac{\rho_{p}}{\rho_{s}}\right)^{1/3}.
```
**参照**：ロッシュ限界の計算関数は未実装。([marsdisk/constants.py])

### (7) ヒル半径

```math
R_{\mathrm{H}}=a\left(\frac{m}{3M}\right)^{1/3}.
```
**参照**：ヒル半径の専用計算は未実装。([marsdisk/constants.py])

### (8) 角運動量流束・応力

```math
\mathcal{F}_{J}=r\,\Sigma\,\left\langle v_{r}v_{\phi}-\nu r\frac{\partial\Omega}{\partial r}\right\rangle.
```
**参照**：角運動量流束の評価機能は未実装。([marsdisk/physics/__init__.py])

### (9) 粘性時定数

```math
t_{\nu}\sim\frac{R^{2}}{\nu}.
```
**参照**：粘性時定数の直接計算は未実装（`marsdisk/physics/viscosity.py` はプレースホルダ）。([marsdisk/physics/viscosity.py])

### (10) 表面層の放射圧とガス抗力による外向き流

```math
v_{r,\mathrm{d}}=v_{r,\mathrm{g}}+\beta T_{s} v_{K,\mathrm{mid}}
```
**参照**：放射圧 β とブローアウト半径は `marsdisk/physics/radiation.py` が提供するが、ガス抗力項との和としての速度式は未実装。([marsdisk/physics/radiation.py], [marsdisk/physics/sinks.py])

### (11) 巨大衝突後の蒸気・凝縮粒子の揮発性散逸（概念式）

* **脱出パラメータ**：\$lambda_{\mathrm{esc}}=\frac{GMm}{kT r}$。
* **β による輻射圧の有効重力低減**：\(M_{\mathrm{eff}}=(1-\beta)M$。

**参照**：現行コードは β を計算するが、揮発性散逸モデルは未実装。([marsdisk/physics/radiation.py])

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

* $a$：軌道長半径
* $a_{\rm blow}$：ブローアウト境界粒径（`marsdisk/physics/radiation.py`）
* $c_s$：音速
* $\kappa$：表層質量不透明度（`marsdisk/physics/psd.py`）
* $\nu$：動粘性（未実装）
* $\Omega$：角速度（`marsdisk/grid.py`）
* $\Sigma$：面密度（`marsdisk/physics/initfields.py`）
* $\beta$：放射圧／重力比（`marsdisk/physics/radiation.py`）
* $\Sigma_{\rm surf}$：表層面密度（`marsdisk/physics/surface.py`）
* $t_{\rm blow}$：ブローアウト時間（`marsdisk/physics/surface.py`）
* $M_{\rm loss}$：累積質量損失（`marsdisk/run.py` 出力）

---

### 参考（物理背景の一次文献）

* 表層ダストの放射圧駆動外向き輸送とその流束評価：Takeuchi & Lin (2003)
* 火星巨大衝突後の蒸気・凝縮粒子の散逸：Hyodo et al. (2018)
