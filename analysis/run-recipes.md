> **文書種別**: 手順（Diátaxis: How-to）

# run-recipes
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: [@Hyodo2017a_ApJ845_125; @Hyodo2017b_ApJ851_122; @Hyodo2018_ApJ860_150; @CanupSalmon2018_SciAdv4_eaar6887]。

### DocSync + ドキュメントテスト（標準手順）
- Codex や開発者が analysis/ を更新する場合は、`make analysis-sync`（DocSyncAgent）で反映した直後に `make analysis-doc-tests` を実行し、`pytest tests/test_analysis_* -q` を一括確認する。
- CI でも同じターゲットをフックできるため、分析手順の追加・改稿時は必ずこの 2 コマンドをセットで記録する。
- 解析手順を変える PR では「DocSync済み／analysis-doc-tests 済み」をチェックリストへ含めると運用が安定する。
- チャットでの簡易リクエストとして「analysisファイルを更新してください」と指示された場合は `make analysis-update`（DocSync + docテストの複合ターゲット）を必ず実行する。

## A. ベースライン実行

1) 目的
最小の0D構成で2年間のcoupled破砕–表層系を完走させ、基準となる Parquet/JSON/CSV 出力を得る。
ベースラインの質量と tidal パラメータは、リング拡散レジームで衛星列の成長が分岐すること（拡散遅→多衛星、速→単一巨大衛星）と、小衛星を残すには $M_{\rm disk}\le3\times10^{-5}M_{\rm Mars}$ かつ $(Q/k_2)<80$ が必要という制約を満たすように設定する。[\@CridaCharnoz2012_Science338_1196; @CanupSalmon2018_SciAdv4_eaar6887]

2) コマンド
```bash
python -m marsdisk.run --config configs/base.yml
```

3) 最小設定断片
```yaml
geometry:
  mode: "0D"
material:
  rho: 3000.0
sizes:
  s_min: 1.0e-6
  s_max: 3.0
numerics:
  t_end_years: 2.0
  dt_init: 10.0
io:
  outdir: "out"
```

4) 期待される出力
- `out/series/run.parquet` → `ls out/series/run.parquet`
- `out/summary.json` → `head -n 10 out/summary.json`
- `out/checks/mass_budget.csv` → `head -n 5 out/checks/mass_budget.csv`
- `out/run_config.json` → `head -n 8 out/run_config.json`

5) 確認項目
- `series/run.parquet` の列に `prod_subblow_area_rate`,`M_out_dot`,`mass_lost_by_blowout`,`mass_lost_by_sinks` に加え、`dt_over_t_blow`,`fast_blowout_factor`,`fast_blowout_flag_gt3`,`fast_blowout_flag_gt10`,`fast_blowout_corrected`,`a_blow_step`,`dSigma_dt_sublimation`,`mass_lost_sinks_step`,`mass_lost_sublimation_step`,`ds_dt_sublimation` が揃う。さらに温度ドライバ列 `T_M_used`,`rad_flux_Mars`,`Q_pr_at_smin`,`beta_at_smin`,`a_blow_at_smin` が出力されていること。供給が0のため `prod_subblow_area_rate` は機械誤差内で0に留まり、`mass_lost_by_sinks` が全行で0であれば HK シンク（`sinks.total_sink_timescale`）が `None` を返し損失項へ寄与していないことを示す。高速ブローアウト補正は既定で無効なので `fast_blowout_corrected` は `false`、閾値フラグは `dt_over_t_blow` の大小に一致する。
- `summary.json` で `case_status` が `beta_at_smin_config` と `beta_threshold` の比較に従い `blowout`（閾値以上）または `ok`（閾値未満）となっていること。加えて `orbits_completed`,`M_out_cum`,`M_sink_cum`，および `M_out_mean_per_orbit` などの公転ロールアップ指標が出力される。温度関連として `T_M_source`,`T_M_initial`,`T_M_final`,`T_M_min`,`T_M_median`,`T_M_max`,`temperature_driver` が記録され、`beta_at_smin_min`/`beta_at_smin_median`/`beta_at_smin_max` と `a_blow_min`/`a_blow_median`/`a_blow_max` が統計として付与されていることを確認する。
- `summary.json` の β関連フィールドが `beta_at_smin_config` / `beta_at_smin_effective` に分かれていること（旧 `beta_at_smin` は出力されない）。
- `summary.json` の `s_min_components` に `config`,`blowout`,`effective` が揃い、`s_min_effective` が max(config, blowout) であること。昇華設定は床粒径へは反映されず、粒径侵食による欠損は `mass_lost_sublimation_step` と `dSigma_dt_sublimation` で診断する。[marsdisk/run.py:598–1362][marsdisk/physics/psd.py:149–264]
- `orbit_rollup.csv` が生成され、各公転に対する `M_out_orbit`,`M_sink_orbit`,`M_loss_per_orbit` が累積されていること。
- `chi_blow` を `1.0` のままにすると `chi_blow_eff=1.0` がサマリに記録され、`"auto"` に切り替えると β と ⟨Q_pr⟩ に連動した補正値（0.5–2.0）が `chi_blow_eff` に入る。
- `checks/mass_budget.csv` の `error_percent` が全行で 0.5% 以下に収まり、最終行の `mass_remaining` と `mass_lost` が初期質量と合致する。
- `run_config.json` の `sublimation_provenance` に HKL 式と選択済み `psat_model`、SiO 既定値（`alpha_evap`,`mu`,`A`,`B`）、`P_gas`、`valid_K`、必要に応じて `psat_table_path`、実行半径・公転時間が保存され、同ファイルに `beta_formula`,`T_M_used`,`rho_used`,`Q_pr_used` も併記されていること。
- `diagnostics.phase7.enable=true` を指定した場合のみ、`run.parquet` に `mloss_*` と `t_coll`/`ts_ratio`、`kappa_eff`/`tau_eff`/`blowout_gate_factor` が追加され、`summary.json` に `median_gate_factor` と `tau_gate_blocked_time_fraction`、`orbit_rollup.csv` に `gate_factor_median` が出力される（デフォルトでは列追加なし）。[docs/devnotes/phase7_gate_spec.md]
- `siO2_disk_cooling/siO2_cooling_map.py` を別途実行し、(E.042)/(E.043) に従った $T_{\rm Mars}(t)$ と $T_p(r,t)$ が Hyodo et al. (2018) の式(2)–(6)と一致することを確認する。初期温度や $\bar{Q}_{\rm abs}$ を掃引し、β 閾値の境界が `out/summary.json` の `beta_at_smin_config` と `beta_at_smin_effective` に整合するかをチェックする。[\@Hyodo2018_ApJ860_150]
- 化学・相平衡フラグを有効化した runs では、気相凝縮と溶融固化物の化学差（Pignatale et al. 2018）および外縁ガス包絡での凝縮スペクトル（Ronnet et al. 2016）によって HKL パラメータや` t_sink`が設定されていることを `sinks.total_sink_timescale` のログで確認する。[\@Pignatale2018_ApJ853_118; @Ronnet2016_ApJ828_109]

