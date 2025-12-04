# marsshearingsheet クイックガイド

> **For AI Agents**: Please refer to [`analysis/AI_USAGE.md`](analysis/AI_USAGE.md) for detailed protocols regarding reference management (`UNKNOWN_REF_REQUESTS`), documentation standards, and automated verification workflows.

## ガス希薄（gas‑poor）前提

本モデルは **火星ロッシュ限界内のガスに乏しい衝突起源ダスト円盤**を解析対象としています。溶融主体で蒸気成分が≲数%に留まるという報告（Hyodo et al. 2017; 2018）と、Phobos/Deimos を残すには低質量・低ガス円盤が必要だという Canup & Salmon (2018) を踏まえ、標準ケースでは **Takeuchi & Lin (2003)** が仮定するガスリッチ表層アウトフローを採用しません（`ALLOW_TL2003=false` が既定）。gas-rich 条件を調べる場合のみ、利用者責任で明示的に切り替えてください。参考枠組みとして Strubbe & Chiang (2006)、Kuramoto (2024) を推奨します。

## 1. モデル概要

- `marsdisk.run.run_zero_d` が 0D（半径無次元）ダスト円盤を時間発展させ、内部破砕で生成される sub-blow-out 粒子供給と表層の放射圧剥離を連成します（式 C1–C4, P1, F1–F2, R1–R3, S0–S1、analysis/equations.md を参照）。
- 主要モジュール  
  - `marsdisk/physics/radiation.py`：平均 <big><big>$`\langle Q_{\rm pr}\rangle`$</big></big>、<big><big>$`\beta`$</big></big>、<big><big>$`a_{\rm blow}`$</big></big>。  
  - `marsdisk/physics/psd.py`：三勾配 + “wavy” 補正付き PSD と不透明度（既定の `configs/base.yml` では `wavy_strength=0.0` で平滑化）。  
  - `marsdisk/physics/shielding.py`：多層 RT 由来の自遮蔽係数 <big><big>$`\Phi(\tau,\omega_0,g)`$</big></big>。  
  - `marsdisk/physics/collide.py`, `smol.py`：Smoluchowski IMEX-BDF(1) による破砕と質量保存検査。  
  - `marsdisk/physics/surface.py`：Strubbe–Chiang（Wyatt 2008 レビュー）スケールの衝突寿命と吹き飛び・追加シンクを含む表層 ODE。  
  - `marsdisk/io/writer.py`：Parquet / JSON / CSV への出力。
- 再現性のため `random`, `numpy.random`, `numpy.random.default_rng` の全 RNG を同一シードで初期化します（analysis/overview.md §9）。

詳細な数式・導出・ブロック図は `analysis/overview.md` と `analysis/equations.md` を参照してください。

### 放射条件とプランク平均 ⟨Q_pr⟩

- 本コードは **プランク平均の放射圧効率** ⟨Q_pr⟩ を放射源（火星表面）の黒体スペクトルで重み付けした無次元係数として扱います。定義は  
  $$
  \langle Q_{\rm pr}\rangle(T_M) = \frac{\int_0^\infty Q_{\rm pr}(\lambda)\,B_\lambda(T_M)\,{\rm d}\lambda}{\int_0^\infty B_\lambda(T_M)\,{\rm d}\lambda},
  $$
  であり、波長依存の吸収・散乱（$Q_{\rm pr}(\lambda)=Q_{\rm abs}+ (1-g)Q_{\rm sca}$）を火星温度 $T_M$ の Planck 関数 $B_\lambda$ で平均化します。
- 実行時は必ず `radiation.qpr_table_path`（Planck 平均表）を指定するか、`radiation.Q_pr` に ⟨Q_pr⟩ の定数値を与えてください。テーブルは `marsdisk/ops/make_qpr_table.py` または観測／Mie 解析で生成した CSV/NPZ を `marsdisk.io.tables.load_qpr_table` が読み込み、`marsdisk/physics/radiation.py` が補間します。
- β や blow-out サイズ、滞在時間係数 `chi_blow`、PSD 下限 `s_min` など、放射に依存する全量はこの ⟨Q_pr⟩ を通じて決まり、別個の吸収効率 $Q_{\rm abs}$ を直接入力する経路はありません。必要なら Mie 計算側で $Q_{\rm abs}, Q_{\rm sca}, g$ を評価し、Planck 重み付きの ⟨Q_pr⟩ をテーブルとして渡してください。

### 全モードON実行フロー（gas-poor 無効）

