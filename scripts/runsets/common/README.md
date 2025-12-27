# scripts/runsets/common/base.yml README

この README は `scripts/runsets/common/base.yml` の設定内容を日本語で整理したものです。
各項目について「何を決めるか」「推奨値（=この base.yml の既定）」「選択肢と意味」をまとめています。

## 目的と運用

- runsets の `run_one` / `run_sweep` はこの `base.yml` を読み込み、OS 別の overrides で差分を追加します。
- `configs/base.yml` と内容を一致させる運用です。編集は `configs/base.yml` → 本ファイルへ同期を推奨します。
- I/O（出力先・ストリーミング等）は base.yml に置かず、runsets の overrides で指定します。

## この README の読み方

- **推奨値**は「この base.yml に書かれている既定値」を指します。
- **未指定**の項目はスキーマ既定が使われます。本 README ではその既定値も補足しています。
- 単位は原則 SI（m, s, kg, K）。`*_RM` は火星半径単位です。

## ベース設定の要点（短いまとめ）

- 1D（半径分解）で、火星温度が 2000 K まで冷えるまで積分（温度停止条件）。
- 外部供給は `mode=const` かつ `prod_area_rate_kg_m2_s=0.0` のため **実質ゼロ供給**。
- 昇華は ON（HKL モデル）、放射圧ブローアウトは ON。
- 遮蔽は OFF、相は **閾値（threshold）** モード。
- 放射は火星起源、温度はテーブル入力（自動生成も有効）。

## 主要パラメータ早見表（base.yml 既定）

### 基本スイッチ

| 設定キー | 推奨値 | 意味/選択肢 |
|---|---|---|
| `physics_mode` | `default` | 衝突+シンク併用。`sublimation_only` / `collisions_only` も選択可 |
| `supply.mode` | `const` | 供給方式。`table` / `powerlaw` / `piecewise` も選択可 |
| `sinks.mode` | `sublimation` | 昇華シンク有効。`none` で停止 |
| `blowout.enabled` | `true` | 放射圧ブローアウト有効/無効 |
| `shielding.mode` | `off` | `psitau` / `fixed_tau1` / `table` で遮蔽を有効化 |
| `phase.enabled` | `true` | 固体/蒸気の相分岐を有効化 |
| `radiation.source` | `mars` | `off` で放射圧無効化 |

### 幾何と時間

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `geometry.mode` | `1D` | `0D` は半径平均、`1D` は分解 |
| `geometry.Nr` | `32` | 1D のセル数（`mode=1D` のとき必須） |
| `disk.geometry.r_in_RM` | `1.0` | 内縁（火星半径単位） |
| `disk.geometry.r_out_RM` | `2.7` | 外縁（火星半径単位） |
| `numerics.t_end_until_temperature_K` | `2000.0` | 火星温度がこの値以下で終了 |
| `numerics.t_end_years` | `null` | 温度停止を使うため無効化 |
| `numerics.t_end_orbits` | `null` | 温度停止を使うため無効化 |
| `numerics.dt_init` | `auto` | 初期刻み（秒）。数値指定も可 |
| `numerics.dt_over_t_blow_max` | `0.1` | `dt/t_blow` の警告閾値 |

### サイズ・PSD・初期条件

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `sizes.s_min` | `1.0e-7` | 最小粒径 [m] |
| `sizes.s_max` | `3.0` | 最大粒径 [m] |
| `sizes.n_bins` | `40` | サイズビン数 |
| `psd.alpha` | `1.83` | PSD 傾き |
| `psd.wavy_strength` | `0.0` | “wavy”補正の強さ（0 で無効） |
| `psd.floor.mode` | `none` | `fixed` / `evolve_smin` も可 |
| `initial.mass_total` | `1.0e-7` | 初期質量（火星質量比） |
| `initial.s0_mode` | `melt_lognormal_mixture` | `upper` / `mono` / `melt_truncated_powerlaw` も可 |

### 動力学（励起・速度）

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `dynamics.e0` | `0.5` | 初期離心率 |
| `dynamics.i0` | `0.05` | 初期傾斜角（ラジアン） |
| `dynamics.v_rel_mode` | `pericenter` | 高 e 向き。`ohtsuki` は低 e 向き |
| `dynamics.kernel_ei_mode` | `config` | `wyatt_eq` で平衡 c_eq を解く |
| `dynamics.kernel_H_mode` | `ia` | `fixed` の場合は `H_fixed_over_a` が必要 |
| `dynamics.e_mode` | `fixed` | `e0` を固定値として使う |
| `dynamics.e_profile.mode` | `mars_pericenter` | `e=1-R_MARS/r` を評価（既定） |