- CLI は `python -m marsdisk.run --config …` を受け取り、0D実行を呼び出す。[marsdisk/run.py:598–1362]
- 0Dケースの軌道量は `omega` と `v_kepler` が `runtime_orbital_radius_m` から導出し、ブローアウト時間や周速度評価の基礎となる。[marsdisk/grid.py:90][marsdisk/grid.py:34]
- 出力として `series/run.parquet`,`summary.json`,`checks/mass_budget.csv`,`run_config.json` を書き出す。[marsdisk/run.py:598–1362][marsdisk/run.py:598–1362][marsdisk/run.py:598–1362][marsdisk/run.py:598–1362]
- タイムシリーズのレコード構造に上記カラムを追加し、損失項と高速ブローアウト診断を分離して記録する。[marsdisk/run.py:598–1362][marsdisk/run.py:598–1362][marsdisk/run.py:598–1362]
- 供給が定数モード0のため生成率は0で、ミキシング後もクリップされる。(configs/base.yml)[marsdisk/physics/supply.py:69–90]
- 質量収支許容値と違反時の処理を 0.5% で定義している。[marsdisk/run.py:64][marsdisk/run.py:598–1362][marsdisk/run.py:598–1362]
- `run_config.json` に式と使用値を格納している。[marsdisk/run.py:598–1362]

### 派生レシピ: `analysis/run-recipes/baseline_blowout_only.yml`
- 実行例
```bash
python -m marsdisk.run --config analysis/run-recipes/baseline_blowout_only.yml
```
- 確認ポイント
  - `series/run.parquet` に `mass_lost_by_sinks` 列が存在し、総和が0（`sinks.mode: none` による HK シンク対照）。[marsdisk/run.py:598–1362]（参考: `tests/test_sinks_none.py`）
  - 列構成はベースラインと同じで、`dt_over_t_blow` や `fast_blowout_factor` も一致し、`fast_blowout_corrected` は常に `false`。`n_substeps` が 1 であることを確認し、サブステップ分割が無効であることを確かめる。
  - `checks/mass_budget.csv` の `error_percent` が 0.5% 以下。[marsdisk/run.py:598–1362]
- YAMLを書き換えず同条件を試す場合は CLI で `--sinks none` を付与する（例：`python -m marsdisk.run --config configs/base.yml --sinks none`）。

### 派生レシピ: 昇華シンクを有効にする
- 実行例
```bash
python -m marsdisk.run --config analysis/run-recipes/baseline_blowout_only.yml --sinks sublimation
```
- 最小設定断片（`sub_params` は設定済み値を尊重）
```yaml
sinks:
  mode: "sublimation"
  enable_sublimation: true
  sub_params:
    mode: "hkl"
    psat_model: "clausius"    # "tabulated" に切り替えると CSV/JSON を参照
    alpha_evap: 0.007         # SiO over Si+SiO2 (Ferguson & Nuth 2012)
    mu: 0.0440849             # kg/mol（NIST WebBook: SiO）
    A: 13.613                 # log10(P_sat/Pa) = A - B/T（Kubaschewski 1974）
    B: 17850.0
    valid_K: [1270.0, 1600.0]
    P_gas: 0.0
```
- 確認ポイント
  - `series/run.parquet` の `mass_lost_by_blowout` と `mass_lost_by_sinks` が別カラムで積算され、昇華オンのステップで `mass_lost_by_sinks` が増加する（HK シンクが有限 `t_sink` を返した証拠）。[marsdisk/physics/sinks.py:83–160][marsdisk/run.py:598–1362]
  - `fast_blowout_factor` や `fast_blowout_flag_gt3/gt10` は昇華の有無に関係なく出力される。高速補正を有効化したい場合は YAML の `io.correct_fast_blowout: true` を追加し、補正適用時に `fast_blowout_corrected` が `true` へ切り替わることを確認する。
  - `summary.json` の `s_min_components` に昇華キーが存在せず（`config`,`blowout`,`effective` のみ）、`s_min_effective` が max(config, blowout) を保つこと。[marsdisk/run.py:598–1362]
    昇華境界は `s_min_evolved` 列で追跡され、床粒径の決定には反映されない。
  - `run_config.json` の `sublimation_provenance` に HKL 選択と SiO パラメータ、`psat_model`、`valid_K`、タブレット使用時のファイルパスがまとまり、実行半径・公転時間とともに再現条件が残る。

### 派生レシピ: サブステップで高速ブローアウトを解像する
- 実行例
```bash
python -m marsdisk.run --config configs/base.yml --set io.substep_fast_blowout=true --set io.substep_max_ratio=1.0
```
- 確認ポイント
  - `series/run.parquet` の `n_substeps` が 1 を超えるステップが存在し、`dSigma_dt_*` 列がサブステップ分割後の表層レートを報告している。
  - `M_out_dot_avg` / `M_sink_dot_avg` / `dM_dt_surface_total_avg` を `dt` と掛け合わせた積分値が、それぞれ `mass_lost_by_blowout` / `mass_lost_by_sinks` / `M_loss_cum + mass_lost_by_sinks` と一致する。
- 補足
  - `io.substep_max_ratio` は `dt/t_{\rm blow}` の閾値で、既定 1.0。より厳しい解像が必要であれば 0.5 などに下げる。
  - サブステップと `io.correct_fast_blowout` は併用可能であり、補正を維持したまま時間分割による安定性を向上させられる。

### 派生レシピ: 最小粒径進化フックを有効にする
- 実行例
  - `configs/base.yml` を複製し、`sizes.evolve_min_size: true` と `sizes.dsdt_model: noop`（任意の識別子）を追加する。
  - `python -m marsdisk.run --config path/to/custom.yml`
- 確認ポイント
  - `series/run.parquet` に `s_min_evolved` 列が追加され、`sizes.evolve_min_size=true` とした場合のみ値が入る（デフォルトでは列ごと非表示）。
  - `summary.json` の `s_min_components` は `config`,`blowout`,`effective` のままであり、`s_min_effective` は常に max(config, blowout)。
    `s_min_evolved` はタイムシリーズ列として記録され、昇華 `ds/dt` の診断情報のみを提供する。

