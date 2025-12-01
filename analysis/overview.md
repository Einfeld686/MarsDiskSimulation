> **文書種別**: 解説（Diátaxis: Explanation）

## 0. ドキュメント指針
- `analysis/overview.md`（本書）はアーキテクチャや仕様の「解説」に位置付け、同系列で `analysis/run-recipes.md` を「手順」、`analysis/equations.md` を「リファレンス」とする Diátaxis 分類を明示した。各ファイル先頭に文書種別メタデータを挿入し、読者が用途別に資料を切り替えられるようにした。
- 重要な設計判断は `analysis/adr/` 以下の Architecture Decision Record (ADR) シリーズで管理する。第1号として `analysis/adr/0001-choose-solver.md` に IMEX-BDF(1) 採用理由と影響範囲を記録し、将来の solver/physics 切り替え議論のたたき台にする。
- 要求→設計→式→テスト→成果物を一表で紐づける要求トレーサビリティマトリクス (RTM) を `analysis/traceability/rtm.csv` に追加し、CI やレビュー時に仕様充足状況を即座に確認できるようにした。
- ドキュメントとコードの整合性は `marsdisk/ops/doc_sync_agent.py` によって維持され、`ensure_equation_ids` が式番号を管理する。[marsdisk/ops/doc_sync_agent.py#main][marsdisk/ops/doc_sync_agent.py#ensure_equation_ids]
- リリースノートと変更履歴は `analysis/CHANGELOG.md` に集約し、DocSyncAgent の対象に含めて参照切れやパス揺れを防ぐ。

## 1. 目的と範囲
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。
- 0D円盤で破砕生成による`prod_subblow_area_rate`と表層剥離による`M_out_dot`を時間発展させ、累積損失を summary の`M_loss`と時系列の`mass_lost_by_*`で記録する。[marsdisk/schema.py#Geometry [L20–L31]][marsdisk/run.py#run_zero_d [L426–L1362]]
- 形成・生存制約はリング拡散の遅速により衛星列の質量シーケンスが変わること（遅:多数・外側ほど重い、速:単一巨大衛星）と、Phobos/Deimos を残すには **$M_{\rm disk}\le3\times10^{-5}M_{\rm Mars}$ 且つ $(Q/k_2)<80$** が必要という条件を踏まえて初期質量と tidal パラメータを設定する。[\@CridaCharnoz2012_Science338_1196; @CanupSalmon2018_SciAdv4_eaar6887]
- CLI経由で呼ばれる`run_zero_d`がYAMLを読み、放射・遮蔽テーブルやPSDを初期化したうえで表層面密度を積分し、出力に書き出す。[marsdisk/run.py#run_zero_d [L426–L1362]]
- 将来の半径1D拡張に備えてケプラー格子と粘性拡散の骨組みを保持するが、現行は0D主導である。[marsdisk/grid.py#omega_kepler [L17–L31]][marsdisk/physics/viscosity.py#step_viscous_diffusion_C5 [L51–L134]]

## 2. 全体アーキテクチャ
- CLI層は`argparse`で`--config`を受け取ると同時に、オプションの`--override path=value`を複数解釈してYAML辞書にマージしたうえで`load_config`を通じて設定を生成する。[marsdisk/run.py#load_config [L372–L387]][marsdisk/run.py#main [L1622–L1654]]
- 設定層はPydanticモデルで幾何、物性、数値制御を検証しつつ`Config`にまとめる。[marsdisk/schema.py#Shielding [L323–L325]][marsdisk/schema.py#IO [L437–L455]]
- 物理層は`marsdisk.physics`サブパッケージの各モジュールを再公開し、放射、遮蔽、Smoluchowski、表層モデルを提供する。[marsdisk/physics/__init__.py#__module__ [L1–L34]]
- 火星放射源は `mars_temperature_driver` を経由して時刻依存の T_M を供給し、`radiation`/`sinks`/`sizes` が参照する。ドライバは `marsdisk/physics/tempdriver.py` の `resolve_temperature_driver` で実体化され、`run_zero_d` のサイクルごとに評価される。[marsdisk/physics/tempdriver.py:149–188][marsdisk/run.py:598–621]
- 放射圧のスイッチは `radiation.source∈{"mars","off","none"}` に制限され、Pydantic と `run_zero_d` の双方でバリデーションすることで太陽放射経路や未定義ソースを受け付けない。`source="none"` は内部で `"off"` に正規化され、Mars-only 探査の要件を守ったまま放射圧を無効化できる。[marsdisk/schema.py:323–323][marsdisk/run.py:548–552]
- Φテーブルは `shielding.table_path` を優先的に解決し、旧 `phi_table` や `mode=table` 指定は `mode_resolved` で `psitau` に正規化してからロードする。[marsdisk/schema.py:384–388][marsdisk/run.py:571–572]
- 相判定は `marsdisk/physics/phase.py` の `PhaseEvaluator` が温度・圧力・遮蔽後のτを受け、マップ（`siO2_cooling_map.lookup_phase_state`）か閾値フォールバックで `phase_state∈{solid,vapor}` と蒸気分率 `f_vap` を返す。判定は各タイムステップで一度だけ実行され、その結果で `sink_selected∈{rp_blowout,hydro_escape,none}` と `t_sink` が固定されるため、同一ステップ内でブローアウトと流体力学的散逸が重複することはない。[marsdisk/physics/phase.py:53-190][marsdisk/run.py:1003-1445]

## 3. データフロー（設定 → 実行 → 物理モジュール → 出力）
- 設定読み込み後に半径`r`と角速度を確定し、放射圧テーブル読み込みやブローアウトサイズ`a_blow`と`s_min`の初期化を行う。[marsdisk/run.py#run_zero_d [L426–L1362]]
- 既定の軌道量は `omega` と `v_kepler` が返し、角速度と周速度を `runtime_orbital_radius_m` から導出する。[marsdisk/grid.py#omega [L90]][marsdisk/grid.py#v_kepler [L34]]
- 各ステップで `mars_temperature_driver` が時刻`t`の火星温度を返し、Planck平均⟨Q_pr⟩・β・`a_blow`・`grain_temperature_graybody` へ伝播する。温度時系列は `run.parquet` の `T_M_used`/`rad_flux_Mars`/Q_pr_at_smin/`beta_at_smin`/`a_blow_at_smin` に記録され、`summary.json` では `T_M_min`/`T_M_median`/`T_M_max` と `beta_at_smin_min`/`beta_at_smin_median`/`beta_at_smin_max` を統計として保持する。[marsdisk/run.py:846–1356][marsdisk/physics/sinks.py:83–160]
- 相分岐は遮蔽計算で得た `tau_mars_line_of_sight` と火星温度を `PhaseEvaluator` に渡して `phase_state` を決定し、`solid` のときはブローアウト（`sink_selected="rp_blowout"`）、`vapor` のときは水素流体逃亡のスケーリング `hydro_escape_timescale` を `surface.step_surface` のシンクとして適用する。評価結果は `run.parquet`/`diagnostics.parquet` の `phase_state`/`phase_f_vap`/`sink_selected`/`tau_gate_blocked` に保存し、`summary.json` では `phase_branching` と `radiation_tau_gate` の両ブロックで集計する。[marsdisk/physics/phase.py#hydro_escape_timescale [L238–260]][marsdisk/run.py:1003-1415][marsdisk/run.py:1507-1599]
- `s_min_components` には `config`,`blowout`,`effective`,`floor_dynamic` を保持し、`radiation.freeze_kappa` がPlanck平均κを初期値で固定、`surface.freeze_sigma` が表層密度を初期値で保つ。`blowout.enabled=false` では `Σ_surf Ω` を抑制し、`shielding.mode∈{"psitau","fixed_tau1","off"}` がΦテーブル適用／一定τ／遮蔽無効を切り替える。昇華侵食量は `mass_lost_sublimation_step` と `dSigma_dt_sublimation` で診断し、任意の `sizes.evolve_min_size=true` は床を変更せず `s_min_evolved` を追跡する。[marsdisk/run.py#run_zero_d [L623–L1016]][marsdisk/physics/psd.py#evolve_min_size [L267–L356]][marsdisk/physics/surface.py#step_surface_density_S1 [L96–L170]]
- `sinks.mode` が `"sublimation"` の場合は昇華・ガス抗力を考慮した `t_sink` を `sinks.total_sink_timescale` で計算し、`"none"` の場合は `t_sink=None` を渡して IMEX の追加損失項を無効化する。[marsdisk/schema.py#QStar [L202–L204]][marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]]
- コールグラフ（`run_zero_d → step_surface → total_sink_timescale → mass_flux_hkl → s_sink_from_timescale`）と gas-poor 既定でのフラグ伝播は `analysis/sinks_callgraph.md` に mermaid 図付きで整理し、`ALLOW_TL2003=false` のまま感度試験時に参照する。
- `siO2_disk_cooling/siO2_cooling_map.py` の熱史マップは (E.042)/(E.043) の解析解で火星表面温度と粒子温度を評価し、Hyodo et al. (2018) の放射冷却スケーリング（式2–6）を直接適用して β 閾値と IR 加熱の境界を可視化する。`python -m siO2_disk_cooling.siO2_cooling_map --plot-mode phase` で固体分率マップ（青=固体、赤=蒸気）を描画でき、`--cell-width-Rmars` 未指定なら隣接の `configs/base.yml` などから `disk.geometry.r_in_RM`/`r_out_RM`/`n_cells` を読んでセル幅を自動推定する。[\@Hyodo2018_ApJ860_150]
- 化学シンクは気相凝縮と溶融固化物の化学差（Pignatale et al. 2018）と外縁ガス包絡での凝縮スペクトル（Ronnet et al. 2016）を根拠に、HKL 昇華フラックスと `s_sink_from_timescale` の係数を設定する。[\@Pignatale2018_ApJ853_118; @Ronnet2016_ApJ828_109]
- 昇華シンク時間は `s_sink_from_timescale` が返す「1公転で消える粒径」`s_{\rm sink}` から `t_{\rm sink}=t_{\rm orb}(s_{\rm ref}/s_{\rm sink})` を再構成し、`Φ \le 0` ではシンクを無効化する。[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]][marsdisk/physics/radiation.py#grain_temperature_graybody [L120–L146]]
- 得られたフラックスと質量収支を逐次蓄積し、Parquet/JSON/CSVに書き出す際に `F_abs`,`sigma_surf`,`kappa_Planck`,`tau_eff`,`psi_shield`,`s_peak`,`M_out_cum` などの診断列を追加し、`dt_over_t_blow` や `fast_blowout_factor = 1 - \exp(-Δt/t_{\rm blow})`、昇華侵食項 `dSigma_dt_sublimation`／`mass_lost_sinks_step` を併記する。Summary には `mass_budget_max_error_percent` と `dt_over_t_blow_median` が追記され、`orbit_rollup.csv` は `mass_loss_frac_per_orbit` や累積損失も含めて更新される (`numerics.orbit_rollup=false` で抑制可)。`chi_blow` が `"auto"` の場合は β と ⟨Q_pr⟩ に基づく 0.5–2.0 の推定値 `chi_blow_eff` が出力され、`t_{\rm blow} = chi_blow_eff/Ω` として用いられる。[marsdisk/run.py#run_zero_d [L1036–L1362]][marsdisk/io/writer.py#write_parquet [L24–L175]]

## 4. 主要モジュール別の責務と依存
- `marsdisk/run.py`はPSD、放射、破片、供給、遮蔽、シンク各モジュールをインポートし、`run_zero_d`内で順に呼び出して時間積分とファイル出力を実行する。[marsdisk/run.py#run_zero_d [L426–L1362]]
- `marsdisk/grid.py`は `omega` と `v_kepler` を公開し、指定半径からケプラー角速度と周速度を取得する共通ユーティリティとなる。[marsdisk/grid.py#omega [L90]][marsdisk/grid.py#v_kepler [L34]]
- `marsdisk/physics/psd.py`は三勾配と“wavy”補正でPSD状態を構築し、不透明度`kappa`を計算して`run_zero_d`に供給する。[marsdisk/physics/psd.py#compute_kappa [L121–L146]]
- `marsdisk/physics/radiation.py`は平均`Q_pr`や放射圧比`beta`、ブローアウト半径を算出し、テーブル読み込みを`io.tables`に委ねる。[marsdisk/physics/radiation.py#blowout_radius [L244–L258]]
- `marsdisk/io/tables.py`はPlanck平均⟨Q_pr⟩を `interp_qpr` で補間し、感度試験では `load_qpr_table` が外部テーブルを読み込んで補間器を更新する。また、`interp_phi` は自遮蔽係数テーブルの補間を提供する。[marsdisk/io/tables.py#interp_qpr [L259–L270]][marsdisk/io/tables.py#load_qpr_table [L283–L295]][marsdisk/io/tables.py#interp_phi]
- `marsdisk/ops/make_qpr_table.py` は `compute_planck_mean_qpr` で Rayleigh–幾何ブリッジを介した Planck 平均⟨Q_pr⟩を計算し、CLI `main` が HDF5 テーブルに書き出して `radiation.qpr_table_path` が参照できるようにする。[marsdisk/ops/make_qpr_table.py#compute_planck_mean_qpr][marsdisk/ops/make_qpr_table.py#main]
- `marsdisk/physics/shielding.py`はΦテーブルを解釈し有効不透明度と`Sigma_tau1`を返し、必要に応じて値をクリップする。[marsdisk/physics/shielding.py#apply_shielding [L133–L216]]
- `marsdisk/physics/surface.py`はStrubbe–Chiang（Wyatt 2008 で紹介）スケーリングやシンク時間を取り込んだIMEXステップを提供し、外向流束とシンクを算出する。高速ブローアウト補正が有効化されている場合は表層流束が `fast_blowout_factor` でスケールされる。[\@StrubbeChiang2006_ApJ648_652; @Wyatt2008][marsdisk/physics/surface.py#step_surface [L185–L208]][marsdisk/run.py#run_zero_d [L426–L1362]]
- `marsdisk/run.py` は `run_config.json` に `physics_controls` を追加して `blowout.enabled`,`freeze_kappa`,`freeze_sigma`,`shielding.mode`,`psd.floor.mode` などの実行時トグルを記録し、従来通り `sublimation_provenance` で HKL 式や `psat_model`、SiO 既定値、実行半径・公転時間も保持してプロベナンスを残す。`sizes.evolve_min_size` や `io.correct_fast_blowout` の設定は `run_inputs` ブロックから確認できる。[marsdisk/run.py#run_zero_d [L1523–L1611]]

## 5. 設定スキーマ（主要キー）
| キー | 型 | 既定値 | 許容範囲 or 選択肢 | 出典 |
| --- | --- | --- | --- | --- |
| config | Config | 必須 | トップレベルで全セクションを保持 | [marsdisk/schema.py#IO [L437–L455]] |
| geometry | Geometry | mode="0D" | mode∈{"0D","1D"}; 半径は任意入力 | [marsdisk/schema.py#Geometry [L20–L31]] |
| material | Material | rho=3000.0 | rho∈[1000,5000]kg/m³ | [marsdisk/schema.py#Material [L96–L108]] |
| temps | Temps | T_M=2000.0 | T_M∈[1000,6000]K | [marsdisk/schema.py#Temps [L111–L127]] |
| sizes | Sizes | n_bins=40 | s_min,s_max必須; n_bins≥1 | [marsdisk/schema.py#Sizes [L130–L151]] |
| initial | Initial | s0_mode="upper" | mass_total必須; s0_mode∈{"mono","upper"} | [marsdisk/schema.py#Initial [L154–L158]] |
| dynamics | Dynamics | f_wake=1.0 | e0,i0,t_damp_orbits必須 | [marsdisk/schema.py#Dynamics [L161–L199]] |
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
| psd | PSD | wavy_strength=0.0 | alpha必須 | [marsdisk/schema.py#PSD [L212–L216]] |
| qstar | QStar | なし | Qs,a_s,B,b_g,v_ref_kms必須 | [marsdisk/schema.py#QStar [L202–L209]] |
| disk | Disk | なし | geometryにr_in_RM,r_out_RM必須 | [marsdisk/schema.py#Disk [L43–L46]] |
| inner_disk_mass | InnerDiskMass | use_Mmars_ratio=True | map_to_sigma="analytic"固定 | [marsdisk/schema.py#InnerDiskMass [L49–L54]] |
| surface | Surface | init_policy="clip_by_tau1" | use_tcoll∈{True,False} | [marsdisk/schema.py#Surface [L223–L224]] |
| supply | Supply | mode="const" | const/powerlaw/table/piecewise切替 | [marsdisk/schema.py#Supply [L85–L93]] |
| sinks | Sinks | enable_sublimation=True | sublimation/gas dragのON/OFFとρ_g | [marsdisk/schema.py#Sinks [L251–L261]] |
| radiation | Radiation | TM_K=None | Q_pr∈(0,∞)かつ0.5≤Q_pr≤1.5 | [marsdisk/schema.py#Radiation [L269–L314]] |
| shielding | Shielding | table_path=None | Φテーブル/legacy `phi_table` を `mode_resolved` で正規化 | [marsdisk/schema.py:384–388] |
| numerics | Numerics | safety=0.1; atol=1e-10; rtol=1e-6 | t_end_years,dt_init必須 | [marsdisk/schema.py#Numerics [L344–L409]] |
| io | IO | outdir="out", substep_fast_blowout=false | 出力先・高速ブローアウト補正 (`correct_fast_blowout`) に加えて、`substep_fast_blowout` と `substep_max_ratio` でステップ分割を制御 | [marsdisk/schema.py#Numerics [L413–L430]] |

## 6. 物理モデルの計算ステップの要約
- ⟨Q_pr⟩ は `planck_mean_qpr` がテーブル／指定値から取得し、外れ値は `qpr_lookup` 側でテーブル範囲へクランプしたうえで β・ブローアウト境界に渡す（R1–R3）。[marsdisk/physics/radiation.py#planck_mean_qpr [L236–247]][marsdisk/physics/radiation.py#qpr_lookup [L179–234]][marsdisk/physics/radiation.py#blowout_radius [L274–288]]
- 粒径分布を `update_psd_state` で三勾配＋任意の“wavy”補正付きに構築し、その状態から不透明度 `\kappa` を計算する（PSD）。[marsdisk/physics/psd.py#update_psd_state [L30–118]][marsdisk/physics/psd.py#compute_kappa [L121–146]]
- 光学深度からΦテーブルを引いて有効不透明度とΣτ=1の上限を求める（Phi）。Φの 0–1 クランプと κ_eff の計算は `effective_kappa` が担い、`apply_shielding` が Στ=1 を返す。[marsdisk/physics/shielding.py#effective_kappa [L90–120]][marsdisk/physics/shielding.py#apply_shielding [L133–216]]
- τ=1 の表層面密度を近似して返す（光学的深さの定義に基づく）。[marsdisk/physics/shielding.py#sigma_tau1 [L123–L130]]
- Strubbe–Chiang衝突寿命やシンク時間を組み込んだ表層ODEを暗示的に進めて外向流束とシンクを出力する（S1）。[marsdisk/physics/surface.py#step_surface_density_S1 [L96–L163]][marsdisk/run.py#run_zero_d [L426–L1362]]
- 飽和蒸気圧モデルのバックエンドを選ぶ（Clausius–Clapeyron／表引き）。[marsdisk/physics/sublimation.py#choose_psat_backend [L386–L496]]
- Smoluchowski IMEX-BDF(1)で内部PSDを更新し質量保存誤差を評価する（C3）。[marsdisk/physics/smol.py#compute_mass_budget_error_C4 [L104–L131]]
- Smol 方程式の時刻更新（剛性=陰／非剛性=陽の IMEX＋一次BDF）。[marsdisk/physics/smol.py#step_imex_bdf1_C3 [L18–L101]]
- 出力判定では `beta_at_smin_config` と `beta_threshold` を比較し、`case_status="blowout"`（閾値以上）、`"ok"`（閾値未満）、質量収支違反など例外時のみ `"failed"` として記録する。[marsdisk/physics/radiation.py#BLOWOUT_BETA_THRESHOLD [L32] :32][marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/run.py#run_zero_d [L426–L1362]]

## 7. 温度・放射の上書きと出力フィールド
- `T_M_used` は放射計算に採用された火星面温度で、`radiation.TM_K`（存在する場合）が `temps.T_M` を上書きしたかどうかを `T_M_source` が `"radiation.TM_K"` または `"temps.T_M"` として示す。[marsdisk/schema.py#Temps [L111–L127]][marsdisk/run.py#load_config [L372]][marsdisk/run.py#run_zero_d [L426–L1362]]
- `mass_lost_by_blowout` は放射圧剥離による累積損失、`mass_lost_by_sinks` は昇華・ガス抗力による累積損失を示す。`sinks.mode="none"` では後者が全ステップで0になり、`checks/mass_budget.csv` で許容誤差0.5%以下が確認される。[marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/io/writer.py#write_parquet [L24–L162]](tests/test_sinks_none.py)

## 8. I/O 仕様（出力ファイル種別、カラム/フィールドの最低限）
- 時系列は積分結果をDataFrameにし`out/series/run.parquet`として`tau`, `a_blow`, `prod_subblow_area_rate`などを保持する。[marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/run.py#run_zero_d [L426–L1362]]
- 高速ブローアウト診断として `dt_over_t_blow`,`fast_blowout_factor`,`fast_blowout_factor_avg`,`fast_blowout_flag_gt3/gt10`,`n_substeps` が出力され、`chi_blow_eff` が自動推定に使われた係数を示す。ステップ平均の質量流束は `M_out_dot_avg`,`M_sink_dot_avg`,`dM_dt_surface_total_avg` を参照する。[marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/io/writer.py#write_parquet [L24–L162]]
- 粒径分布の時間変化は `out/series/psd_hist.parquet` に `time`×`bin_index` の縦持ちテーブルとして出力され、`s_bin_center`,`N_bin`,`Sigma_surf` を含む。[marsdisk/run.py:1281–1415][marsdisk/io/writer.py:75–137]
- 最小粒径進化フックは `sizes.evolve_min_size` と `sizes.dsdt_model` / `sizes.dsdt_params` / `sizes.apply_evolved_min_size` で制御され、`s_min_evolved` カラムに逐次記録される。[marsdisk/physics/psd.py#apply_uniform_size_drift [L149–L264]][marsdisk/physics/sizes.py#eval_ds_dt_sublimation [L10–L28]]
- 集計は`summary.json`に累積損失や閾値ステータスを書き、ライターが縮進整形する。[marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/io/writer.py#write_parquet [L24–L162]]
- 検証ログは質量予算CSVと`run_config.json`に式・定数・Git情報を残して後追い解析を支える。[marsdisk/run.py#run_zero_d [L426–L1362]][marsdisk/io/writer.py#write_parquet [L24–L162]]
- `diagnostics.phase7.enable=true` のときだけ Phase7 診断列を追加する。`run.parquet` では `mloss_blowout_rate`/`mloss_sink_rate`/`mloss_total_rate` と `cum_mloss_*`、競合時間 `t_coll` と `ts_ratio=t_blow/t_coll`、遮蔽後の `kappa_eff`/`tau_eff`、ゲート係数 `blowout_gate_factor` をエクスポートし、summary に `median_gate_factor` と τゲート遮断割合 `tau_gate_blocked_time_fraction`、rollup に `gate_factor_median` を出力する（フラグOFF時は既存列のみ）。[marsdisk/run.py:1036–1950][docs/devnotes/phase7_gate_spec.md]

### 固定ステップの時間管理
- `time`カラムは各ステップ終了時の通算秒数で、固定刻み`Δt = numerics.dt_init` [s] を用いる。
- 反復は`numerics.t_end_years`で指定した積分時間か`MAX_STEPS`到達のいずれかまで継続する。



### write_parquet ─ TODO: describe write_parquet
- 入力: … / 出力: …
- 数式/前提: （TODO: 簡潔に）
- 参照: [marsdisk/io/writer.py#write_parquet [L24–L162]]


### write_summary ─ TODO: describe write_summary
- 入力: … / 出力: …
- 数式/前提: （TODO: 簡潔に）
- 参照: [marsdisk/io/writer.py#write_summary [L185]]


### write_run_config ─ TODO: describe write_run_config
- 入力: … / 出力: …
- 数式/前提: （TODO: 簡潔に）
- 参照: [marsdisk/io/writer.py#write_run_config [L196]]


### write_mass_budget ─ TODO: describe write_mass_budget
- 入力: … / 出力: …
- 数式/前提: （TODO: 簡潔に）
- 参照: [marsdisk/io/writer.py#write_mass_budget [L204]]


### load_phi_table ─ TODO: describe load_phi_table
- 入力: … / 出力: …
- 数式/前提: （TODO: 簡潔に）
- 参照: [marsdisk/io/tables.py#load_phi_table [L298–L353]]
## 9. 再現性と追跡性（乱数・バージョン・プロヴェナンス）
- 乱数初期化は`random`と`numpy`のシードを固定して試行を再現可能にする。[marsdisk/run.py#run_zero_d [L426]]
- 各ステップの質量初期値・損失・誤差百分率を記録し、閾値超過時に例外フラグを設定できる。[marsdisk/run.py#run_zero_d [L426–L1362]]
- 実行設定の式・使用値・Git状態を`run_config.json`に書き出し外部ツールから追跡できる。[marsdisk/run.py#run_zero_d [L426–L1362]]

## 10. 既知の制約・未実装・注意点
- Q_prやΦテーブルが存在しない場合は解析近似へフォールバックし警告を出すため、精密光学定数は外部入力が必要である。[marsdisk/io/tables.py#interp_qpr [L259–L270]]
- サブリメーション境界は時間尺度が不足すると固定値1e-3 mと警告で代替され、現状は暫定実装である。[marsdisk/physics/fragments.py#s_sub_boundary [L101–L164]]
- 追加シンクは代表サイズによる簡易推算で、モードに応じて時間尺度を最小選択するのみである。[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]]
- 長期シミュレーションは`MAX_STEPS`で上限制限されStrubbe–Chiangカップリングも光学深度閾値に依存するため、高τ領域の精度は未確認である。[marsdisk/run.py#run_zero_d [L426–L1362]]

## 11. 最小実行例（1つだけ、実行コマンドと最小設定）
以下のコマンドと設定を用いるとベースケースの0Dシミュレーションが完走する。[marsdisk/run.py#run_zero_d [L426–L1362]](configs/base.yml)

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

## 14. 内側ロッシュ円盤 Φ×温度スイート
- `scripts/run_inner_disk_suite.py` は Φ(1)={0.20,0.37,0.60} と T_M=1000–6000 K（50 K 刻み）を組み合わせ、代表半径 2.5 R_Mars で `geometry.r` と `numerics.dt_init` を公転周期に合わせた `--override` へ展開する。[scripts/run_inner_disk_suite.py:78–79][scripts/run_inner_disk_suite.py:321–365]
- 各ケース実行後に `series/psd_hist.parquet` を読み込んで PSD の時間変化を描画し、`figs/frame_*.png` と `animations/psd_evolution.gif` を生成して凡例に「惑星放射起因のブローアウト」を記載する。[scripts/run_inner_disk_suite.py:187–203][scripts/run_inner_disk_suite.py:364–380]
- `orbit_rollup.csv` を `orbit_rollup_summary.csv` に整形し、Φ=0.37 かつ T_M=2000/4000/6000 K の GIF を `runs/inner_disk_suite/animations/Phi0p37_TMXXXX.gif` として複写する。定数Φテーブルは `tables/phi_const_0p20.csv` などに配置する。[scripts/run_inner_disk_suite.py:230–243][scripts/run_inner_disk_suite.py:364–380]

## 15. 解析ユーティリティ（β・質量損失サンプラー）
- βマップ生成は `BetaSamplingConfig` の `base_config`（YAML から `Config` へ load 済み）を `sample_beta_over_orbit` が複写し、`_prepare_case_config` がケースごとに 0D 半径・温度・⟨Q_pr⟩テーブルを上書きしたうえで gas drag を強制的に無効化し、`geometry.s_min` は YAML 値のまま固定して `max(s_{min,\mathrm{config}},a_{\mathrm{blow}})` のクランプを `run_zero_d` に委譲する。[marsdisk/analysis/beta_sampler.py:91–133][marsdisk/run.py:639–646] これにより r/T だけを掃引しつつ gas-poor 条件と 1 公転 IMEX 制御（`t_end_orbits=1`,`dt_init="auto"`,`dt_over_t_blow_max`）を全ケースへ適用できる。[marsdisk/analysis/beta_sampler.py:91–133]
- `sample_beta_over_orbit` は r×T グリッドをキュー化し、`jobs>1` なら `ProcessPoolExecutor` で並列化、1 の場合は逐次実行する。[marsdisk/analysis/beta_sampler.py#sample_beta_over_orbit [L217–331]] 各 `_run_single_case` は `min_steps` 未満の時系列や `dt/t_{\rm blow}` キャップ違反を即例外化し、`dt_over_t_blow` を中央値/P90/最大にまとめて `diagnostics` へ保存する。[marsdisk/analysis/beta_sampler.py#sample_beta_over_orbit [L217–321]]  全ケース完了後は `time_grid_fraction`,`time_steps_per_orbit`,`t_orb_range_s`,`dt_over_t_blow_{median,p90,max_observed}` に加え、必要なら `example_run_config` を `diagnostics` に残しつつ `beta_cube` を返す。[marsdisk/analysis/beta_sampler.py#sample_beta_over_orbit [L274–331]]
- `sample_mass_loss_one_orbit` は単一点 (r/T) の 0D 実行を包み、`summary.json` と `series/run.parquet` から `M_out_cum`,`M_sink_cum`,`mass_loss_frac_per_orbit`,`beta_at_smin_config`,`beta_at_smin_effective`,`dt_over_t_blow_{median,p90}`, `mass_budget_max_error_percent` を再構成した辞書を返す。同一 API で `sinks.mode="none"` などの比較ケースも取得でき、`scripts/sweep_mass_loss_map.py` のような格子ドライバが直接呼び出せる。[marsdisk/analysis/massloss_sampler.py#sample_mass_loss_one_orbit [L114–263]][scripts/sweep_mass_loss_map.py:197–209]
- どちらのユーティリティも `marsdisk.io.tables.get_qpr_table_path()` を参照して実行時の ⟨Q_pr⟩ テーブルを `run_zero_d` と共有し、`run_config.json` や例外ログにパスを残す。Planck平均テーブルが遅延ロードされると `get_qpr_table_path` が解決済みパスを返し、`radiation.qpr_lookup` はこのパスを用いた β/ブローアウト評価を継続する。[marsdisk/io/tables.py#get_qpr_table_path [L356–359]][marsdisk/run.py:548–558][marsdisk/physics/radiation.py:111–116]

## 16. 将来実装プラン（0D完成→1D拡張）
- **0Dカップリングの仕上げ**: `run_zero_d` の IMEX 主ループで `prod_subblow_area_rate`,`M_out_dot`,`M_out_cum` を常時計算し、`write_parquet`/`write_summary`/`write_mass_budget_log` を経由して `series`・`summary`・`checks` へ `M_out_cum`,`M_sink_cum`,`M_loss` を揃えて記録する。`surface.step_surface_density_S1`→`sinks.total_sink_timescale`→`smol.step_imex_bdf1_C3` の順序を固定し、`mass_lost_by_blowout`・`mass_lost_by_sinks` と C4 差分を突き合わせる。[marsdisk/run.py:598–1016][marsdisk/io/writer.py:24–145][marsdisk/physics/surface.py:98–170][marsdisk/physics/sinks.py:83–160][marsdisk/physics/smol.py:104–131]
- **物理スイッチの YAML 外出し**: 昇華・ガス抗力・自遮蔽倍率・wake 係数などのトグルを `Config` モデルに追加して `configs/base.yml` から切り替え可能にし、`ALLOW_TL2003=false` を標準値として schema 検証に組み込む。`shielding` や `radiation` が legacy alias を吸収している流儀を再利用し、依存項目の整合性チェックを Pydantic validator で実装する。[marsdisk/schema.py:454–455][configs/base.yml:1–40]
- **テーブル／テスト整備**: Q_pr と Φ のロード／補間を `marsdisk/io/tables.py` に統一関数としてまとめ、テーブルの存在確認とメタデータ保存を一本化する。同時に pytest で Wyatt スケール、Blow-out 起因の wavy PSD、IMEX 収束制限を検証する 3 本のテスト（`tests/test_scalings.py`,`tests/test_mass_conservation.py`,`tests/test_surface_outflux_wavy.py`）を拡張し、CI が数値退行を先に検出できるようにする。[marsdisk/io/tables.py:22–22][tests/test_scalings.py:13–20][tests/test_mass_conservation.py:10–41][tests/test_surface_outflux_wavy.py:10–37]
- **1D拡張の受け皿**: `RadialGrid.from_edges` と `step_viscous_diffusion_C5` を `numerics.enable_viscosity` で有効化できるフックとして維持し、0D 実行でも格子初期化と粘性係数の placeholder を通す。将来 1D へ拡張するときはこのフックに演算子分割（C5）を組み込むだけで済む構成へ整える。[marsdisk/grid.py:93–94][marsdisk/physics/viscosity.py:51–134]
- **DocSync/検証フローの固定**: 変更を入れたら `python -m tools.doc_sync_agent --all --write` → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` の順に実行し、run_card（`out/<timestamp>_<title>__<shortsha>__seed<n>/run_card.md`）へコマンド・乱数種・主要ハッシュ・analysis レシピ確認結果を集約する。`analysis/run-recipes.md` には当該 run の操作手順を追加し、analysis を唯一の仕様源に保つ。

@-- BEGIN:SIO2_DISK_COOLING_ANALYSIS --
## SiO₂ 凝固優勢（距離×時間マップ）サマリ（2025-11-12 15:52 UTC）
- T0=6000K: r範囲=1.955–2.400 R_Mars (glass), 代表到達=1.657 年; 液相到達範囲=1.080–2.400 R_Mars, 代表到達=0.841 年
- T0=4000K: r範囲=1.665–2.400 R_Mars (glass), 代表到達=1.252 年; 液相到達範囲=1.000–2.400 R_Mars, 代表到達=0.265 年
- T0=2000K: r範囲=1.000–2.400 R_Mars (glass), 代表到達=0.000 年; 液相到達範囲=1.000–2.400 R_Mars, 代表到達=0.000 年
出力: siO2_disk_cooling/outputs/ 以下を参照
@-- END:SIO2_DISK_COOLING_ANALYSIS --

@-- BEGIN:PROVENANCE_OVERVIEW --
## 出典と根拠（Provenance）
- 既知キーは `analysis/references.registry.json` で正規化し、doi／bibtex／適用範囲／主張サマリを一元管理する。
- `analysis/source_map.json` はコード行→参照キーの多対多マッピングを保持し、未解決項目には `todos` 配列で slug を残す。
- `analysis/equations.md` は既知のみ `[@Key]` を付与し、未知は `TODO(REF:<slug>)` として `analysis/UNKNOWN_REF_REQUESTS.*` に連動。
@-- END:PROVENANCE_OVERVIEW --

@-- BEGIN:UNKNOWN_SOURCES_OVERVIEW --
## 未解決出典（自動）
- `analysis/UNKNOWN_REF_REQUESTS.jsonl` を GPT-5 Pro が直接読み取り、式・定数・仮定の slug ごとに探索する。
- 人が読む要約は `analysis/UNKNOWN_REF_REQUESTS.md` に出力し、優先度やコード位置を一覧化する。
- 現在の登録: `tmars_cooling_solution_v1`, `tp_radiative_equilibrium_v1`, `tl2003_surface_flow_scope_v1`（高優先:最初の2件）。
@-- END:UNKNOWN_SOURCES_OVERVIEW --

@-- BEGIN:PHYSCHECK_OVERVIEW --
## 物理チェック（自動）
- `python -m marsdisk.ops.physcheck --config configs/base.yml` が質量保存・次元解析・極限テストを一括実行し、`run_checks` で検証結果を束ねる。[marsdisk/ops/physcheck.py#run_checks [L173–181]]
- レポートは `reports/physcheck/` に JSON/Markdown で保存し、WARN/FAIL の根拠を列挙。
- DocSync 後は `make analysis-doc-tests` を実行し、`tests/test_ref_coverage.py` まで含めた検査結果を記録する。
@-- END:PHYSCHECK_OVERVIEW --