### 破砕強度（Q*）

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `qstar.Qs` | `3.5e7` | 強度項係数 |
| `qstar.a_s` | `0.38` | 強度項のサイズ指数 |
| `qstar.B` | `0.3` | 重力項係数 |
| `qstar.b_g` | `1.36` | 重力項のサイズ指数 |
| `qstar.v_ref_kms` | `[1.5, 7.0]` | 参照衝突速度 [km/s] |
| `qstar.coeff_units` | `ba99_cgs` | `si` も可（単位系が変わる） |

### 供給（surface 生成率）

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `supply.enabled` | `true`（未指定） | 供給のマスタースイッチ |
| `supply.const.prod_area_rate_kg_m2_s` | `0.0` | 面積あたり供給率 |
| `supply.const.mu_reference_tau` | `1.0` | 供給スケールの参照 τ（スイープ既定に合わせて固定） |
| `supply.mixing.epsilon_mix` | `1.0` | 混合効率（0〜1） |
| `supply.transport.mode` | `direct` | `deep_mixing` は深部リザーバ経由 |
| `supply.injection.mode` | `powerlaw_bins` | `min_bin` も可 |
| `supply.injection.q` | `3.5` | 供給 PSD の指数 |
| `supply.table.path` | `data/supply_rate.csv` | `mode=table` のとき使用 |

### 昇華・シンク

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `sinks.sub_params.mode` | `hkl` | `logistic` / `hkl_timescale` も可 |
| `sinks.T_sub` | `1300.0` | 昇華判定温度 [K] |
| `sinks.sub_params.alpha_evap` | `0.007` | HKL 蒸発係数 |
| `sinks.sub_params.mu` | `0.0440849` | 分子量 [kg/mol] |
| `sinks.enable_gas_drag` | `false` | gas-poor 既定では無効 |
| `sinks.rp_blowout.enable` | `true` | 放射圧ブローアウトをシンクとして有効 |
| `sinks.hydro_escape.enable` | `false` | 熱的脱出シンクの有効化 |

### 放射・温度ドライバ

| 設定キー | 推奨値 | 意味/備考 |
|---|---|---|
| `radiation.TM_K` | `4000.0` | 火星赤外温度 [K] |
| `radiation.qpr_table_path` | `marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv` | ⟨Q_pr⟩ テーブル |
| `radiation.Q_pr` | 未指定 | 未指定の場合はテーブル優先 |
| `mars_temperature_driver.mode` | `table` | `constant` / `hyodo` も可 |
| `mars_temperature_driver.table.path` | `data/mars_temperature_T4000p0K.csv` | 温度テーブル |
| `mars_temperature_driver.autogenerate.enabled` | `true` | テーブル自動生成を許可 |

## セクション詳細

### scope / physics_mode / process

- **scope**
  - 役割: 解析対象と期間を定義。
  - 推奨値: `region=inner`
  - 選択肢:
    - `region=inner`: 内側ディスクのみ（現状はこの選択のみ）
    - `analysis_years>0`: 解析期間（年、フォールバック用途）
  - **非推奨**: `scope.analysis_years` は base.yml では指定しない方針。終了条件は `numerics.*` で明示する。
- **physics_mode**
  - 役割: 物理モードの大枠を切り替える。
  - 推奨値: `default`
  - 選択肢:
    - `default` / `full`: 衝突 + シンク（昇華等）を併用
    - `sublimation_only`: 昇華のみ（衝突・ブローアウトは無効化）
    - `collisions_only`: 衝突のみ（昇華シンクは無効化）
- **process.state_tagging**
  - 役割: 状態タグ付けの試験フック。
  - 推奨値: `enabled=false`
  - 選択肢: `true`（タグ付けを試験的に有効化）/ `false`

### geometry / disk.geometry / inner_disk_mass / chi_blow