### 派生レシピ: Step18 供給 vs ブローアウト診断行列
- 実行例
```bash
python diagnostics/minimal/run_minimal_matrix.py
```
- 生成物
  - `diagnostics/minimal/results/supply_vs_blowout.csv` に 5 半径 × 3 温度 × 3 ブローアウト制御（補正OFF/ON、サブステップON）の45行がまとまり、各ケースの最終 `Omega_s`,`t_blow_s`,`dt_over_t_blow`,`dSigma_dt_blowout`,`blowout_to_supply_ratio` が揃う。
  - `diagnostics/minimal/results/supply_vs_blowout_reference_check.json` が `analysis/radius_sweep/radius_sweep_metrics.csv` (T=2500 K, baseline) との照合を <1e-2 の相対誤差で記録し、数値逸脱が無いことを確認する。
  - ヒートマップ `diagnostics/minimal/plots/supply_vs_blowout.png` が `figures/` にも複製され、`blowout_to_supply_ratio ≳ 1` がブローアウト支配域として示される。
  - 各実行結果は `diagnostics/minimal/runs/<series>/<case_id>/` 配下に展開され、`series/run.parquet` 末尾行から `dSigma_dt_*` 列と `fast_blowout_factor_avg` を取得できる。
- 確認ポイント
  - ベースライン系列 (`series="baseline"`) で `fast_blowout_corrected` が常に `false`、`n_substeps=1` であること。
  - 補正ON系列では `fast_blowout_corrected` が `dt/t_blow>1` のステップで `true` になり、`fast_blowout_factor_avg` が `1-exp(-dt/t_blow)` に一致する。
  - サブステップ系列では `n_substeps>1` のステップが現れ、`dt_over_t_blow` が `io.substep_max_ratio` 未満まで分割されている。
  - reference_check で `within_tol` が全件 `true`。NaN を含む指標はスキップされる仕様（`diagnostics/minimal/run_minimal_matrix.py`）。

### 派生レシピ: 内側ロッシュ円盤 Φ×温度スイート
- 実行例
```bash
python scripts/run_inner_disk_suite.py --config configs/base.yml --skip-existing
```
- 期待される生成物
  - `runs/inner_disk_suite/phi_0p37/TM_2000/series/psd_hist.parquet` に `(time, bin_index, s_bin_center, N_bin, Sigma_surf)` が保存される。
  - `runs/inner_disk_suite/phi_0p37/TM_2000/figs/frame_0000.png` などが生成され、左下に「惑星放射起因のブローアウト」が明記される。
  - `runs/inner_disk_suite/phi_0p37/TM_2000/animations/psd_evolution.gif` が追加され、Φ=0.37 かつ T_M=2000/4000/6000 K の GIF が `runs/inner_disk_suite/animations/` に複写される。
  - `runs/inner_disk_suite/phi_0p37/TM_2000/orbit_rollup_summary.csv` が派生する。
    公転ごとの集計列 `mass_blowout_Mmars` を確認し、吹き飛び質量の単位換算が期待どおりかをチェックする。
- 確認ポイント
  - `summary.json` の `phi_table_path` と `shielding_mode` が `shielding.table_path` と `mode=table` の正規化結果を保持する。[marsdisk/run.py:1430–1452]
  - `psd_hist.parquet` 内の `bin_index` が昇順で、`s_bin_center` と `N_bin` が PNG/GIF のプロットと一致する。[marsdisk/run.py:1281–1297]
  - GIF 生成ルーチンが `figs/frame_*.png` を束ね、Φ=0.37 の指定温度ではハイライト GIF をベースディレクトリへ複写する。[scripts/run_inner_disk_suite.py:187–203][scripts/run_inner_disk_suite.py:364–380]
  - `orbit_rollup_summary.csv` は `orbit_rollup.csv` の `M_out_orbit` を引き継ぎ、注釈用に `time_s_end` を付与する。[scripts/run_inner_disk_suite.py:187–209]
    ここで `mass_blowout_Mmars` 列がマルス質量換算の再出力である点を確認する。
- 根拠
  - 公転周期・オーバーライドの構築は `build_cases` / `build_overrides` が担い、Φ定数テーブルを `tables/phi_const_*.csv` から解決する。[scripts/run_inner_disk_suite.py:78–79][scripts/run_inner_disk_suite.py:230–259]
  - PSD 可視化と GIF 生成は `render_psd_frames` と `make_gif` が担当し、凡例テキストを固定で描画する。[scripts/run_inner_disk_suite.py:187–203]
  - 公転集計は `export_orbit_summary` が整形し、ハイライト GIF の複写処理はメインループ終端で実行される。[scripts/run_inner_disk_suite.py:187–209][scripts/run_inner_disk_suite.py:364–380]

## B. スイープ

1) 目的
`sweep_heatmaps.py` を用いて主要パラメータ (例: `r` と `T_M`) の格子を安全に周回し、ケース別出力と集約CSVを生成する。

2) コマンド
```bash
python scripts/sweep_heatmaps.py --map 1 --outdir sweeps/map1_demo --jobs 4
```

3) 最小設定断片
```yaml
geometry: { mode: "0D", r: 1.5e7 }
temps:    { T_M: 2000.0 }
supply:   { mode: "const", const: { prod_area_rate_kg_m2_s: 1.0e-8 } }
numerics: { t_end_years: 0.01, dt_init: 1.0e4 }
io:       { outdir: "sweeps/__will_be_overwritten__" }
```

4) 期待される出力
- `sweeps/map1_demo/map1/*/config.yaml` → `ls sweeps/map1_demo/map1 | head`
- `sweeps/map1_demo/map1/*/out/summary.json` → `find sweeps/map1_demo/map1 -path '*/out/summary.json' | head`
- `sweeps/map1_demo/map1/*/out/case_completed.json` → `find sweeps/map1_demo/map1 -name case_completed.json | head`
- `results/map1.csv` → `head -n 5 results/map1.csv`

5) 確認項目
- 各 `config.yaml` に `geometry.r` と `temps.T_M` が軸値で上書きされていること。
- 生成された `out/summary.json` / `out/series/run.parquet` が各ケースごとに存在し、`case_status` や `s_min_effective` が反映されていること。
- `case_completed.json` が各ケースの `out/` に置かれ、タイムスタンプと `summary`/`series` パスが記録されていること。
- `results/map1.csv` に `map_id`,`case_id`,`total_mass_lost_Mmars`,`run_status`,`case_status` が揃い、行順が `order` で整列していること。
- `scripts/analyze_radius_trend.py` を実行した場合は `analysis/radius_sweep/radius_sweep_metrics.csv` に `Omega_s`,`t_orb_s`,`dt_over_t_blow`,`fast_blowout_factor`,`fast_blowout_flag_gt3/gt10` が追加され、警告ログに `dt/t_blow` の閾値超過ケースが列挙されること。