> **注意**: AGENTS.md §4 にある通り、本プロジェクトは gas-poor を既定とし TL2003 表層方程式の使用を抑制しています。ここでは感度試験として `ALLOW_TL2003=true` などでガードを明示的に外し、昇華・ガス抗力・遮蔽・“wavy” PSD・Strubbe–Chiang（Wyatt 2008）衝突・HKL 侵食など **全スイッチを有効化した状態**（ただし gas-poor 簡略化は適用しない）で 0D シミュレーションを走らせる手順と式の対応を記述します。

```bash
ALLOW_TL2003=true \
python -m marsdisk.run --config configs/base.yml \
  --override radiation.qpr_table_path=data/qpr_table.csv \
  --override shielding.phi_table=data/phi_multiscatter.csv \
  --override numerics.eval_per_step=true \
  --override io.correct_fast_blowout=true \
  --override sinks.mode=sublimation \
  --override sinks.enable_sublimation=true \
  --override sinks.enable_gas_drag=true \
  --override sinks.sub_params.mode=hkl \
  --override sinks.sub_params.psat_model=clausius \
  --override sinks.sub_params.P_gas=5.0 \
  --override chi_blow=auto
```

1. **放射・軌道前処理**
   - 代表半径から <big><big>$`v_K`$</big></big> (E.001) と <big><big>$`\Omega`$</big></big> (E.002) を取得し、軌道力学の基準量を定めます。
   - `radiation.qpr_table_path` で補間した <big><big>$`⟨Q_{\rm pr}⟩`$</big></big> から <big><big>$`\beta`$</big></big> (E.013) と <big><big>$`s_{\rm blow}`$</big></big> (E.014) を評価します。
   - `chi_blow=auto` を指定すると <big><big>$`\beta`$</big></big> と <big><big>$`⟨Q_{\rm pr}⟩`$</big></big> から滞在時間係数を推定し、<big><big>$`s_{\min,\rm eff}`$</big></big> を自動更新します。
   - **キー式**  
     > <big><big>$`t_{\rm blow}=1/\Omega`$</big></big>  
     > <big><big>$`s_{\min,\rm eff} = \max(s_{\min,\rm cfg}, s_{\rm blow})`$</big></big>
2. **自遮蔽と表層初期化**
   - `shielding.phi_table` を読み込み、多層 RT 由来の <big><big>$`\Phi(\tau,w_0,g)`$</big></big> を補間 (E.017) します。
   - 得られた係数で <big><big>$`\kappa_{\rm eff}`$</big></big> (E.015) と <big><big>$`\Sigma_{\tau=1}`$</big></big> (E.016, E.031) を計算し、`surface.init_policy="clip_by_tau1"` で表層をクリップします。
   - **キー式**  
     > <big><big>$`\kappa_{\rm eff}=\Phi\kappa_{\rm surf}`$</big></big>  
     > <big><big>$`\Sigma_{\tau=1}=1/\kappa_{\rm eff}`$</big></big>
3. **PSD と破砕供給**
   - 内側質量は <big><big>$`\Sigma(r)`$</big></big> (E.023) から初期化し、`psd.wavy_strength>0` なら “wavy” 補正を適用します。
   - Wyatt 衝突速度 <big><big>$`v_{ij}`$</big></big> (E.020) を用いて <big><big>$`C_{ij}`$</big></big> (E.024) と <big><big>$`Q_D^*`$</big></big> (E.026) を組み立て、<big><big>$`\dot{m}_{<a_{\rm blow}}`$</big></big> (E.035) を得ます。
   - **キー式**  
     > <big><big>$`v_{ij}=v_K\sqrt{1.25 e_i^2 + i_j^2}`$</big></big>  
     > <big><big>$`\dot{m}_{<a_{\rm blow}} = \sum_{ij} C_{ij}\,m_{ij}`$</big></big>（E.035 の要約）
4. **Smoluchowski IMEX**
   - `numerics.eval_per_step=true` では毎ステップ <big><big>$`\Lambda_i=\sum_j C_{ij}`$</big></big> を再評価し、IMEX-BDF1 更新 (E.010) を適用します。
   - Strubbe–Chiang スケール <big><big>$`t_{\rm coll}`$</big></big> (E.006) を loss に加え、<big><big>$`\epsilon_{\rm mass}`$</big></big> (E.011) が閾値を超えた場合は <big><big>$`\Delta t`$</big></big> を半減します。
   - **キー式**  
     > <big><big>$`t_{\rm coll}=1/(\Omega\tau_{\perp})`$</big></big>  
     > <big><big>$`\Delta t \le 0.1\,\min(t_{{\rm coll},k})`$</big></big>