- **geometry**
  - 役割: 0D/1D の空間次元と分割数を指定。
  - 推奨値: `mode=1D`, `Nr=32`
  - 選択肢:
    - `mode=0D`: 半径方向を平均化（高速・簡易）
    - `mode=1D`: 半径方向に分解（詳細）
    - `Nr`: 1D のセル数（`mode=1D` のとき必須）
- **disk.geometry**
  - 役割: 火星半径単位で内外縁と面密度分布を定義。
  - 推奨値: `r_in_RM=1.0`, `r_out_RM=2.7`, `r_profile=uniform`, `p_index=0.0`
  - 選択肢:
    - `r_profile=uniform`: 一様分布（`p_index` は無視）
    - `r_profile=powerlaw`: Σ ∝ r^-p の分布（`p_index` を指定）
- **inner_disk_mass**
  - 役割: 初期面密度の規模を内側ディスク質量から決定。
  - 推奨値: `use_Mmars_ratio=true`, `M_in_ratio=3.0e-5`, `map_to_sigma=analytic`
  - 選択肢:
    - `use_Mmars_ratio=true`: 火星質量比で指定
    - `map_to_sigma=analytic`: 解析式で Σ に変換（現状この選択のみ）
- **chi_blow**
  - 役割: ブローアウト時間スケールの倍率。
  - 推奨値: `auto`
  - 選択肢:
    - `auto`: β と ⟨Q_pr⟩ から自動推定
    - 数値: 指定倍率で固定

### material / sizes / initial

- **material.rho**
  - 役割: 粒子バルク密度（放射圧や破砕に影響）。
  - 推奨値: `3000.0` kg/m³
  - 選択肢: 正の実数（大きいほどブローアウト半径は小さくなる傾向）
- **sizes**
  - 役割: サイズビンの範囲と分解能。
  - 推奨値: `s_min=1.0e-7`, `s_max=3.0`, `n_bins=40`
  - 追加トグル:
    - `evolve_min_size=false`: 最小粒径の動的進化を無効
    - `apply_evolved_min_size=false`: 進化した `s_min` を実効下限に反映しない
    - `dsdt_model` / `dsdt_params`: `evolve_min_size=true` のときに使う進化モデル名と係数
  - 選択肢:
    - `evolve_min_size=true`: `dsdt_model` と `dsdt_params` を使って `s_min` を更新
- **initial**
  - 役割: 初期総質量と初期 PSD の形状。
  - 推奨値: `mass_total=1.0e-7`, `s0_mode=melt_lognormal_mixture`
  - `melt_psd` 推奨値:
    - `f_fine=0.25`, `s_fine=1.0e-4`, `s_meter=1.5`, `width_dex=0.3`
    - `s_cut_condensation=1.0e-6`, `s_min_solid=1.0e-4`, `s_max_solid=3.0`, `alpha_solid=3.5`
  - 選択肢（`s0_mode`）:
    - `upper`: 既定カスケードを維持
    - `mono`: 単一サイズの粒子に集中
    - `melt_lognormal_mixture`: 溶融起源の 2 成分 lognormal 混合
    - `melt_truncated_powerlaw`: 溶融起源の打ち切りパワーロー
  - `melt_psd`: `f_fine/s_fine/s_meter/width_dex` などで混合形状を調整

### dynamics

- 役割: 衝突速度や励起状態（e/i）を決める。
- 推奨値:
  - `e0=0.5`, `i0=0.05`, `t_damp_orbits=20.0`, `f_wake=2.0`
  - `v_rel_mode=pericenter`
  - `kernel_ei_mode=config`, `kernel_H_mode=ia`, `H_factor=1.0`
  - `e_mode=fixed`, `e_profile.mode=mars_pericenter`
  - `i_mode=fixed`