6) 根拠
- スイープCLI引数とベース設定のデフォルトを `DEFAULT_BASE_CONFIG` と `parse_args` が提供し、マップ仕様は `create_map_definition` で組み立てる。[scripts/sweep_heatmaps.py:47][scripts/sweep_heatmaps.py:246–402][scripts/sweep_heatmaps.py:445–550]
- ケースごとに `geometry.r`,`temps.T_M`,`io.outdir` を設定し、設定ファイルと出力先を準備して `run_case` へ渡す処理を `build_cases` と `run_case` が担う。[scripts/sweep_heatmaps.py:686–739][scripts/sweep_heatmaps.py:1143–1249]
- 出力を読み込み `case_status` や `s_min_effective` を抽出する処理は `_get_beta_for_checks`,`extract_smin_from_series`,`populate_record_from_outputs` が担当する。[scripts/sweep_heatmaps.py:786–812][scripts/sweep_heatmaps.py:815–823][scripts/sweep_heatmaps.py:826–846][scripts/sweep_heatmaps.py:1029–1140]
  事前の JSON 読み出しは `parse_summary` がまとめ、上記ヘルパーへ辞書を受け渡す。
- 完了フラグ `case_completed.json` の生成と再実行判定は `mark_case_complete` と `case_is_completed` で実装される。[scripts/sweep_heatmaps.py:639–653][scripts/sweep_heatmaps.py:656–661]
- 集約CSVの出力は `_results_dataframe` と `main` 内の集計ロジックで行い、`total_mass_lost_Mmars` などを整形して保存する。[scripts/sweep_heatmaps.py:1252–1258][scripts/sweep_heatmaps.py:1261–1524]

### 感度掃引（質量損失サンプラー連携）

1) 目的  
`sample_mass_loss_one_orbit` と `scripts/sweep_mass_loss_map.py` を併用し、1公転あたりの質量損失マップ（`M_out_cum`,`M_sink_cum`,`mass_loss_frac_per_orbit`）を gas-poor 既定や比較モード（例: `sinks.mode="none"`）で掃引する。タイムシリーズとサマリを読み直して `dt_over_t_blow_{median,p90}` や `mass_budget_max_error_percent` を同じ CSV に詰め、感度試験の仕様を analysis に集約する。

2) コマンド  
```bash
python scripts/sweep_mass_loss_map.py \
  --base-config configs/base.yml \
  --qpr-table data/qpr_table.csv \
  --rRM 2.1 2.9 5 \
  --TM 2000 2600 4 \
  --outdir sweeps/massloss_demo \
  --jobs 4 \
  --dt-over-tblow-max 0.05 \
  --include-sinks-none \
  --override temps.T_M=2400 numerics.dt_init=auto sinks.mode=sublimation \
  --override supply.const.prod_area_rate_kg_m2_s=5e-9 material.rho=2900
```
Python から直接呼ぶ場合は `sample_mass_loss_one_orbit(..., sinks_mode="sublimation", enable_sublimation=True, enable_gas_drag=False)` のように明示する。

3) 最小設定断片  
- ベース YAML（0D gas-poor）と Planck 平均 ⟨Q_pr⟩ テーブル。  
- サンプラーのシンク切替は `sinks_mode`（例: `"sublimation"`, `"none"`, `"gas_drag"`）、`enable_sublimation`、`enable_gas_drag` の3引数で制御する。`enable_sublimation=None` の場合は `sinks_mode=="sublimation"` に合わせて自動化され、gas-rich 感度を取りたいときだけ `enable_gas_drag=True` を指定する。[marsdisk/analysis/massloss_sampler.py:28–78]  
- `dt_over_t_blow_max` は 0.05–0.1 以内で指定し、`scripts/sweep_mass_loss_map.py` 側では `--dt-over-tblow-max` フラグから各サンプルに伝播する。[scripts/sweep_mass_loss_map.py:36–36][scripts/sweep_mass_loss_map.py:302–325]

4) 期待される出力  
- `map_massloss.csv`：各 (r_RM, T_M) 行に `M_out_cum`, `M_sink_cum`, `M_loss_cum`, `mass_loss_frac_per_orbit`, `dt_over_t_blow_{median,p90}`, `mass_budget_max_error_percent`, `beta_at_smin_{config,effective}`, `sinks_mode`, `qpr_table_path` が入る。`--include-sinks-none` を付けると `nosinks_mass_loss_frac_per_orbit` など接頭辞列が加わる。  
- `logs/spec.json`：採用した格子、`dt_over_t_blow` の全体統計、`mass_loss_frac_{min,max,median}`、入力 YAML/テーブルパスを記録する。[scripts/sweep_mass_loss_map.py:197–235]  
- 直接サンプル時は `dict` が返り、質量損失・dt統計・`mass_budget_max_error_percent`・`dt_over_t_blow_requirement_pass` をキーで参照できる。

5) 確認項目  
- `sample_mass_loss_one_orbit` は一時 outdir に `summary.json` と `series/run.parquet` を生成し、累積 `M_out_cum`,`M_sink_cum` が欠損した場合は最終行の `mass_lost_by_*` を読み出す。`checks/mass_budget.csv` の `|error_percent|` 最大値が 0.5% 未満であることを `mass_budget_max_error_percent` から確認する。[marsdisk/analysis/massloss_sampler.py:174–259]  
- `dt_over_t_blow_requirement_pass` が `True` でも、中央値・p90 が `--dt-over-tblow-max` を超えないか `map_massloss.csv` 側で再確認する。  
- `--override` は `PATH=VALUE` をスペース区切りで並べる書式で、`PATH` は `temps.T_M` のようなドット区切り、`VALUE` は bool/数値/quoted string を自動解釈する。複数指定する場合は `--override ... --override ...` と繰り返すか、単一フラグに複数パラメータを与える。解析側では `_apply_overrides_dict` が YAML dict にマージするため、r/T の固定や追加のシンク係数を安全に上書きできる。[scripts/sweep_mass_loss_map.py:302–325][marsdisk/run.py:136–137]  
- gas drag 感度を取る場合は Python サンプリングで `enable_gas_drag=True` を渡し、`result["sinks_mode"]` が意図どおり変わっているか `map_massloss.csv` もしくは辞書出力で確認する。  

