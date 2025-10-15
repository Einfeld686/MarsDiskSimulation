# run-recipes
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚いガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。

## A. ベースライン実行

1) 目的
最小の0D構成で2年間のcoupled破砕–表層系を完走させ、基準となる Parquet/JSON/CSV 出力を得る。

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
- `series/run.parquet` の列に `prod_subblow_area_rate`,`M_out_dot`,`mass_lost_by_blowout`,`mass_lost_by_sinks` に加え、`dt_over_t_blow`,`fast_blowout_factor`,`fast_blowout_flag_gt3`,`fast_blowout_flag_gt10`,`fast_blowout_corrected` が揃う。供給が0のため `prod_subblow_area_rate` は機械誤差内で0に留まり、`mass_lost_by_sinks` が全行で0であれば HK シンク（`sinks.total_sink_timescale`）が `None` を返し損失項へ寄与していないことを示す。高速ブローアウト補正は既定で無効なので `fast_blowout_corrected` は `false`、閾値フラグは `dt_over_t_blow` の大小に一致する。
- `summary.json` で `case_status` が `beta_at_smin_config` と `beta_threshold` の比較に従い `blowout`（閾値以上）または `ok`（閾値未満）となっていること。
- `summary.json` の β関連フィールドが `beta_at_smin_config` / `beta_at_smin_effective` に分かれていること（旧 `beta_at_smin` は出力されない）。
- `summary.json` の `s_min_components` に `config`,`blowout`,`sublimation`,`effective` が揃い、`sublimation` が `fragments.s_sub_boundary` 由来の HK 境界（`enable_sublimation: false` では 0.0）になっていること、`effective` が `max(config, blowout, sublimation)` を満たすこと。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/physics/fragments.py#s_sub_boundary [L102–L165]]
- `chi_blow` を `1.0` のままにすると `chi_blow_eff=1.0` がサマリに記録され、`"auto"` に切り替えると β と ⟨Q_pr⟩ に連動した補正値（0.5–2.0）が `chi_blow_eff` に入る。
- `checks/mass_budget.csv` の `error_percent` が全行で 0.5% 以下に収まり、最終行の `mass_remaining` と `mass_lost` が初期質量と合致する。
- `run_config.json` の `sublimation_provenance` に HKL 式と選択済み `psat_model`、SiO 既定値（`alpha_evap`,`mu`,`A`,`B`）、`P_gas`、`valid_K`、必要に応じて `psat_table_path`、実行半径・公転時間が保存され、同ファイルに `beta_formula`,`T_M_used`,`rho_used`,`Q_pr_used` も併記されていること。