- 選択肢と意味:
  - `v_rel_mode`:
    - `pericenter`: 高 e での相対速度を強めに評価（推奨）
    - `ohtsuki`: 低 e 用の古典式（e≳0.1 では過小評価に注意）
  - `kernel_ei_mode`:
    - `config`: `e0/i0` をそのまま使用
    - `wyatt_eq`: 衝突平衡の `c_eq` を解いて使用
  - `kernel_H_mode`:
    - `ia`: i と a から H を計算（`H_factor` で調整）
    - `fixed`: `H_fixed_over_a` を明示
  - `e_mode`:
    - `fixed`: `e0` を固定値として使う
    - `mars_clearance`: Δr をサンプルして e を導出（`dr_min_m`/`dr_max_m`、`e_profile.mode=off` が必須）
  - `e_profile.mode`:
    - `mars_pericenter`: `e=1-R_MARS/r` を評価（既定）
    - `off`: `e0` を固定値として使う（レガシー）
    - `table`: CSV から e(r) を補間（レガシー）
  - `dr_dist`:
    - `uniform`: Δr を一様分布でサンプル
    - `loguniform`: 対数一様でサンプル
  - `i_mode`:
    - `fixed`: `i0` を固定値として使う
    - `obs_tilt_spread`: 観測傾斜の分布からサンプル（`obs_tilt_deg` と `i_spread_deg`）

### psd / qstar

- **psd**
  - 役割: サイズ分布の基本傾きと“wavy”補正。
  - 推奨値: `alpha=1.83`, `wavy_strength=0.0`, `floor.mode=none`
  - `wavy_strength`: `0` で無効、正の値で波状補正の強さを指定
  - 選択肢:
    - `floor.mode=none`: 固定の下限なし
    - `floor.mode=fixed`: `sizes.s_min` を固定下限に採用
    - `floor.mode=evolve_smin`: `s_min` を動的に押し上げ
- **qstar**
  - 役割: 破砕強度 Q* の係数セット。
  - 推奨値: `Qs=3.5e7`, `a_s=0.38`, `B=0.3`, `b_g=1.36`, `v_ref_kms=[1.5, 7.0]`, `coeff_units=ba99_cgs`
  - 選択肢:
    - `coeff_units=ba99_cgs`: BA99 系の CGS 係数（推奨）
    - `coeff_units=si`: SI で直接入力
    - `override_coeffs=true`: `coeff_table` を使って速度依存の係数を明示

### surface / init_tau1 / optical_depth

- **surface**
  - 役割: 表層の衝突・流出計算を切り替える。
  - 推奨値: `init_policy=none`, `use_tcoll=true`, `freeze_sigma=false`, `collision_solver=smol`
  - 選択肢:
    - `init_policy=none`: 初期 Σ をそのまま使用
    - `init_policy=clip_by_tau1`: τ=1 に合わせて初期 Σ をクリップ
    - `collision_solver=smol`: Smoluchowski を使う（高 e 向き）
    - `collision_solver=surface_ode`: レガシー表層 ODE（低 e 向き）
  - 補足:
    - `sigma_surf_init_override`: 初期 Σ を直接指定（null で無効）
    - `use_tcoll=true`: 衝突寿命スケールを表層更新に反映
    - `freeze_sigma=true`: 表層 Σ を固定し時間発展を止める
- **init_tau1**
  - 役割: 初期状態を τ≈1 に揃える補助。
  - 推奨値: `enabled=false`, `scale_to_tau1=false`
  - 選択肢:
    - `enabled=true`: Σ を τ=1 相当に置き換え
    - `scale_to_tau1=true`: τ=1 上限に合わせて Σ をスケール
- **optical_depth**
  - 役割: τ の目標値と停止条件を管理。
  - 推奨値: `tau0_target=1.0`, `tau_stop=2.302585092994046`, `tau_stop_tol=1e-06`, `tau_field=tau_los`
  - 選択肢:
    - `tau_field=tau_los`: 現状は LOS のみ
    - `tau_stop`: これを超えると計算停止（`tau_stop_tol` で許容幅）

### supply

- 役割: 外部供給（生成率）の与え方を指定。
- 推奨値:
  - `enabled=true`（未指定だが既定）
  - `mode=const`, `const.prod_area_rate_kg_m2_s=0.0`（実質供給ゼロ）
  - `mixing.epsilon_mix=1.0`, `feedback/reservoir/temperature.enabled=false`
  - `transport.mode=direct`, `injection.mode=powerlaw_bins`, `injection.q=3.5`
  - `table.path=data/supply_rate.csv`, `table.interp=linear`（`mode=table` 用の予備設定）