6) 根拠  
- サンプラーはベース `Config` をディープコピーして r/T/⟨Q_pr⟩/シンク設定/`dt_over_t_blow_max` を上書きし、1公転のみ `run_zero_d` を回す。`summary.json` と `series/run.parquet` を読み直し、`M_out_cum`,`M_sink_cum`,`mass_loss_frac_per_orbit`,`beta_at_smin_config`,`beta_at_smin_effective`,`dt_over_t_blow_{median,p90}`、質量収支誤差をまとめた辞書を返す。[marsdisk/analysis/massloss_sampler.py:114–263]  
- `scripts/sweep_mass_loss_map.py` は全格子に対して同サンプラーを呼び出し、必要に応じて `sinks.mode="none"` 比較も実行したうえで `map_massloss.csv` と `logs/spec.json` を生成する。dt 比や質量収支統計を `spec.json` に追記し、CLI フラグ (`--dt-over-tblow-max`,`--override`) を各呼び出しへ伝搬させる。[scripts/sweep_mass_loss_map.py:25–25]

## C. 再開・再実行

1) 目的
途中停止したスイープや既存0D出力を維持したまま安全に再開・再実行する。

2) コマンド
```bash
python scripts/sweep_heatmaps.py --map 1 --outdir sweeps/map1_demo --jobs 2
# 個別ケースを再計算する場合は case_completed.json を削除してから同コマンドを再実行
rm sweeps/map1_demo/map1/rRM_1.0__TM_1000/out/case_completed.json
python scripts/sweep_heatmaps.py --map 1 --outdir sweeps/map1_demo --jobs 1
# 既存0D出力を保全したい場合は新しい outdir を指定して単発実行
python -m marsdisk.run --config configs/base.yml --enforce-mass-budget
```

3) 最小設定断片
```yaml
io:
  outdir: "runs/2025-02-01"
```

4) 期待される出力
- `sweeps/map1_demo/map1/*/out/case_completed.json` → `find sweeps/map1_demo/map1 -name case_completed.json | head`
- 再計算したケースの `case_completed.json` が新しい `timestamp` を持つ → `head -n 5 sweeps/map1_demo/map1/rRM_1.0__TM_1000/out/case_completed.json`
- 新 outdir の単発実行結果 → `ls runs/2025-02-01/summary.json`

5) 確認項目
- 既存ケースは `case_is_completed` により `run_status: cached` でスキップされることを `results/map1.csv` で確認する。
- `case_completed.json` を削除したケースのみ再度 `run_status: success` で上書きされること。
- `writer.write_*` は同じ outdir を上書きするため、過去結果を保持したい場合は設定で outdir を切り替えること。
- `--enforce-mass-budget` を付与すると許容超過時に早期終了するため、再開前に質量収支を把握しておくこと。

6) 根拠
- ケース再利用時の `case_is_completed` 判定と `run_status` 更新ロジック。[scripts/sweep_heatmaps.py:656–661][scripts/sweep_heatmaps.py:1143–1249]
- 完了フラグ削除後は再実行し、新たなフラグと出力を生成する。[scripts/sweep_heatmaps.py:639–653][scripts/sweep_heatmaps.py:1143–1249][scripts/sweep_heatmaps.py:1261–1524]
- 単発実行は `io.outdir` に書き込み、既存内容を上書きする。[marsdisk/run.py:598–1362]
- CLI フラグ `--enforce-mass-budget` で許容超過時に例外を送出する。[marsdisk/run.py:598–1362]

## D. 同定可能性チェック

1) 目的
`summary.json` の累積損失 `M_loss` を取り出す。
タイムシリーズ最終行の `M_loss_cum` と照合し、差分を手元で検算する。

2) コマンド
```bash
python -c "import json,pandas as pd; s=json.load(open('out/summary.json'))['M_loss']; df=pd.read_parquet('out/series/run.parquet'); print(f'delta={abs(df.M_loss_cum.iloc[-1]-s):.3e}')"
```

3) 最小設定断片
```yaml
sinks:
  enable_sublimation: false
  enable_gas_drag: false
```

4) 期待される出力
- 差分表示 → `delta=0.000e+00` 付近の数値が出れば一致確認完了
- タイムシリーズ確認用 → `python -c "import pandas as pd; print(pd.read_parquet('out/series/run.parquet').tail(1))"`

5) 確認項目
- `delta` が 1e-10 以下であれば数値一致とみなす。
- `mass_lost_by_sinks` 最終値が 0 に近いこと（シンク無効のため）。
- `mass_total_bins` 最終値が `initial.mass_total - M_loss` に一致すること。

6) 根拠
- `summary.json` の `M_loss` は `M_out_cum + M_sink_cum` を記録する。[marsdisk/run.py:598–1362]
- タイムシリーズ `M_loss_cum`,`mass_lost_by_blowout`,`mass_lost_by_sinks`,`mass_total_bins` の更新式。[marsdisk/run.py:598–1362]
- シンク無効設定は昇華・ガス抗力を停止させる。(configs/base.yml)[marsdisk/schema.py:202–204]

## E. トラブルシュート

1) 目的
既知の依存欠如・設定不足・数値ガードに起因する失敗を事前に回避する。

2) コマンド
```bash
# Parquet 書き出しで pyarrow が未導入の場合
pip install pyarrow
# 実行時に幾何半径や質量収支を検査
python -m marsdisk.run --config configs/base.yml --enforce-mass-budget
```

3) 最小設定断片
```yaml
geometry:
  r: 5.0e6  # 0Dでは必須
supply:
  mode: "const"
  const: { prod_area_rate_kg_m2_s: 0.0 }
```

4) 期待される出力
- Parquet 正常化確認 → `python -c "import pandas as pd; pd.read_parquet('out/series/run.parquet').head()"`
- 半径未指定エラー回避後の再実行 → エラーログが消え通常の `summary.json`

5) 確認項目
- `pyarrow` が無いと `df.to_parquet(..., engine="pyarrow")` で ImportError になるため事前に導入する。
- `geometry.r` が未指定だと 0D 実行で `ValueError` になるので、必ず `r` か `disk.geometry` を与える。
- `Supply.mode: table` を使う際は `path` のCSVを設置する。無い場合は `const` モードに戻す。
- `s_min` が `s_max` を上回ると 0.9倍のクランプが入り、意図しない下限になる。設定値の整合を事前に確認する。

6) 根拠
- Parquet書き出しが `pyarrow` 依存である。[marsdisk/io/writer.py:20–21]
- 0D実行は `geometry.r` 未指定時に例外を送出する。[marsdisk/run.py:466–468]
- 供給テーブル読込は `pd.read_csv` でパスが必要。[marsdisk/physics/supply.py:25–63]
- `s_min` が `s_max` を超えると 0.9倍に補正して警告する。[marsdisk/run.py:598–1362]