5. **TL2003 表層 IMEX**
   - gas-poor ガードを外すと Takeuchi & Lin (2003) の薄いガス層 ODE (E.007) をそのまま解きます。
   - Strubbe–Chiang 衝突寿命と追加 sink から <big><big>$`\lambda`$</big></big> を組み、<big><big>$`\Sigma_{\tau=1}`$</big></big> でクリップした後に <big><big>$`\dot{M}_{\rm out}`$</big></big> を記録します。
   - **キー式**  
     > <big><big>$`\Sigma^{n+1}=\dfrac{\Sigma^n+\Delta t\,\dot{\Sigma}_{\rm prod}}{1+\Delta t\,\lambda}`$</big></big>  
     > <big><big>$`\dot{M}_{\rm out} = \Sigma^{n+1}\Omega`$</big></big>
6. **昇華・ガス抗力シンク**
   - `sinks.enable_sublimation=true` と `sinks.sub_params.mode="hkl"` で HKL フラックス <big><big>$`J(T)`$</big></big> (E.018) を評価し、<big><big>$`t_{\rm sink}`$</big></big> を構成します。
   - `enable_gas_drag=true` かつ <big><big>$`\rho_g>0`$</big></big> ならガス抗力タイムスケールを計算し、最小値を `step_surface_density_S1` へ渡します。
   - **キー式**  
     > <big><big>$`t_{\rm ref}=1/\Omega`$</big></big>  
     > <big><big>$`\Phi_{\rm sink}=\Sigma^{n+1}/t_{\rm sink}`$</big></big>
7. **出力と検証**
   - `out/series/*.parquet` に `prod_subblow_area_rate`, `M_out_dot`, `mass_lost_by_sinks` などを逐次保存します。
   - `out/checks/mass_budget.csv` で <big><big>$`\epsilon_{\rm mass}`$</big></big> を 0.5% 未満に監視し、2 年積分後の <big><big>$`M_{\rm loss}`$</big></big> を `out/summary.json` に記録します。
   - **キー式**  
     > <big><big>$`\epsilon_{\rm mass} = \left|1 - \dfrac{M_{\rm tracked}}{M_{\rm init}-M_{\rm loss}}\right|`$</big></big>  
     > <big><big>$`M_{\rm loss} = \int_0^{2\,{\rm yr}} \dot{M}_{\rm out}\,dt`$</big></big>

## 2. クイックスタート

```bash
python -m venv .venv && source .venv/bin/activate  # 任意の仮想環境
pip install -r requirements.txt                    # ない場合は numpy pandas pyarrow ruamel.yaml pydantic 等を個別導入

python -m marsdisk.run --config configs/base.yml   # 0D シミュレーション実行（sinks.mode=none, wavy_strength=0.0 が既定）
# 昇華・ガス抗力などの追加シンクを試したい場合
python -m marsdisk.run --config configs/base.yml --sinks sublimation --set sinks.enable_sublimation=true
# wavy 補正を有効化したい場合
python -m marsdisk.run --config configs/base.yml --override psd.wavy_strength=0.2
```

### 生成物（標準設定）

| 出力 | 内容 |
| --- | --- |
| `out/series/run.parquet` | 時系列（`prod_subblow_area_rate`, `M_out_dot`, `tau`, `t_blow`, `T_M_used`, `rad_flux_Mars`, `Q_pr_at_smin`, `beta_at_smin`, `a_blow_at_smin` など） |
| `out/summary.json` | `M_loss`, `M_loss_from_sinks`, `M_loss_from_sublimation`, `s_blow_m`, `beta_at_smin*`, `s_min_effective[m]`, `T_M_source`, `T_M_used[K]` 等を含むサマリ |
| `out/checks/mass_budget.csv` | ステップ毎の質量保存ログ（許容誤差 0.5% 未満） |
| `out/run_config.json` | 使用した式、定数、シード、`init_ei` ブロック（`dynamics.e_mode/i_mode`、<big><big>$`\Delta r`$</big></big>, <big><big>$`e_0`$</big></big>, <big><big>$`i_0`$</big></big>、`e_formula_SI`, `a_m_source` など） |

`series/run.parquet` にはタイムステップ毎の高速ブローアウト診断が含まれます。主な列は以下の通りです。