- 選択肢と意味:
  - `enabled`:
    - `true`: 供給を有効（推奨）
    - `false`: 供給を強制ゼロ
  - `mode`:
    - `const`: 一定供給（推奨）
    - `table`: CSV テーブルで時間変化を与える
    - `powerlaw`: 指定の指数則で時間変化
    - `piecewise`: 複数区間をつなぐ（高度）
  - `const` パラメータ:
    - `prod_area_rate_kg_m2_s`: 面積あたり供給率
    - `mu_orbit10pct`, `mu_reference_tau`, `orbit_fraction_at_mu1`: τ=1 基準の供給スケール
  - `mixing.epsilon_mix`:
    - 0〜1 の混合効率（1 は全量が表層へ）
  - `headroom_policy`（未指定なら既定 `clip`）:
    - `clip`: τ=1 の余裕分で供給を抑制
    - `spill`: 供給してから超過分を削除
  - `transport.mode`:
    - `direct`: 供給を表層へ直接投入（推奨）
    - `deep_mixing`: 深部リザーバを経由（`t_mix_orbits` が必要）
  - `transport.headroom_gate`（未指定なら既定 `hard`）:
    - `hard`: τ=1 の余裕が無い場合は強制的にゼロ供給
    - `soft`: 余裕に応じて滑らかに抑制（将来拡張向け）
  - `injection.mode`:
    - `min_bin`: 最小ビンに集中
    - `powerlaw_bins`: サイズ範囲に分配（推奨）
  - `injection.velocity.mode`（未指定なら既定 `inherit`）:
    - `inherit`: ベースの e/i を継承
    - `fixed_ei`: `e_inj`/`i_inj` を固定指定
    - `factor`: `vrel_factor` で相対速度を倍率調整
  - `feedback/reservoir/temperature`:
    - いずれも `enabled=false` が推奨（非標準・感度試験向け）

### sinks

- 役割: 昇華・ガス抵抗・流出などの追加損失。
- 推奨値:
  - `mode=sublimation`, `enable_sublimation=true`, `sublimation_location=smol`
  - `T_sub=1300.0`
  - `enable_gas_drag=false`, `rho_g=0.0`, `rp_blowout.enable=true`, `hydro_escape.enable=false`
  - `sub_params.mode=hkl`（HKL）
  - `sub_params` 推奨値（HKL）:
    - `alpha_evap=0.007`, `mu=0.0440849`
    - `A=13.613`, `B=17850.0`
    - `enable_liquid_branch=true`, `psat_liquid_switch_K=1900.0`
    - `A_liq=13.203`, `B_liq=25898.9`
    - `dT=50.0`, `eta_instant=0.1`, `P_gas=0.0`, `mass_conserving=true`
- 選択肢と意味:
  - `mode`:
    - `sublimation`: 昇華シンクを有効化（推奨）
    - `none`: すべてのシンクを停止
  - `sublimation_location`:
    - `smol`: Smol 系に統合（推奨）
    - `surface`: 表層 ODE にのみ適用
    - `both`: 両方に適用
  - `sub_params.mode`:
    - `hkl`: Hertz-Knudsen-Langmuir（推奨）
    - `hkl_timescale`: HKL を時定数形式で扱う
    - `logistic`: 単純ロジスティック（簡易）
  - `psat_model`（未指定は `auto`）:
    - `auto`: HKL の既定に従う
    - `clausius`: Clausius-Clapeyron 係数
    - `tabulated`: 外部テーブルを参照
  - `enable_gas_drag`:
    - `true`: ガス抵抗を有効化（gas-rich 想定）
    - `false`: gas-poor 前提で無効化（推奨）

### radiation / shielding / blowout / phase

- **radiation**
  - 役割: 放射圧と温度入力の定義。
  - 推奨値:
    - `source=mars`, `use_mars_rp=true`, `use_solar_rp=false`
    - `freeze_kappa=false`
    - `TM_K=4000.0`
    - `qpr_table_path=marsdisk/io/data/qpr_planck_sio2_abbas_calibrated_lowT.csv`
    - `Q_pr` は未指定（テーブルを優先）
    - `mars_temperature_driver.enabled=true`, `mode=table`, `table.path=data/mars_temperature_T4000p0K.csv`
    - `mars_temperature_driver.table`: `time_unit=day`, `column_time=time_day`, `column_temperature=T_K`
    - `mars_temperature_driver.autogenerate`:
      - `enabled=true`, `output_dir=data`, `dt_hours=1.0`
      - `min_years=2.0`, `time_margin_years=0.5`
      - `time_unit=day`, `column_time=time_day`, `column_temperature=T_K`
  - 選択肢:
    - `source=mars` / `off`: 放射圧の有無
    - `Q_pr`: 固定値を指定（テーブルを使わない場合）
    - `mars_temperature_driver.mode`:
      - `constant`: 一定温度
      - `table`: テーブル補間（推奨）
      - `hyodo`: Hyodo 近似
    - `autogenerate.enabled=true`: テーブルが無い場合に自動生成
    - `tau_gate.enable=true`: τ が大きいときに放射圧を抑制