## F. SiO psat auto-selector と HKLフラックスの最小検証

1) 目的  
`psat_model="auto"` がタブレット／局所Clausius／既定Clausiusを正しく切り替え、HKLフラックスが温度に対して単調・非負であることを最小構成で確認する。

2) コマンド
```bash
# SiO表データ生成（既に存在する場合は再実行不要）
PYTHONPATH=. python analysis/checks_psat_auto_01/make_table.py
# 3ケース実行（tabulated / local-fit / clausius fallback）
PYTHONPATH=. python -m marsdisk.run --config analysis/checks_psat_auto_01/inputs/case_A_tabulated.yml
PYTHONPATH=. python -m marsdisk.run --config analysis/checks_psat_auto_01/inputs/case_B_localfit.yml
PYTHONPATH=. python -m marsdisk.run --config analysis/checks_psat_auto_01/inputs/case_C_clausius.yml
# HKL温度掃引 + 安全性アサーション
PYTHONPATH=. python analysis/checks_psat_auto_01/scan_hkl.py
# 対応ユニットテスト
PYTHONPATH=. pytest -q tests/test_sublimation_sio.py -q
```

3) 最小設定断片
- 0D幾何と40ビンPSD、供給0。`sinks.sub_params.psat_model: "auto"`、`psat_table_path` はケースA/BでCSV指定、ケースCでは未指定。
- SiO物性は (α=7×10⁻³, μ=4.40849×10⁻² kg mol⁻¹, A=13.613, B=17850, P_gas=0) を `SublimationParams` 既定値から流用する。[analysis/checks_psat_auto_01/inputs/case_A_tabulated.yml][marsdisk/physics/sublimation.py:127–135]

4) 期待される出力
- `analysis/checks_psat_auto_01/runs/case_*/series/run.parquet` → `python -c "import pandas as pd; print(pd.read_parquet('analysis/checks_psat_auto_01/runs/case_A_tabulated/series/run.parquet').head())"`
- `analysis/checks_psat_auto_01/runs/case_*/run_config.json` の `psat_model_resolved` が順に `tabulated`／`clausius(local-fit)`／`clausius(baseline)` になる。→ `jq '.sublimation_provenance.psat_model_resolved' analysis/checks_psat_auto_01/runs/case_B_localfit/run_config.json`
- `analysis/checks_psat_auto_01/scans/hkl_assertions.json` の `monotonic`, `finite`, `nonnegative` がすべて `true`。
- `analysis/checks_psat_auto_01/scans/psat_provenance.json` に resolved モデル、A/B係数、valid_K、表範囲がまとまる。
- `analysis/checks_psat_auto_01/logs/pytest_sio.log` が全テスト成功を示す。

5) 確認項目
- `run_config.json` の `valid_K_active` と `psat_table_range_K` がケースごとの温度に応じて更新されている。[marsdisk/physics/sublimation.py:525–531]
- `case_B_localfit` の `run.log` で局所フィット適用メッセージ（`psat auto: requested temperature ... using local Clausius fit.`）が出力される。
- `scan_hkl.py` が各ケースで91サンプルを出力し、最小／最大フラックスが ~1e-4–1e5 kg m⁻² s⁻¹ に収まる。
- `tests/test_sublimation_sio.py` が pass し、HKL実装とauto-selector回帰が保たれている。

6) 根拠
- psatテーブルは Clausius式 `log10 P = A - B/T` から生成し、PCHIP補間にロードする。[analysis/checks_psat_auto_01/make_table.py][marsdisk/physics/sublimation.py:219–227]
- auto-selector はタブレット範囲内で内挿、それ以外で局所最小二乗フィットまたは既定係数にフォールバックする。[marsdisk/physics/sublimation.py:486–494][marsdisk/physics/sublimation.py:326–334]
- HKLフラックスは `mass_flux_hkl` が評価し、`scan_hkl.py` で同式を再計算して温度スキャンを行う。[marsdisk/physics/sublimation.py:576–584][analysis/checks_psat_auto_01/scan_hkl.py]
- 出力ファイル群は既存の writer 実装に従って Parquet/JSON/CSV として保存される。[marsdisk/io/writer.py:24–162]

## G. 解析ユーティリティ（β・質量損失マップ）

### レシピ: `sample_beta_over_orbit` で β(r, T, t) を取得

1) 目的  
`BetaSamplingConfig` を介して r/R_M × T_M 格子を一括実行し、`beta_cube` と `diagnostics`（`time_grid_fraction`, `dt_over_t_blow_*` など）を得る。

2) コマンド  
```bash
python - <<'PY'
from pathlib import Path
from marsdisk.run import load_config
from marsdisk.analysis import BetaSamplingConfig, sample_beta_over_orbit

cfg = load_config(Path("configs/base.yml"))
sampler = BetaSamplingConfig(
    base_config=cfg,
    r_values=[2.2, 2.6],
    T_values=[2000.0, 2500.0],
    qpr_table_path=Path("data/qpr_table.csv"),
    jobs=2,
    min_steps=120,
    dt_over_t_blow_max=0.1,
)
r_vals, T_vals, frac, beta_cube = sample_beta_over_orbit(sampler)
print(f"grid={r_vals.size*T_vals.size}, steps={frac.size}")
print(sampler.diagnostics["dt_over_t_blow_median"])
PY
```

3) 最小設定断片  
- 0DベースYAML（`configs/base.yml`）と `data/qpr_table.csv`。  
- `BetaSamplingConfig` に `jobs=1` 以上、`min_steps>=100` を渡す。  
- `dt_over_t_blow_max` は既定 0.1 を推奨。
- YAML は `marsdisk.run.load_config` などで `Config` に変換し、その写像を `_prepare_case_config` が各 (r,T) サンプル用に 0D 半径・温度・⟨Q_pr⟩テーブルへ上書きしつつ `geometry.s_min` を動かさず gas drag を強制無効化するため、元 YAML の物理スイッチが汚染されない。[marsdisk/analysis/beta_sampler.py:91–133][marsdisk/run.py:639–646]

4) 期待される出力  
- `beta_cube.shape == (len(r_values), len(T_values), len(time_grid_fraction))`。  
- `sampler.diagnostics` に `time_grid_fraction`, `time_grid_s_reference`, `time_steps_per_orbit`, `t_orb_reference_s`, `t_orb_range_s`, `dt_over_t_blow_{median,p90,max_observed}`, `qpr_used_stats`, `example_run_config` が入る。  
- 先頭ケースの `run_config` が `diagnostics["example_run_config"]` に保存される。