- `dt_over_t_blow` = <big><big>$`\Delta t / t_{\rm blow}`$</big></big>（無次元）。
- `fast_blowout_factor` = <big><big>$`1 - \exp(-\Delta t / t_{\rm blow})`$</big></big>（面密度に対する有効損失分率）。
- `fast_blowout_flag_gt3` / `fast_blowout_flag_gt10`：<big><big>$`\Delta t / t_{\rm blow}`$</big></big> が 3・10 を超えたステップで `true`。
- `fast_blowout_corrected`：`io.correct_fast_blowout=true` のときだけ `true` になり、補正の有無を明示します。
- `dSigma_dt_blowout`,`dSigma_dt_sinks`,`dSigma_dt_total`（kg m⁻² s⁻¹）と、惑星質量スケールに平均化した `M_out_dot_avg`,`M_sink_dot_avg`,`dM_dt_surface_total_avg`。
- `n_substeps`：高速ブローアウトをサブステップ分割した場合の分割数（既定 1）。
- 温度ドライバの列：`T_M_used`（K）、`rad_flux_Mars`（=σ_SB T^4）、`Q_pr_at_smin`、`beta_at_smin`、`a_blow_at_smin` が追加され、火星放射の時系列が追跡できます。

`chi_blow` は YAML のトップレベルで設定でき、スカラー値を与えると従来通り `t_{\rm blow}` = <big><big>$`\chi_{\rm blow} / \Omega`$</big></big> を使用します。`"auto"` を指定すると <big><big>$`\beta`$</big></big> と <big><big>$`⟨Q_{\rm pr}⟩`$</big></big> から 0.5–2.0 の範囲で自動推定した係数を採用し、その値を `chi_blow_eff` としてタイムシリーズとサマリに記録します。

火星温度は優先順位付きのソースで決定されます。`radiation.TM_K` が明示されていれば従来通りその定数値を使い、未設定かつ `radiation.mars_temperature_driver.enabled=true` の場合は温度ドライバ（`mode="constant"` / `"table"`）から時間依存の `T_M(t)` を取得します。いずれも無効なら `temps.T_M` がフォールバックとして採用されます。採用結果は `summary.json` の `T_M_source` / `temperature_driver` に、時系列は `series/run.parquet` の `T_M_used`・`rad_flux_Mars`・`Q_pr_at_smin`・`beta_at_smin`・`a_blow_at_smin` に記録され、`summary.json` には最小値/中央値/最大値が追記されます。Q_pr/Phi テーブルは `analysis/AI_USAGE.md` に従って `marsdisk/io/tables.py` 経由で読み込み、欠損時は警告付きの解析近似へフォールバックします。

## 3. 設定 YAML の要点

`configs/base.yml` は 0D 実行に必要な最小ブロックを含みます。各セクションの主要項目と挙動は以下の通りです（詳細は `analysis/AI_USAGE.md`）。