- **shielding**
  - 役割: 自遮蔽 Φ(τ) の扱い。
  - 推奨値: `mode=off`, `table_path=marsdisk/io/data/phi.csv`
  - 選択肢:
    - `off`: 遮蔽なし（推奨）
    - `psitau`: Φ(τ) テーブルを用いて遮蔽
    - `fixed_tau1`: τ を固定値にクランプ
    - `table`: `psitau` のエイリアス
  - 補足（未指定の既定）:
    - `los_geometry.mode=aspect_ratio_factor`
    - `los_geometry.h_over_r=1.0`, `los_geometry.path_multiplier=1.0`
- **blowout**
  - 役割: 放射圧ブローアウトの対象と範囲。
  - 推奨値: `enabled=true`, `target_phase=solid_only`, `layer=surface_tau_le_1`, `gate_mode=none`（未指定だが既定）
  - 選択肢:
    - `target_phase=solid_only`: 固体のみを対象（推奨）
    - `target_phase=any`: 気相も含める
    - `layer=surface_tau_le_1`: τ≤1 表層のみ
    - `layer=full_surface`: 表層全体
    - `gate_mode`: 他の損失が速い場合に抑制（`none`/`sublimation_competition`/`collision_competition`）
- **phase**
  - 役割: 固体/蒸気の分岐。
  - 推奨値: `enabled=true`, `source=threshold`, `temperature_input=particle`
  - `entrypoint`: `siO2_disk_cooling.siO2_cooling_map:lookup_phase_state`（`source=map` のとき使用）
  - `tau_field=los`, `q_abs_mean=0.4`
  - `thresholds` 推奨値: `T_condense_K=1700.0`, `T_vaporize_K=2000.0`, `P_ref_bar=1.0`, `tau_ref=1.0`
  - 選択肢:
    - `source=threshold`: 温度閾値で分岐（推奨）
    - `source=map`: 外部マップを参照（`entrypoint` 必須）
    - `temperature_input=mars_surface`: 火星表面温度
    - `temperature_input=particle`: 粒子平衡温度（推奨）
    - `thresholds`: `T_condense_K`/`T_vaporize_K` で境界を設定

### numerics / diagnostics

- **numerics**
  - 役割: 積分条件と停止条件。
  - 推奨値:
    - `t_end_until_temperature_K=2000.0`, `t_end_years=null`, `t_end_orbits=null`
    - `t_end_temperature_margin_years=0.0`
    - `dt_init=auto`, `safety=0.1`
    - `atol=1.0e-10`, `rtol=1.0e-6`
    - `stop_on_blowout_below_smin=true`
    - `eval_per_step=true`, `orbit_rollup=true`, `dt_over_t_blow_max=0.1`
    - `dt_min_tcoll_ratio` は未指定（既定 `0.5`）
  - 選択肢:
    - `t_end_years` / `t_end_orbits`: 温度停止を使わない場合の終了時刻
    - `t_end_until_temperature_K`: 温度が下がるまで継続
    - `dt_init`: 数値指定（秒）または `auto`
    - `dt_over_t_blow_max`: `dt/t_blow` の警告閾値（未指定で無効）
  - 補足:
    - `stop_on_blowout_below_smin=true`: ブローアウト下限が `sizes.s_min` を下回ると早期停止
- **diagnostics**
  - 役割: 追加診断の出力制御。
  - 推奨値: `extended_diagnostics.enable=false`
  - 選択肢:
    - `extended_diagnostics.enable=true`: 追加列の出力を許可
    - `energy_bookkeeping.enabled=true`: 衝突エネルギー診断を出力（base.yml では未指定、既定 false）

## 変更時の指針

- 研究条件や出力先は `study_*.yml` や runsets の overrides で上書きする前提です。
- base.yml の構造を変更した場合は `configs/base.yml` と揃える形で同期してください。