5) 確認項目  
- `sampler.diagnostics["qpr_used_stats"]["samples"] == len(r_values)*len(T_values)` で各格子の ⟨Q_pr⟩ が再評価されていること。  
- `example_run_config["run_inputs"]["Q_pr_used"]` が `data/qpr_table.csv` の補間値（`tables.get_qpr_table_path()` が返すパス）と一致する。  
- `dt_over_t_blow_median` と `dt_over_t_blow_p90` が 0.1 未満で IMEX 安定条件を満たす。

6) 根拠  
- βサンプラーは YAML→`Config` 変換後のオブジェクトを深いコピーし、`_prepare_case_config` が 0D 半径・温度・⟨Q_pr⟩テーブルを書き換えつつ gas drag を落とし、`geometry.s_min` を固定したまま `max(s_{\min,{\rm cfg}},a_{\rm blow})` のクランプに任せる。[marsdisk/analysis/beta_sampler.py:91–133][marsdisk/run.py:639–646]
- `BetaSamplingConfig.jobs` と `min_steps` は `sample_beta_over_orbit` 内で `ProcessPoolExecutor(max_workers=jobs)` の並列度および各 `_run_single_case` の最小タイムステップ数を規制し、`dt_over_t_blow_max` の伝播もここで行う。[marsdisk/analysis/beta_sampler.py:217–256]
- `diagnostics` には `time_grid_fraction`, `time_grid_s_reference`, `time_steps_per_orbit`, `t_orb_reference_s`, `t_orb_range_s`, `dt_over_t_blow_{median,p90,max_observed}`, `qpr_used_stats`, `example_run_config` が格納される。[marsdisk/analysis/beta_sampler.py:274–331]
- 実行中に解決されたテーブルパスは `tables.get_qpr_table_path()` と `run_zero_d` が共有する。[marsdisk/io/tables.py:356–359][marsdisk/run.py:548–558]

### レシピ: `sample_mass_loss_one_orbit` で単点質量損失を取得

1) 目的  
単一の (r/R_M, T_M) について 1 周期分の 0D 進化を行い、`M_out_cum`, `M_sink_cum`, `mass_loss_frac_per_orbit`, `beta_at_smin_*`, `dt_over_t_blow_{median,p90}` を即時取得する。

2) コマンド  
```bash
python - <<'PY'
from pathlib import Path
from marsdisk.analysis import sample_mass_loss_one_orbit

result = sample_mass_loss_one_orbit(
    r_RM=2.4,
    T_M=2500.0,
    base_yaml=Path("configs/base.yml"),
    qpr_table=Path("data/qpr_table.csv"),
    dt_over_t_blow_max=0.1,
    sinks_mode="sublimation",
    enable_sublimation=True,
    enable_gas_drag=False,
)
print(result["M_out_cum"], result["M_sink_cum"], result["qpr_table_path"])
PY
```

3) 最小設定断片  
- ベース YAML と ⟨Q_pr⟩ CSV。  
- `sinks_mode` は `"sublimation"`（既定 gas-poor）か `"none"` を選択し、対応する `enable_sublimation` フラグを合わせる。  
- `dt_over_t_blow_max` は 0.1 以下、`overrides` で半径や温度を追加上書きしても良い。

4) 期待される出力  
- `M_out_cum`, `M_sink_cum`, `M_loss_cum`, `mass_loss_frac_per_orbit`, `beta_at_smin_config`, `beta_at_smin_effective`, `dt_over_t_blow_{median,p90}`, `mass_budget_max_error_percent`, `qpr_table_path` を含む辞書。  
- `dt_over_t_blow_requirement_pass` が `True`（中央値≤0.05）か `False/NaN` の判定。  
- `sinks_mode` が結果にエコーされ、比較ケースを識別できる。

5) 確認項目  
- `result["qpr_table_path"]` が入力 CSV の絶対パスに解決され、`tables.get_qpr_table_path()` が返す値と一致する。  
- `mass_budget_max_error_percent < 0.5` を満たし、`scripts/sweep_mass_loss_map.py` でグリッド走査する際の健全性指標に流用できる。  
- `beta_at_smin_config` と `case_status` の整合を `summary.json` と照合しておく。

6) 根拠  
- サンプラーは YAML を読み込んで 0D 設定を複製し、r/T・シンク制御・`dt_over_t_blow_max` を上書きしたうえで `run_zero_d` を 1 周期だけ回す。[marsdisk/analysis/massloss_sampler.py#sample_mass_loss_one_orbit [L114–180]]  
- `summary.json` と `series/run.parquet` から累積損失や `dt_over_t_blow` 統計を再構成し、`mass_budget_max_error_percent` や `qpr_table_path` を転記する。[marsdisk/analysis/massloss_sampler.py#sample_mass_loss_one_orbit [L181–263]]  
- `scripts/sweep_mass_loss_map.py` は格子ごとに本APIを呼び、比較モード（`sinks.mode="none"`）の追加列もこの辞書へ接頭辞付きで結合する。[scripts/sweep_mass_loss_map.py:197–209]

## H. ドキュメント coverage ガード

1) 目的  
新規コードやドキュメント追加時に関数参照率 < 0.75 のまま放置されないよう、`agent_test.ci_guard_analysis` を手元・CI 双方で自動実行する。

2) コマンド  
```bash
# make ターゲット経由
make analysis-coverage-guard
# もしくは pytest 実行時に自動で走るテスト
pytest tests/test_analysis_coverage_guard.py -q
```

3) 内容  
- `make analysis-coverage-guard` は `python -m agent_test.ci_guard_analysis --coverage analysis/coverage/coverage.json --refs analysis/doc_refs.json --inventory analysis/inventory.json --fail-under 0.75 --require-clean-anchors` をラップし、関数参照率とアンカー整合性を同時に検証する。[Makefile:analysis-coverage-guard [L21–L24]][agent_test/ci_guard_analysis.py:1–224]
- 同じコマンドを `tests/test_analysis_coverage_guard.py` が実行するため、`pytest` を回すだけで coverage 低下や未参照関数が検出される。[tests/test_analysis_coverage_guard.py:7–11]
- 失敗時は標準出力で不足シンボル（例: `marsdisk/io/writer.py#write_orbit_rollup`）が列挙されるので、`analysis/overview.md` や `analysis/run-recipes.md` に参照を追加したうえで `python analysis/tools/make_coverage.py` を再実行し、`analysis/coverage/coverage.json` を更新する。[analysis/tools/make_coverage.py:1–210]
- DocSyncAgent から `analysis/doc_refs.json` を再生成する際は `python -m tools.doc_sync_agent --all --write` を併用し、coverage 作成前後で参照情報を整合させる。

### update_psd_state — PSD初期化の流れ

