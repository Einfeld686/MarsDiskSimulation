# glossary (A-priority terms only)

本ファイルは、火星起源ダスト円盤モデルのうち「最重要（A優先）」な用語だけをまとめた AI・開発者向け用語集です。数式や導出は `analysis/equations.md` を唯一の参照源とし、ここでは意味づけと参照リンクのみを保持します。

---

## 目次

1. [コア用語集（A優先）](#コア用語集a優先)
2. [変数命名ガイドライン](#変数命名ガイドライン)
3. [略語一覧](#略語一覧)
4. [単位規約](#単位規約)
5. [時間スケール命名規則](#時間スケール命名規則)
6. [接頭辞・接尾辞の意味](#接頭辞接尾辞の意味)

---

## コア用語集（A優先）

| term_id | label | audience | math_level | origin | status | priority | definition_ja | eq_refs | lit_refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| G.A01 | Mars moon-forming disk | both | light | papers+code | draft | A | 巨大衝突後に火星のまわりへ残るダスト主体の円盤。「火星月形成円盤」として Phobos/Deimos の材料供給源になり、本リポジトリの時間発展モデルが追跡する対象。 |  | Hyodo2017a,Hyodo2017b,Hyodo2018,Ronnet2016,Pignatale2018,Kuramoto2024,CanupSalmon2018 |
| G.A02 | gas-poor disk | both | light | papers+code | draft | A | 蒸気や背景ガスの質量が固体よりずっと小さい状態の月形成円盤。ガス抗力や TL2003 型表層アウトフローを無視できる前提として採用される「ガス希薄ディスク」。 |  | Hyodo2017a,Hyodo2018,CanupSalmon2018,Kuramoto2024 |
| G.A03 | TL2003 gas-rich surface outflow | me | full | paper:TakeuchiLin2003 | draft | A | 光学的に厚いガス層が支配する表層ダストの外向き流出モデルである「TL2003 表層アウトフロー」。本プロジェクトでは gas-rich 感度試験でのみ `ALLOW_TL2003=true` とし、標準では無効化する。 | E.007 | TakeuchiLin2003,StrubbeChiang2006 |
| G.A04 | radiation-pressure ratio β | both | full | code:radiation.py | draft | A | 放射圧と重力の比を表す無次元量である β。0.5 を超えると粒子軌道が束縛を外れ、吹き飛びサイズより小さい粒子が系外へ逃げる。 | E.013 | Hyodo2018,Ronnet2016,StrubbeChiang2006 |
| G.A05 | blow-out size s_blow | both | light | code:radiation.py | draft | A | β≃0.5 となる粒径で「吹き飛びサイズ」s_blow。これより小さいダストは放射圧で短時間に失われ、PSD の実効的最小サイズとして扱う。 | E.014 | Hyodo2018,StrubbeChiang2006 |
| G.A06 | Planck-mean Q_pr | both | full | code:radiation.py | draft | A | 火星表面温度でプランク平均した放射圧効率 ⟨Q_pr⟩。放射圧パラメータ β や吹き飛びサイズ s_blow など放射依存の量は、このプランク平均 Q_pr を通じて評価する。 | E.004 | Hyodo2018,Ronnet2016 |
| G.A07 | sub-blow-out particles | both | light | code+papers | draft | A | 吹き飛びサイズ s_blow より小さく、β が大きいため 1 公転以内に系外へ放出される小粒子群。内部破砕カスケードで供給され、円盤質量損失の主担い手となる「sub-blow-out 粒子」。 | E.035 | Hyodo2018,StrubbeChiang2006 |

---

## 変数命名ガイドライン

### 全般原則

1. **snake_case を基本とする**: Python 標準に従い、変数・関数は `lower_snake_case`
2. **物理量は単位を接尾辞で示す**: `r_m`（メートル）、`T_K`（ケルビン）、`t_s`（秒）
3. **無次元量は接尾辞なし**: `tau`、`beta`、`alpha`
4. **累積量は `_cum` 接尾辞**: `M_loss_cum`、`M_sink_cum`
5. **レートは `_dot` または `_rate` 接尾辞**: `M_out_dot`、`prod_area_rate`
6. **設定値は `_cfg` 接尾辞**: `blowout_enabled_cfg`

### 主要変数の命名パターン

| パターン | 例 | 意味 |
|----------|-----|------|
| `<quantity>_<unit>` | `r_m`, `T_K`, `t_s` | 物理量と単位 |
| `<quantity>_<source>` | `T_M_used`, `r_source` | 値の出典を明示 |
| `<quantity>_at_<condition>` | `beta_at_smin`, `Q_pr_at_smin` | 特定条件での評価値 |
| `<quantity>_<adjective>` | `s_min_effective`, `kappa_eff` | 修飾された物理量 |
| `d<quantity>_dt_<process>` | `dSigma_dt_blowout`, `ds_dt_sublimation` | 時間微分（プロセス別） |
| `t_<process>` | `t_blow`, `t_coll`, `t_sink` | 時間スケール |
| `<bool>_enabled` | `blowout_enabled`, `collisions_active` | フラグ変数 |

---

## 略語一覧

### 物理量の略語

| 略語 | 正式名 | 日本語 | コード例 |
|------|--------|--------|----------|
| `s` | size / radius | 粒径 | `s_min`, `s_max` |
| `a` | semi-major axis / size | 軌道長半径 / 粒径 | `a_blow` |
| `r` | orbital radius | 軌道半径 | `r_m`, `r_RM` |
| `Omega` | angular frequency | 角速度 | `Omega_step` |
| `tau` | optical depth | 光学深度 | `tau_eff`, `tau_los` |
| `kappa` | opacity | 不透明度 | `kappa_surf`, `kappa_eff` |
| `Sigma` | surface density | 面密度 | `Sigma_surf`, `Sigma_tau1` |
| `rho` | mass density | 質量密度 | `rho_used` |
| `beta` | radiation pressure ratio | 放射圧比 | `beta_at_smin` |
| `Q_pr` | radiation pressure efficiency | 放射圧効率 | `qpr_mean` |
| `alpha` | PSD power-law index | PSD 勾配 | `cfg.psd.alpha` |
| `chi` | blow-out correction factor | ブローアウト補正係数 | `chi_blow_eff` |
| `psi`, `Phi` | shielding coefficient | 遮蔽係数 | `psi_shield`, `phi_tau_fn` |
| `e` | eccentricity | 離心率 | `e0_effective` |
| `i` | inclination | 軌道傾斜角 | `i0_effective` |

### プロセスの略語

| 略語 | 正式名 | 日本語 |
|------|--------|--------|
| `blow` | blow-out | ブローアウト（放射圧脱出） |
| `coll` | collision | 衝突 |
| `sub` | sublimation | 昇華 |
| `sink` | sink (loss mechanism) | シンク（損失機構） |
| `prod` | production | 生成 |
| `rp` | radiation pressure | 放射圧 |
| `hydro` | hydrodynamic escape | 流体力学的散逸 |

### システムの略語

| 略語 | 正式名 | 日本語 |
|------|--------|--------|
| `PSD` | Particle Size Distribution | 粒径分布 |
| `ODE` | Ordinary Differential Equation | 常微分方程式 |
| `IMEX` | Implicit-Explicit | 陰陽混合法 |
| `BDF` | Backward Differentiation Formula | 後退差分公式 |
| `RM` | Mars radius (R_Mars) | 火星半径 |
| `los` | line of sight | 視線方向 |
| `cfg` | configuration | 設定 |

---

## 単位規約

### SI 基本単位の接尾辞

| 接尾辞 | 単位 | 例 |
|--------|------|-----|
| `_m` | メートル (m) | `r_m`, `s_min` (暗黙でm) |
| `_s` | 秒 (s) | `t_blow_s`, `dt` (暗黙でs) |
| `_K` | ケルビン (K) | `T_M_K`, `T_use` |
| `_kg` | キログラム (kg) | `M_loss_kg` |
| `_Pa` | パスカル (Pa) | `P_gas_Pa` |

### 複合単位の接尾辞

| 接尾辞 | 単位 | 例 |
|--------|------|-----|
| `_kg_m2` | kg m⁻² | `Sigma_surf` (面密度) |
| `_kg_m2_s` | kg m⁻² s⁻¹ | `prod_area_rate_kg_m2_s` |
| `_m_s` | m s⁻¹ | `v_K` (ケプラー速度) |
| `_rad_s` | rad s⁻¹ | `Omega` (角速度) |
| `_m2_kg` | m² kg⁻¹ | `kappa` (不透明度) |

### 天文単位

| 接尾辞 | 単位 | 例 |
|--------|------|-----|
| `_RM` | 火星半径 (R_Mars) | `r_RM`, `r_in_RM` |
| `_Mmars` | 火星質量 (M_Mars) | `M_loss` (暗黙で M_Mars) |
| `_years` | 年 | `t_end_years` |
| `_orbits` | 公転周期 | `t_end_orbits` |

### 暗黙の単位（接尾辞なし）

以下の変数は文脈から単位が明らかなため、接尾辞を省略:

| 変数 | 暗黙の単位 | 備考 |
|------|-----------|------|
| `s_min`, `s_max`, `a_blow` | m | 粒径は常にメートル |
| `dt` | s | 時間刻みは常に秒 |
| `Omega` | rad s⁻¹ | 角速度 |
| `tau` | 無次元 | 光学深度 |
| `beta` | 無次元 | 放射圧比 |
| `alpha` | 無次元 | PSD 勾配 |
| `M_loss_cum`, `M_out_dot` | M_Mars | 質量は火星質量単位 |

---

## 時間スケール命名規則

時間スケールは `t_<process>` のパターンで命名:

| 変数名 | 物理的意味 | 式 | 出典 |
|--------|-----------|-----|------|
| `t_blow` | ブローアウト時間 | χ/Ω | Strubbe & Chiang (2006) |
| `t_coll` | 衝突時間 | 1/(Ω τ) | Wyatt (2008) |
| `t_sink` | シンク総合時間 | 調和平均 | - |
| `t_orb` | 公転周期 | 2π/Ω | - |
| `t_sub` | 昇華時間 | s / \|ds/dt\| | HKL |
| `t_solid` | 固体維持時間 | 競合時間の min | - |
| `t_damp` | 減衰時間 | dynamics 由来 | - |

### 時間スケール計算の階層

```text
t_sink = 1 / (1/t_sub + 1/t_drag + ...)   # 調和平均
t_solid = min(t_sub, t_coll)               # 競合時間
gate_factor = t_solid / (t_solid + t_blow) # ゲート係数
```

---

## 接頭辞・接尾辞の意味

### 接頭辞

| 接頭辞 | 意味 | 例 |
|--------|------|-----|
| `d` | 差分・微分 | `dSigma_dt`, `delta_sigma` |
| `n_` | 個数・カウント | `n_steps`, `n_bins` |
| `is_`, `has_` | ブール判定 | `is_last`, `has_output` |
| `_` | プライベート | `_resolve_blowout`, `_safe_float` |

### 接尾辞

| 接尾辞 | 意味 | 例 |
|--------|------|-----|
| `_step` | 各ステップの値 | `T_use`, `a_blow_step` |
| `_cum` | 累積値 | `M_loss_cum`, `M_sink_cum` |
| `_dot` | 時間微分 (rate) | `M_out_dot`, `M_sink_dot` |
| `_avg` | 平均値 | `M_out_dot_avg` |
| `_eff` | 有効値（補正後） | `kappa_eff`, `chi_blow_eff` |
| `_cfg` | 設定由来 | `blowout_enabled_cfg` |
| `_raw` | 補正前の生値 | `ds_dt_raw` |
| `_last` | 直前ステップの値 | `phase_state_last` |
| `_initial` | 初期値 | `kappa_surf_initial` |
| `_resolved` | 解決済み値 | `qpr_table_path_resolved` |
| `_active` | 有効化フラグ | `collisions_active_step` |
| `_enabled` | 設定での有効化 | `blowout_enabled` |
| `_flag` | ブールフラグ | `fast_blowout_flag` |
| `_track` | 履歴リスト | `temperature_track` |

---

## コード例

### 良い命名の例

```python
# 物理量 + 単位
r_m = 0.5 * (cfg.disk.geometry.r_in_RM + cfg.disk.geometry.r_out_RM) * R_MARS  # 軌道半径 [m]
T_M_K = temp_runtime.evaluate(time)     # 火星温度 [K]
Sigma_surf_kg_m2 = sigma_surf           # 面密度 [kg/m²]

# 条件付き評価
beta_at_smin = radiation.beta(s_min, rho, T, Q_pr=qpr)
Q_pr_at_smin = radiation.qpr_lookup(s_min, T)

# 時間微分
dSigma_dt_blowout = outflux_surface
dSigma_dt_sublimation = delta_sigma_sub / dt

# 累積・レート
M_loss_cum += blow_mass_total
M_out_dot = outflux_mass_rate_kg / constants.M_MARS

# フラグ
blowout_enabled = blowout_enabled_cfg and collisions_active
sublimation_active_step = sublimation_active and not liquid_block
```

### 避けるべき命名

```python
# ❌ 略語が不明瞭
x = 0.5              # → beta_threshold = 0.5
tmp = r / R_MARS     # → r_RM = r / constants.R_MARS

# ❌ 単位が不明
t = 2.0              # → t_end_years = 2.0 または t_end_s = ...

# ❌ 意味が曖昧
val = compute_kappa(...)  # → kappa_surf = compute_kappa(...)
flag = True               # → blowout_enabled = True
```