| セクション | 主なフィールド | 備考 |
| --- | --- | --- |
| `geometry` | `mode="0D"`, `r` | 代表半径（m）。`e_mode="mars_clearance"` を使う場合は必須。 |
| `material` | `rho` | 粒子バルク密度。 |
| `temps` / `radiation` | `T_M`, `TM_K`, `mars_temperature_driver.*`, `Q_pr`, `qpr_table` | `radiation.TM_K` → `radiation.mars_temperature_driver` → `temps.T_M` の順で温度ソースを解決。Q_pr はテーブル or スカラーで上書き可能。 |
| `sizes` | `s_min`, `s_max`, `n_bins` | 対数ビン数は 30–60 推奨（既定 40）。 |
| `initial` | `mass_total`, `s0_mode` | 初期 PSD モードは `"upper"` / `"mono"`。 |
| `dynamics` | `e0`, `i0`, `t_damp_orbits`, `f_wake` | **既定モードは `e_mode="fixed"` / `i_mode="fixed"`**。モードを指定しなければ入力スカラー `e0` / `i0` がそのまま初期値となります。`e_mode="mars_clearance"` を選ぶと <big><big>$`\Delta r`$</big></big>（m）を `dr_min_m` / `dr_max_m` からサンプリングし <big><big>$`e = 1 - (R_{\rm MARS}+\Delta r)/a`$</big></big> を適用、`i_mode="obs_tilt_spread"` では `obs_tilt_deg ± i_spread_deg`（度）をラジアンに変換して一様乱数サンプリングします。`rng_seed` を指定すると再現性を確保できます。 |
| `psd` | `alpha`, `wavy_strength` | 三勾配 PSD と “wavy” 補正の強さ。`configs/base.yml` では wavy を無効化するため `0.0` を既定とし、必要に応じて CLI で上書き。 |
| `qstar` | `Qs`, `a_s`, `B`, `b_g`, `v_ref_kms` | Leinhardt & Stewart (2012) の補間式を採用。 |
| `surface` | `init_policy`, `use_tcoll` | Strubbe–Chiang 衝突寿命の導入や <big><big>$`\Sigma_{\tau=1}`$</big></big> のクリップを制御。 |
| `supply` | `mode`, `const` / `powerlaw` / `table` / `piecewise` | 表層供給の時間依存・空間構造。 |
| `sinks` | `mode`, `enable_sublimation`, `enable_gas_drag`, `sub_params.*`, `rho_g` | 昇華・ガス抗力など追加シンク。`mode="none"` で一括無効。 |
| `shielding` | `phi_table` | Φ テーブル経由で自遮蔽係数を補正。 |
| `phase` | `enabled`, `source`, `entrypoint`, `extra_kwargs` | バルク相判定を外部エントリポイントで切替可能。既定は `siO2_disk_cooling.siO2_cooling_map:lookup_phase_state` を用いた SiO₂ 冷却マップ。 |
| `numerics` | `t_end_years`, `dt_init`, `safety`, `atol`, `rtol` | IMEX-BDF(1) のタイムステップ制御 (<big><big>$`\Delta t \le 0.1 \times \min t_{\rm coll,k}`$</big></big> が収束条件)。 |
| `io` | `outdir` | 出力ディレクトリ。 |

サンプルとして `analysis/overview.md` の YAML スニペットや `configs/base.yml` / `configs/sweep_example.yml` を参照してください。

#### 火星温度ドライバ設定例

- **既存互換 (constant)** — `configs/base.yml` では `radiation.mars_temperature_driver.enabled=false` のまま `mode="constant"` と `constant.value_K` を与えており、デフォルトでは従来の定数温度と完全一致します。
- **テーブル駆動 (table)** — `configs/mars_temperature_driver_table.yml` は `mars_temperature_driver.enabled=true` かつ `mode="table"` を指定し、`data/mars_temperature_table_example.csv` (`time_day`, `T_K`) を線形補間して 2 年の窓を駆動します。外挿モードは `extrapolation: "hold"`（端点保持）または `"error"`（範囲外で停止）から選べます。

CLI からは `--override radiation.mars_temperature_driver.enabled=true` のようにドット記法で上書きできます（`table.path` や `table.time_unit` も同様）。

### RNG とプロヴェナンス

- `dynamics.rng_seed` を省略した場合は既定シード（`marsdisk/run.py` 内定義）が適用され、`run_config.json` の `init_ei.seed_used` に記録されます。
- `run_config.json` には式、使用定数、Git 情報、`e_formula_SI`（単位説明付き）を埋め込み、分析再現性を担保します。

## 4. 補助スクリプトの配置

- 可視化ユーティリティは `tools/` 配下に集約しました（`tools/plotting.py`、`tools/diagnostics/` など）。
- ドキュメント同期や Q_pr テーブル生成などの開発運用向けコードは `marsdisk/ops/` に移動し、`python -m marsdisk.ops.doc_sync_agent --help` などで呼び出せます。既存の `python -m tools.doc_sync_agent` も互換ラッパーとして動作します。
- PSD 数値実験の試験的スクリプトは `prototypes/psd/` へ分離しました。`tools/psd_*` は新しい配置へのフォワーダとして残しており、既存ワークフローから段階的に切り替え可能です。
- 可視化ツールの詳細は `analysis/tools/visualizations.md`（スクリプト一覧）および `tools/AGENTS.md`（運用規則）を参照してください。

### スクリプトとツールの役割
- `scripts/` はエージェント／CI の公式エントリポイントを置く場所です。`python scripts/<name>.py` で直接実行するスイープ・バッチ・CLI はここに集約し、各ファイルの詳細は `scripts/README.md` に記載します。
- `tools/` は可視化・解析補助・互換ラッパーなどを提供するユーティリティ置き場です。他スクリプトから import される部品や旧 CLI を残す場合はこちらに配置し、徐々に scripts 側へ機能を移管する方針です。

## 5. 可視化とバッチ実行