- 手順
  - `configs/*.yml` で `sizes` と `psd` セクションを調整する。`sizes.s_min/s_max/n_bins` がビン定義を、`psd.alpha` と `psd.wavy_strength` が三勾配＋“wavy”補正を決め、`psd.floor.mode` を `fixed`/`evolve_smin`/`none` から選ぶと床処理が切り替わる。[marsdisk/schema.py:142–151][marsdisk/schema.py:189–199]
  - 実行時は `run_zero_d` がブローアウト境界を評価したあと `psd.update_psd_state` を呼び出し、初期PSDを構築する。[marsdisk/run.py:575–593]
  - 完走後、`out/series/run.parquet` に `kappa`,`s_min`,`mass_total_bins` などが記録される。`psd.floor.mode="evolve_smin"` の場合は `s_min_evolved` 列で進化床を確認する。
- 入出力
  - 入力は `s_min`,`s_max`,`alpha`,`wavy_strength`,`n_bins`,`rho`。不正なサイズ順やビン数は `MarsDiskError` で停止する。[marsdisk/physics/psd.py:30–118]
  - 出力は PSD 状態辞書（`sizes`,`widths`,`number`,`edges`,`rho` など）で、`psd.compute_kappa` や `psd.apply_uniform_size_drift` がそのまま利用する。[marsdisk/physics/psd.py:30–118][marsdisk/run.py:598–603]
- 参照: [marsdisk/physics/psd.py:30–118]
- 根拠: wavy補正と不透明度の健全性は `tests/test_psd_kappa.py` と `marsdisk/tests/test_surface_outflux.py` が自動検証する。[tests/test_psd_kappa.py:22–30][marsdisk/tests/test_surface_outflux.py:33–37]

### qpr_lookup — ⟨Q_pr⟩ テーブルの運用

- 手順
  - `radiation.qpr_table_path`（または互換の `qpr_table`）に Planck平均表の CSV を指定するか、`radiation.Q_pr` で単一値を強制する。[marsdisk/schema.py:314–314]
  - `python -m marsdisk.run --config ...` を起動すると、`run_zero_d` がテーブルをロードし `_lookup_qpr` 経由で `radiation.qpr_lookup` を呼び、ブローアウト解を反復評価する。[marsdisk/run.py:536–536]
  - テーブル未指定で override も無い場合は実行開始時に `RuntimeError` で停止するため、CI で早期に検出できる。
- 入出力
  - `radiation.qpr_lookup(s, T_M, table=None)` は正の grain size と温度を要求し、既定でキャッシュ済み補間器を用いる。テーブルを渡すとその場で評価する。[marsdisk/physics/radiation.py:179–203]
  - 戻り値は無次元の `⟨Q_pr⟩` で、後続の `radiation.beta` や `radiation.blowout_radius` に供給される。[marsdisk/physics/radiation.py:250–258]
- 参照: [marsdisk/physics/radiation.py:179–203]
- 根拠: テーブル補間とバリデーションは `tests/test_qpr_lookup.py` が確認し、β計算との整合も同テストで比較される。[tests/test_qpr_lookup.py:34–66]

### beta — 放射圧比の確認ポイント

- 手順
  - `material.rho` と `temps.T_M`（または `radiation.TM_K`）を設定し、`radiation.qpr_table_path` もしくは `radiation.Q_pr` で `⟨Q_pr⟩` を定義する。[marsdisk/schema.py:108–108][marsdisk/schema.py:124–127][marsdisk/schema.py:314–314]
- 実行中は `run_zero_d` が βを `s_min_config` と `s_min_effective` で評価し、`case_status` や `summary.json` の `beta_at_smin_config` / `beta_at_smin_effective` フィールドへ書き出す。[marsdisk/run.py:598–607][marsdisk/run.py:1236–1263]
  - `out/series/run.parquet` で列 `beta_at_smin_config` / `beta_at_smin_effective` を確認し、閾値を超えた場合 `case_status="blowout"` が記録される。
- 入出力
- `radiation.beta(s, rho, T_M, Q_pr=None)` はサイズ・密度・温度・任意の Planck平均 `⟨Q_pr⟩` を受け取り、無次元のβを返す。引数が非正の場合は例外で停止する。[marsdisk/physics/radiation.py:236–241]
- `run_config.json` には採用した Q_pr や β式が `beta_formula` として保存され、再現実行に利用できる。[marsdisk/run.py:1232–1260]
- 参照: [marsdisk/physics/radiation.py:236–241]
- 根拠: βの逆サイズ依存と Q_pr 上書きは `marsdisk/tests/test_radiation_shielding.py` が、要約出力との連動は `tests/test_summary_backcompat.py` などの統合テストが担保している。[marsdisk/tests/test_radiation_shielding.py:28–31][tests/test_summary_backcompat.py:9–10]

@-- BEGIN:PROVENANCE_RUNREC --
## 出典と根拠（Provenance）
- `analysis/references.registry.json` を唯一の文献レジストリとし、doi/bibtex/採用範囲/主要主張をここへ統合する。
- `analysis/source_map.json` でコード行→参照キーの表を管理し、`todos` 付きエントリは Unknown slug への橋渡しとする。
- `analysis/equations.md` の各ブロック末尾は既知 `[@Key]`、未知 `TODO(REF:<slug>)` を徹底し、DocSync で整合をとる。
@-- END:PROVENANCE_RUNREC --

@-- BEGIN:UNKNOWN_SOURCES_RUNREC --
## 未解決出典（自動）
- `analysis/UNKNOWN_REF_REQUESTS.jsonl` を GPT-5 Pro への問い合わせパケットとして維持し、slug 単位で探索を指示する。
- 対応する Markdown (`analysis/UNKNOWN_REF_REQUESTS.md`) には優先度とコード位置、要約がまとまっている。
- 現状 slug: `tmars_cooling_solution_v1`, `tp_radiative_equilibrium_v1`, `tl2003_surface_flow_scope_v1`。
@-- END:UNKNOWN_SOURCES_RUNREC --

@-- BEGIN:PHYSCHECK_RUNREC --
## 物理チェック（自動）
- `python -m marsdisk.ops.physcheck --config configs/base.yml` で質量保存・次元解析・極限テストをまとめて走らせ、ログを `reports/physcheck/` に残す。[marsdisk/ops/physcheck.py#main]
- `make analysis-doc-tests` は `tests/test_ref_coverage.py` を含む doc 系 pytest を束ね、参照タグの欠落を早期に検知する。
- WARN/FAIL が出た際は `analysis/provenance_report.md` へ反映し、DocSync の差分としてレビューする。
@-- END:PHYSCHECK_RUNREC --