6) 根拠
- CLI は `python -m marsdisk.run --config …` を受け取り、0D実行を呼び出す。[marsdisk/run.py#run_zero_d [L273–L1005]]
- 0Dケースの軌道量は `omega` と `v_kepler` が `runtime_orbital_radius_m` から導出し、ブローアウト時間や周速度評価の基礎となる。[marsdisk/grid.py:90][marsdisk/grid.py:34]
- 出力として `series/run.parquet`,`summary.json`,`checks/mass_budget.csv`,`run_config.json` を書き出す。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]]
- タイムシリーズのレコード構造に上記カラムを追加し、損失項と高速ブローアウト診断を分離して記録する。[marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]]
- 供給が定数モード0のため生成率は0で、ミキシング後もクリップされる。(configs/base.yml)[marsdisk/physics/supply.py#_rate_basic [L69–L90]]
- 質量収支許容値と違反時の処理を 0.5% で定義している。[marsdisk/run.py#KAPPA_MIN [L55]][marsdisk/run.py#run_zero_d [L273–L1005]][marsdisk/run.py#run_zero_d [L273–L1005]]
- `run_config.json` に式と使用値を格納している。[marsdisk/run.py#run_zero_d [L273–L1005]]

### 派生レシピ: `analysis/run-recipes/baseline_blowout_only.yml`
- 実行例
```bash
python -m marsdisk.run --config analysis/run-recipes/baseline_blowout_only.yml
```
- 確認ポイント
  - `series/run.parquet` に `mass_lost_by_sinks` 列が存在し、総和が0（`sinks.mode: none` による HK シンク対照）。[marsdisk/run.py#run_zero_d [L273–L1005]](tests/test_sinks_none.py)
  - 列構成はベースラインと同じで、`dt_over_t_blow` や `fast_blowout_factor` も一致し、`fast_blowout_corrected` は常に `false`。`n_substeps` が 1 であることを確認し、サブステップ分割が無効であることを確かめる。
  - `checks/mass_budget.csv` の `error_percent` が 0.5% 以下。[marsdisk/run.py#run_zero_d [L273–L1005]]
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
  - `series/run.parquet` の `mass_lost_by_blowout` と `mass_lost_by_sinks` が別カラムで積算され、昇華オンのステップで `mass_lost_by_sinks` が増加する（HK シンクが有限 `t_sink` を返した証拠）。[marsdisk/physics/sinks.py#total_sink_timescale [L83–L160]][marsdisk/run.py#run_zero_d [L273–L1005]]
  - `fast_blowout_factor` や `fast_blowout_flag_gt3/gt10` は昇華の有無に関係なく出力される。高速補正を有効化したい場合は YAML の `io.correct_fast_blowout: true` を追加し、補正適用時に `fast_blowout_corrected` が `true` へ切り替わることを確認する。
  - `summary.json` の `s_min_components.sublimation` が HK 境界 `fragments.s_sub_boundary` に一致し、`s_min_effective = max(config, blowout, sublimation)` が保たれている。`s_min_components` の差分は `sinks.total_sink_timescale` と同じ HK 条件に連動する。
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
  - `summary.json` の `s_min_components` に `"evolved"` キーが追加され、最終的な `s_min_effective` が `max(config, blowout, sublimation, evolved)` の規約を満たしている。

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
- スイープCLI引数とベース設定のデフォルトを `DEFAULT_BASE_CONFIG` と `parse_args` が提供し、マップ仕様は `create_map_definition` で組み立てる。[scripts/sweep_heatmaps.py#DEFAULT_BASE_CONFIG [L47]][scripts/sweep_heatmaps.py#parse_args [L97–L137]][scripts/sweep_heatmaps.py#create_map_definition [L159–L234]]
- ケースごとに `geometry.r`,`temps.T_M`,`io.outdir` を設定し、設定ファイルと出力先を準備して `run_case` へ渡す処理を `build_cases` と `run_case` が担う。[scripts/sweep_heatmaps.py#build_cases [L370–L409]][scripts/sweep_heatmaps.py#run_case [L771–L862]]
- 出力を読み込み `case_status` や `s_min_effective` を抽出する処理は `parse_summary`,`_get_beta_for_checks`,`extract_smin_from_series`,`populate_record_from_outputs` が担当する。[scripts/sweep_heatmaps.py#parse_summary [L456–L482]][scripts/sweep_heatmaps.py#_get_beta_for_checks [L485–L493]][scripts/sweep_heatmaps.py#extract_smin_from_series [L496–L516]][scripts/sweep_heatmaps.py#populate_record_from_outputs [L690–L768]]
- 完了フラグ `case_completed.json` の生成と再実行判定は `mark_case_complete` と `case_is_completed` で実装される。[scripts/sweep_heatmaps.py#mark_case_complete [L323–L337]][scripts/sweep_heatmaps.py#case_is_completed [L340–L345]]
- 集約CSVの出力は `_results_dataframe` と `main` 内の集計ロジックで行い、`total_mass_lost_Mmars` などを整形して保存する。[scripts/sweep_heatmaps.py#_results_dataframe [L865–L871]][scripts/sweep_heatmaps.py#main [L874–L1035]]

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
- ケース再利用時の `case_is_completed` 判定と `run_status` 更新ロジック。[scripts/sweep_heatmaps.py#case_is_completed [L340–L345]][scripts/sweep_heatmaps.py#run_case [L771–L862]]
- 完了フラグ削除後は再実行し、新たなフラグと出力を生成する。[scripts/sweep_heatmaps.py#mark_case_complete [L323–L337]][scripts/sweep_heatmaps.py#run_case [L771–L862]][scripts/sweep_heatmaps.py#main [L874–L1035]]
- 単発実行は `io.outdir` に書き込み、既存内容を上書きする。[marsdisk/run.py#run_zero_d [L273–L1005]]
- CLI フラグ `--enforce-mass-budget` で許容超過時に例外を送出する。[marsdisk/run.py#run_zero_d [L273–L1005]]

## D. 同定可能性チェック

1) 目的
`summary.json` の累積損失 `M_loss` がタイムシリーズ最終行の `M_loss_cum` と一致するかを手元で検算する。

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
- `summary.json` の `M_loss` は `M_loss_cum + M_sink_cum` を記録する。[marsdisk/run.py#run_zero_d [L273–L1005]]
- タイムシリーズ `M_loss_cum`,`mass_lost_by_blowout`,`mass_lost_by_sinks`,`mass_total_bins` の更新式。[marsdisk/run.py#run_zero_d [L273–L1005]]
- シンク無効設定は昇華・ガス抗力を停止させる。(configs/base.yml)[marsdisk/schema.py#QStar [L197–L204]]

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
- Parquet書き出しが `pyarrow` 依存である。[marsdisk/io/writer.py#_ensure_parent [L20–L21]]
- 0D実行は `geometry.r` 未指定時に例外を送出する。[marsdisk/run.py#run_n_steps [L205–L223]]
- 供給テーブル読込は `pd.read_csv` でパスが必要。[marsdisk/physics/supply.py#_TableData [L25–L63]]
- `s_min` が `s_max` を超えると 0.9倍に補正して警告する。[marsdisk/run.py#run_zero_d [L273–L1005]]

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
- SiO物性は (α=7×10⁻³, μ=4.40849×10⁻² kg mol⁻¹, A=13.613, B=17850, P_gas=0) を `SublimationParams` 既定値から流用する。[analysis/checks_psat_auto_01/inputs/case_A_tabulated.yml][marsdisk/physics/sublimation.py#grain_temperature_graybody [L124–L135]]

4) 期待される出力
- `analysis/checks_psat_auto_01/runs/case_*/series/run.parquet` → `python -c "import pandas as pd; print(pd.read_parquet('analysis/checks_psat_auto_01/runs/case_A_tabulated/series/run.parquet').head())"`
- `analysis/checks_psat_auto_01/runs/case_*/run_config.json` の `psat_model_resolved` が順に `tabulated`／`clausius(local-fit)`／`clausius(baseline)` になる。→ `jq '.sublimation_provenance.psat_model_resolved' analysis/checks_psat_auto_01/runs/case_B_localfit/run_config.json`
- `analysis/checks_psat_auto_01/scans/hkl_assertions.json` の `monotonic`, `finite`, `nonnegative` がすべて `true`。
- `analysis/checks_psat_auto_01/scans/psat_provenance.json` に resolved モデル、A/B係数、valid_K、表範囲がまとまる。
- `analysis/checks_psat_auto_01/logs/pytest_sio.log` が全テスト成功を示す。

5) 確認項目
- `run_config.json` の `valid_K_active` と `psat_table_range_K` がケースごとの温度に応じて更新されている。[marsdisk/physics/sublimation.py#p_sat [L525–L531]]
- `case_B_localfit` の `run.log` で局所フィット適用メッセージ（`psat auto: requested temperature ... using local Clausius fit.`）が出力される。
- `scan_hkl.py` が各ケースで91サンプルを出力し、最小／最大フラックスが ~1e-4–1e5 kg m⁻² s⁻¹ に収まる。
- `tests/test_sublimation_sio.py` が pass し、HKL実装とauto-selector回帰が保たれている。

6) 根拠
- psatテーブルは Clausius式 `log10 P = A - B/T` から生成し、PCHIP補間にロードする。[analysis/checks_psat_auto_01/make_table.py][marsdisk/physics/sublimation.py#_load_psat_table [L167–L227]]
- auto-selector はタブレット範囲内で内挿、それ以外で局所最小二乗フィットまたは既定係数にフォールバックする。[marsdisk/physics/sublimation.py#choose_psat_backend [L386–L494]][marsdisk/physics/sublimation.py#_local_clausius_fit_selection [L269–L334]]
- HKLフラックスは `mass_flux_hkl` が評価し、`scan_hkl.py` で同式を再計算して温度スキャンを行う。[marsdisk/physics/sublimation.py#mass_flux_hkl [L534–L584]][analysis/checks_psat_auto_01/scan_hkl.py]
- 出力ファイル群は既存の writer 実装に従って Parquet/JSON/CSV として保存される。[marsdisk/io/writer.py#write_parquet [L24–L106]]