`scripts/sweep_heatmaps.py` は感度掃引用に YAML を自動生成し、複数ケースを実行して `results/*.csv` と `sweeps/<map>/<case_id>/out/` へ集計します。  
`scripts/plot_heatmaps.py` は `results/map*.csv` からヒートマップ（例：`total_mass_lost_Mmars`, `beta_at_smin`）を描画し `figures/` へ保存します。  
使い方は各スクリプトの `--help` と `analysis/run-recipes.md` を参照してください。

## 6. テスト

ユニットテストは `pytest` で実行します。

```bash
pytest
```

- Strubbe–Chiang 衝突寿命スケーリング、ブローアウト即時消滅による “wavy” PSD、IMEX 安定性などのテストが `marsdisk/tests/` に用意されています。
- RNG 駆動モードの再現性と出力レンジを確認する `test_dynamics_sampling.py` も含まれます。

## 7. 参考ドキュメント

- `analysis/overview.md`：アーキテクチャ／物理式／データフローの詳細。  
- `analysis/AI_USAGE.md`：YAML 設定のポイントと I/O 契約。  
- `analysis/run-recipes.md`：ベンチマークや掃引ジョブの運用ノウハウ。  
- `analysis/sinks_callgraph.md`：追加シンクの流れと依存関係。  
- `analysis/equations.md`：採用方程式と文献まとめ。  
- `analysis/CHANGELOG.md`：リリースノートと変更履歴（analysis 配下に統合）。  

必要に応じて `analysis/` ディレクトリを `python -m tools.doc_sync_agent --all --write`（Makefile では `make analysis-sync`）で同期し、コード変更後の参照情報を更新してください。その直後に `make analysis-doc-tests` を実行すると `tools/run_analysis_doc_tests.py` が `pytest tests/test_analysis_* -q` を一括実行し、合格率を ASCII バーで可視化します。Codex/開発者ともに「DocSync → ドキュメントテスト」の順でまとめて記録するのが標準手順で、チャットで「analysisファイルを更新してください」と頼むだけで `make analysis-update`（両コマンドを連続実行）を走らせられます。

## 8. デバッグとトラブルシュート

- **温度掃引が変化しない場合**  
  `radiation.TM_K` が設定されたまま `temps.T_M` を変えても、上書きされた定数温度が使われるため結果が固定されます。`summary.json` の `T_M_source` を確認し、掃引時は `radiation.TM_K` を `null` にするか CLI で未指定にしてください。
- **昇華シンクの可視化**  
  YAML で `io.debug_sinks: true` を指定すると `out/<case>/debug/sinks_trace.jsonl` が生成され、各ステップの `t_sink`, `dominant_sink`, `total_sink_dm_dt_kg_s`, `cum_sublimation_mass_kg` などを追跡できます。ロギングを無効に戻すには `false` を指定します。
- **RNG の再現性**  
  CLI / YAML の同一設定で再実行しても、`dynamics.rng_seed` が一致していれば `summary.json` / `series/run.parquet` の統計量は一致します。シードを省略した場合は幾何条件からの自動決定値（`run_config.json` の `rng_seed_expr` を参照）が使われます。

@-- BEGIN:SIO2_DISK_COOLING_README --
### SiO₂ disk cooling（距離×時間マップ）
SiO₂ 粒子の温度がガラス転移・液相終端に到達する時刻を距離と時間のマップとして評価するシミュレーションです。
- モデル: $T_{\mathrm{Mars}}(t)=(T_0^{-3}+3\sigma t/(D\rho c_p))^{-1/3}$, $T_p(r,t)=T_{\mathrm{Mars}}(t)\sqrt{R_{\mathrm{Mars}}/(2r)}$
- 実行方法: `python siO2_disk_cooling/siO2_cooling_map.py`
- 生成物: `siO2_disk_cooling/outputs/*.png`, `siO2_disk_cooling/outputs/*.csv`

| T0 [K] | T_p \le T_{glass} 到達範囲 | 代表時刻 | T_p \le T_{liquidus} 到達範囲 | 代表時刻 |
| --- | --- | --- | --- | --- |
| 6000 | 1.955–2.400 R_Mars | 1.657 年 | 1.080–2.400 R_Mars | 0.841 年 |
| 4000 | 1.665–2.400 R_Mars | 1.252 年 | 1.000–2.400 R_Mars | 0.265 年 |
| 2000 | 1.000–2.400 R_Mars | 0.000 年 | 1.000–2.400 R_Mars | 0.000 年 |
@-- END:SIO2_DISK_COOLING_README --
