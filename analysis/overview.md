## 1. 目的と範囲
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。
- 0D円盤で破砕生成による`prod_subblow_area_rate`と表層剥離による`M_out_dot`を時間発展させ、累積損失`M_loss_cum`を記録する。[marsdisk/schema.py#Geometry [L19–L26]][marsdisk/run.py#run_zero_d [L273–L1005]]
- CLI経由で呼ばれる`run_zero_d`がYAMLを読み、放射・遮蔽テーブルやPSDを初期化したうえで表層面密度を積分し、出力に書き出す。[marsdisk/run.py#run_zero_d [L273–L1005]]
- 将来の半径1D拡張に備えてケプラー格子と粘性拡散の骨組みを保持するが、現行は0D主導である。[marsdisk/grid.py#omega_kepler [L17–L31]][marsdisk/physics/viscosity.py#step_viscous_diffusion_C5 [L51–L134]]

## 2. 全体アーキテクチャ
- CLI層は`argparse`で`--config`を受け取り`load_config`を通じて設定を読み込む。[marsdisk/run.py#run_zero_d [L273–L1005]]
- 設定層はPydanticモデルで幾何、物性、数値制御を検証しつつ`Config`にまとめる。[marsdisk/schema.py#Radiation [L259–L277]]
- 物理層は`marsdisk.physics`サブパッケージの各モジュールを再公開し、放射、遮蔽、Smoluchowski、表層モデルを提供する。[marsdisk/physics/__init__.py#__module__ [L1–L34]]

## 3. データフロー（設定 → 実行 → 物理モジュール → 出力）
- 設定読み込み後に半径`r`と角速度を確定し、放射圧テーブル読み込みやブローアウトサイズ`a_blow`と`s_min`の初期化を行う。[marsdisk/run.py#run_zero_d [L273–L1005]]
- 既定の軌道量は `omega` と `v_kepler` が返し、角速度と周速度を `runtime_orbital_radius_m` から導出する。[marsdisk/grid.py:90][marsdisk/grid.py:34]
- 各ステップでPSD由来の不透明度と光学深度から遮蔽を適用し、外部供給`prod_rate`とシンク時間を渡して表層ODEを解く。[marsdisk/run.py#run_zero_d [L273–L1005]]
- 最小粒径の決定では、`fragments.s_sub_boundary` が `runtime_orbital_radius_m` 付きの `SublimationParams` から灰色体温度 `T_d = T_M\sqrt{R_{\rm MARS}/(2r)}` を算出し、1公転時間 `t_{\rm orb}=2\pi/\Omega` を基準に Hertz–Knudsen 厚み減少で `s_{\rm sub}` を評価する。`sizes.evolve_min_size=true` の場合はこの候補値を `psd.evolve_min_size` が受け、`s_min_evolved` として記録されたうえで `max(config, blowout, sublimation, evolved)` を満たすよう最終 `s_min` に反映される。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/physics/fragments.py#s_sub_boundary [L102–L165]][marsdisk/physics/psd.py#evolve_min_size [L149–L224]]
- `sinks.mode` が `"sublimation"` の場合は昇華・ガス抗力を考慮した `t_sink` を `sinks.total_sink_timescale` で計算し、`"none"` の場合は `t_sink=None` を渡して IMEX の追加損失項を無効化する。[marsdisk/schema.py#QStar [L197–L204]][marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]]
- 昇華シンク時間は `s_sink_from_timescale` が返す「1公転で消える粒径」`s_{\rm sink}` から `t_{\rm sink}=t_{\rm orb}(s_{\rm ref}/s_{\rm sink})` を再構成し、`Φ \le 0` ではシンクを無効化する。[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]][marsdisk/physics/sublimation.py#grain_temperature_graybody [L124–L135]]
- 得られたフラックスと質量収支を逐次蓄積し、DataFrame化した後にParquet・JSON・CSVへ書き出す。タイムステップ幅とブローアウト時間の解像度は `dt_over_t_blow`、有効損失分率は `fast_blowout_factor = 1 - \exp(-Δt/t_{\rm blow})` として記録され、`io.correct_fast_blowout=true` が設定された場合のみ `fast_blowout_corrected` が `true` になる。平均化された質量損失レートは `M_out_dot_avg`,`M_sink_dot_avg`,`dM_dt_surface_total_avg` として併記され、積分値 `M_loss_cum` / `mass_lost_by_sinks` の検証に利用できる。`chi_blow` が `"auto"` の場合は β と ⟨Q_pr⟩ に基づく 0.5–2.0 の推定値 `chi_blow_eff` が出力され、`t_{\rm blow} = chi_blow_eff/Ω` として用いられる。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/io/writer.py#write_parquet [L24–L106]]

## 4. 主要モジュール別の責務と依存
- `marsdisk/run.py`はPSD、放射、破片、供給、遮蔽、シンク各モジュールをインポートし、`run_zero_d`内で順に呼び出して時間積分とファイル出力を実行する。[marsdisk/run.py#run_zero_d [L273–L1005]]
- `marsdisk/grid.py`は `omega` と `v_kepler` を公開し、指定半径からケプラー角速度と周速度を取得する共通ユーティリティとなる。[marsdisk/grid.py:90][marsdisk/grid.py:34]
- `marsdisk/physics/psd.py`は三勾配と“wavy”補正でPSD状態を構築し、不透明度`kappa`を計算して`run_zero_d`に供給する。[marsdisk/physics/psd.py#compute_kappa [L121–L146]]
- `marsdisk/physics/radiation.py`は平均`Q_pr`や放射圧比`beta`、ブローアウト半径を算出し、テーブル読み込みを`io.tables`に委ねる。[marsdisk/physics/radiation.py#blowout_radius [L245–L259]]
- `marsdisk/io/tables.py`はPlanck平均⟨Q_pr⟩を `interp_qpr` で補間し、感度試験では `load_qpr_table` が外部テーブルを読み込んで補間器を更新する。[marsdisk/io/tables.py:253][marsdisk/io/tables.py:273]
- `marsdisk/physics/shielding.py`はΦテーブルを解釈し有効不透明度と`Sigma_tau1`を返し、必要に応じて値をクリップする。[marsdisk/physics/shielding.py#apply_shielding [L133–L216]]
- `marsdisk/physics/surface.py`はWyattスケーリングやシンク時間を取り込んだIMEXステップを提供し、外向流束とシンクを算出する。高速ブローアウト補正が有効化されている場合は表層流束が `fast_blowout_factor` でスケールされる。[marsdisk/physics/surface.py#step_surface [L178–L208]][marsdisk/run.py#run_zero_d [L273–L1005]]
- `marsdisk/run.py` は `run_config.json` に `sublimation_provenance` を追加し、HKL式、選択された `psat_model`、SiO 既定値（`α`,`μ`,`A`,`B`）、`P_gas`、有効温度範囲、タブレットファイルのパス、および実行時半径・公転時間を記録して後続解析のプロベナンスを残す。`sizes.evolve_min_size` や `io.correct_fast_blowout` の設定も `run_config` の `run_inputs` ブロックに含まれ、再現実行時の判定材料となる。[marsdisk/run.py#run_zero_d [L273–L1005]]

## 5. 設定スキーマ（主要キー）
| キー | 型 | 既定値 | 許容範囲 or 選択肢 | 出典 |
| --- | --- | --- | --- | --- |
| config | Config | 必須 | トップレベルで全セクションを保持 | [marsdisk/schema.py#Radiation [L259–L277]] |
| geometry | Geometry | mode="0D" | mode∈{"0D","1D"}; 半径は任意入力 | [marsdisk/schema.py#Geometry [L19–L26]] |
| material | Material | rho=3000.0 | rho∈[1000,5000]kg/m³ | [marsdisk/schema.py#Material [L91–L103]] |
| temps | Temps | T_M=2000.0 | T_M∈[1000,6000]K | [marsdisk/schema.py#Temps [L106–L122]] |
| sizes | Sizes | n_bins=40 | s_min,s_max必須; n_bins≥1 | [marsdisk/schema.py#Sizes [L125–L146]] |
| initial | Initial | s0_mode="upper" | mass_total必須; s0_mode∈{"mono","upper"} | [marsdisk/schema.py#Sizes [L125–L146]] |
| dynamics | Dynamics | f_wake=1.0 | e0,i0,t_damp_orbits必須 | [marsdisk/schema.py#Sizes [L125–L146]] |
> 既定では `e_mode` / `i_mode` を指定せず、入力スカラー `e0` / `i0` がそのまま初期値として採用される。
> **新オプション**: `dynamics.e_mode` と `dynamics.i_mode` に `mars_clearance` / `obs_tilt_spread` を指定すると、Δr・a・R_MARS をメートルで評価した `e = 1 - (R_MARS + Δr)/a` と、観測者傾斜 `obs_tilt_deg`（度）を中心にラジアン内部値 `i0` をサンプリングする。最小例:
> ```yaml
> dynamics:
>   e0: 0.1
>   i0: 0.05
>   t_damp_orbits: 1000.0
>   e_mode: mars_clearance
>   dr_min_m: 1.0
>   dr_max_m: 10.0
>   dr_dist: uniform
>   i_mode: obs_tilt_spread
>   obs_tilt_deg: 30.0
>   i_spread_deg: 5.0
>   rng_seed: 42
> ```
| psd | PSD | wavy_strength=0.0 | alpha必須 | [marsdisk/schema.py#Dynamics [L156–L194]] |
| qstar | QStar | なし | Qs,a_s,B,b_g,v_ref_kms必須 | [marsdisk/schema.py#Dynamics [L156–L194]] |
| disk | Disk | なし | geometryにr_in_RM,r_out_RM必須 | [marsdisk/schema.py#DiskGeometry [L29–L35]] |
| inner_disk_mass | InnerDiskMass | use_Mmars_ratio=True | map_to_sigma="analytic"固定 | [marsdisk/schema.py#InnerDiskMass [L44–L49]] |
| surface | Surface | init_policy="clip_by_tau1" | use_tcoll∈{True,False} | [marsdisk/schema.py#Dynamics [L156–L194]] |
| supply | Supply | mode="const" | const/powerlaw/table/piecewise切替 | [marsdisk/schema.py#SupplyConst [L52–L53]] |
| sinks | Sinks | enable_sublimation=True | sublimation/gas dragのON/OFFとρ_g | [marsdisk/schema.py#QStar [L197–L204]] |
| radiation | Radiation | TM_K=None | Q_pr∈(0,∞)かつ0.5≤Q_pr≤1.5 | [marsdisk/schema.py#Surface [L214–L219]] |
| shielding | Shielding | phi_table=None | Φテーブルパス任意指定 | [marsdisk/schema.py#SublimationParamsModel [L222–L238]] |
| numerics | Numerics | safety=0.1; atol=1e-10; rtol=1e-6 | t_end_years,dt_init必須 | [marsdisk/schema.py#SublimationParamsModel [L222–L238]] |
| io | IO | outdir="out", substep_fast_blowout=false | 出力先・高速ブローアウト補正 (`correct_fast_blowout`) に加えて、`substep_fast_blowout` と `substep_max_ratio` でステップ分割を制御 | [marsdisk/schema.py#Numerics [L286–L293]] |

## 6. 物理モデルの計算ステップの要約
- 粒径と温度から放射圧比を計算してブローアウト境界を定める（beta）。[marsdisk/physics/radiation.py#blowout_radius [L245–L259]]
- 粒径分布を三勾配で構築し“wavy”補正込みの数密と不透明度を用意する（PSD）。[marsdisk/physics/psd.py#compute_kappa [L121–L146]]
- 光学深度からΦテーブルを引いて有効不透明度とΣτ=1の上限を求める（Phi）。[marsdisk/physics/shielding.py#apply_shielding [L133–L216]]
- Wyattの衝突寿命やシンク時間を組み込んだ表層ODEを暗示的に進めて外向流束とシンクを出力する（S1）。[marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]][marsdisk/run.py#run_zero_d [L273–L1005]]
- Smoluchowski IMEX-BDF(1)で内部PSDを更新し質量保存誤差を評価する（C3）。[marsdisk/physics/smol.py#compute_mass_budget_error_C4 [L104–L131]]
- 出力判定では `beta_at_smin_config` と `beta_threshold` を比較し、`case_status="blowout"`（閾値以上）、`"ok"`（閾値未満）、質量収支違反など例外時のみ `"failed"` として記録する。[marsdisk/physics/radiation.py#BLOWOUT_BETA_THRESHOLD [L32]][marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]]

## 7. 温度・放射の上書きと出力フィールド
- `T_M_used` は放射計算に採用された火星面温度で、`radiation.TM_K`（存在する場合）が `temps.T_M` を上書きしたかどうかを `T_M_source` が `"radiation.TM_K"` または `"temps.T_M"` として示す。[marsdisk/schema.py#Temps [L106–L122]][marsdisk/run.py#load_config [L231–L239]][marsdisk/run.py#run_zero_d [L273–L1005]]
- `mass_lost_by_blowout` は放射圧剥離による累積損失、`mass_lost_by_sinks` は昇華・ガス抗力による累積損失を示す。`sinks.mode="none"` では後者が全ステップで0になり、`checks/mass_budget.csv` で許容誤差0.5%以下が確認される。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/io/writer.py#write_parquet [L24–L106]](tests/test_sinks_none.py)

## 8. I/O 仕様（出力ファイル種別、カラム/フィールドの最低限）
- 時系列は積分結果をDataFrameにし`out/series/run.parquet`として`tau`, `a_blow`, `prod_subblow_area_rate`などを保持する。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]]
- 高速ブローアウト診断として `dt_over_t_blow`,`fast_blowout_factor`,`fast_blowout_factor_avg`,`fast_blowout_flag_gt3/gt10`,`n_substeps` が出力され、`chi_blow_eff` が自動推定に使われた係数を示す。ステップ平均の質量流束は `M_out_dot_avg`,`M_sink_dot_avg`,`dM_dt_surface_total_avg` を参照する。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/io/writer.py#write_parquet [L24–L106]]
- 最小粒径進化フックは `sizes.evolve_min_size` と `sizes.dsdt_model` / `sizes.dsdt_params` / `sizes.apply_evolved_min_size` で制御され、`s_min_evolved` カラムに逐次記録される。[marsdisk/physics/psd.py#evolve_min_size [L149–L224]][marsdisk/physics/sizes.py#eval_ds_dt_sublimation [L10–L28]]
- 集計は`summary.json`に累積損失や閾値ステータスを書き、ライターが縮進整形する。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/io/writer.py#write_parquet [L24–L106]]
- 検証ログは質量予算CSVと`run_config.json`に式・定数・Git情報を残して後追い解析を支える。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/io/writer.py#write_parquet [L24–L106]]

### 固定ステップの時間管理
- `time`カラムは各ステップ終了時の通算秒数で、固定刻み`Δt = numerics.dt_init` [s] を用いる。
- 反復は`numerics.t_end_years`で指定した積分時間か`MAX_STEPS`到達のいずれかまで継続する。

## 9. 再現性と追跡性（乱数・バージョン・プロヴェナンス）
- 乱数初期化は`random`と`numpy`のシードを固定して試行を再現可能にする。[marsdisk/run.py#run_n_steps [L205–L223]]
- 各ステップの質量初期値・損失・誤差百分率を記録し、閾値超過時に例外フラグを設定できる。[marsdisk/run.py#run_zero_d [L273–L1005]]
- 実行設定の式・使用値・Git状態を`run_config.json`に書き出し外部ツールから追跡できる。[marsdisk/run.py#run_zero_d [L273–L1005]]

## 10. 既知の制約・未実装・注意点
- Q_prやΦテーブルが存在しない場合は解析近似へフォールバックし警告を出すため、精密光学定数は外部入力が必要である。[marsdisk/io/tables.py#interp_phi [L263–L270]]
- サブリメーション境界は時間尺度が不足すると固定値1e-3 mと警告で代替され、現状は暫定実装である。[marsdisk/physics/fragments.py#s_sub_boundary [L102–L165]]
- 追加シンクは代表サイズによる簡易推算で、モードに応じて時間尺度を最小選択するのみである。[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]
- 長期シミュレーションは`MAX_STEPS`で上限制限されWyattカップリングも光学深度閾値に依存するため、高τ領域の精度は未確認である。[marsdisk/run.py#run_zero_d [L273–L1005]]

## 11. 最小実行例（1つだけ、実行コマンドと最小設定）
以下のコマンドと設定を用いるとベースケースの0Dシミュレーションが完走する。[marsdisk/run.py#run_zero_d [L273–L1005]](configs/base.yml)

```bash
python -m marsdisk.run --config configs/base.yml
```

```yaml
geometry:
  mode: "0D"
material:
  rho: 3000.0
temps:
  T_M: 2000.0
sizes:
  s_min: 1.0e-6
  s_max: 3.0
  n_bins: 40
initial:
  mass_total: 1.0e-5
  s0_mode: "upper"
numerics:
  t_end_years: 2.0
  dt_init: 10.0
io:
  outdir: "out"
```

## 12. Step18 — 供給 vs ブローアウト dM/dt ベンチマーク
- `diagnostics/minimal/run_minimal_matrix.py` が 5 半径 × 3 温度 × 3 ブローアウト制御（補正OFF/ON、サブステップON）の45ケースを2年間積分し、供給 `prod_subblow_area_rate` と表層損失 `dSigma_dt_blowout`／`M_out_dot` を同一テーブルに集約する。(diagnostics/minimal/run_minimal_matrix.py)
- 実行コマンドは `python diagnostics/minimal/run_minimal_matrix.py`。完了すると `diagnostics/minimal/results/supply_vs_blowout.csv` に各ケースの最終 `Omega_s`,`t_blow_s`,`dt_over_t_blow`,`blowout_to_supply_ratio` が書き出され、`diagnostics/minimal/results/supply_vs_blowout_reference_check.json` で `analysis/radius_sweep/radius_sweep_metrics.csv` と (T=2500 K, baseline モード) の数値整合が <1e-2 の相対誤差で検証される。
- 供給に対する表層流出の瘦せやすさはヒートマップ `diagnostics/minimal/plots/supply_vs_blowout.png` と `figures/supply_vs_blowout.png` に保存され、`blowout_to_supply_ratio ≳ 1` がブローアウト優勢領域として即座に読み取れる。
- 各ケースの Parquet/summary は `diagnostics/minimal/runs/<series>/<case_id>/` に展開され、`series/run.parquet` 末尾の `dSigma_dt_*` 列が旧 `outflux_surface`/`sink_flux_surface` を補完する。ベースライン系列は `analysis/radius_sweep/radius_sweep_metrics.csv` の該当行と比較し、`dSigma_dt_blowout` を含めた主要指標が一致することを reference_check で保証している。

## 13. 最新検証ログ（SiO psat auto-selector + HKLフラックス）
- `analysis/checks_psat_auto_01/` 以下に **psat_model="auto"** の挙動検証を格納し、タブレット→局所Clausius→既定Clausiusの切り替えを run_config.json の `sublimation_provenance` で追跡できる。[analysis/checks_psat_auto_01/runs/case_A_tabulated/run_config.json][analysis/checks_psat_auto_01/runs/case_B_localfit/run_config.json][analysis/checks_psat_auto_01/runs/case_C_clausius/run_config.json]
- HKLフラックスの温度掃引は `analysis/checks_psat_auto_01/scan_hkl.py` で実施し、`scans/hkl_scan_case_*.csv` と `scans/hkl_assertions.json` に単調性・非負性チェック結果を記録している。SiOのα=7×10⁻³、μ=4.40849×10⁻² kg mol⁻¹、P_gas=0 を明示してHN式 `J=α(P_sat-P_gas)\sqrt{\mu/(2\pi RT)}` を評価する。[analysis/checks_psat_auto_01/scans/hkl_assertions.json][marsdisk/physics/sublimation.py#mass_flux_hkl [L534–L584]]
- 各ケースは `analysis/checks_psat_auto_01/logs/run.log` に CLI 実行ログを、`logs/pytest_sio.log` に昇華ユニットテスト結果を保存し、`scans/psat_provenance.json` にresolvedモデル・A/B係数・valid_Kをサマリして再分析に備える。[analysis/checks_psat_auto_01/scans/psat_provenance.json][analysis/checks_psat_auto_01/logs/pytest_sio.log]
