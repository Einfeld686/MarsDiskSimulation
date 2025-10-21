# marsshearingsheet クイックガイド

## ガス希薄（gas‑poor）前提

本モデルは **火星ロッシュ限界内のガスに乏しい衝突起源ダスト円盤**を解析対象としています。溶融主体で蒸気成分が≲数%に留まるという報告（Hyodo et al. 2017; 2018）と、Phobos/Deimos を残すには低質量・低ガス円盤が必要だという Canup & Salmon (2018) を踏まえ、標準ケースでは **Takeuchi & Lin (2003)** が仮定するガスリッチ表層アウトフローを採用しません（`ALLOW_TL2003=false` が既定）。gas-rich 条件を調べる場合のみ、利用者責任で明示的に切り替えてください。参考枠組みとして Strubbe & Chiang (2006)、Kuramoto (2024) を推奨します。

## 1. モデル概要

- `marsdisk.run.run_zero_d` が 0D（半径無次元）ダスト円盤を時間発展させ、内部破砕で生成される sub-blow-out 粒子供給と表層の放射圧剥離を連成します（式 C1–C4, P1, F1–F2, R1–R3, S0–S1、analysis/equations.md を参照）。
- 主要モジュール  
  - `marsdisk/physics/radiation.py`：平均 $\langle Q_{\rm pr}\rangle$、$\beta$、$a_{\rm blow}$。  
  - `marsdisk/physics/psd.py`：三勾配 + “wavy” 補正付き PSD と不透明度。  
  - `marsdisk/physics/shielding.py`：多層 RT 由来の自遮蔽係数 $\Phi(\tau,\omega_0,g)$。  
  - `marsdisk/physics/collide.py`, `smol.py`：Smoluchowski IMEX-BDF(1) による破砕と質量保存検査。  
  - `marsdisk/physics/surface.py`：Wyatt スケールの衝突寿命と吹き飛び・追加シンクを含む表層 ODE。  
  - `marsdisk/io/writer.py`：Parquet / JSON / CSV への出力。
- 再現性のため `random`, `numpy.random`, `numpy.random.default_rng` の全 RNG を同一シードで初期化します（analysis/overview.md §9）。

詳細な数式・導出・ブロック図は `analysis/overview.md` と `analysis/equations.md` を参照してください。

## 2. クイックスタート

```bash
python -m venv .venv && source .venv/bin/activate  # 任意の仮想環境
pip install -r requirements.txt                    # ない場合は numpy pandas pyarrow ruamel.yaml pydantic 等を個別導入

python -m marsdisk.run --config configs/base.yml   # 0D シミュレーション実行
# 追加シンク（昇華・ガス抗力）を無効化したい場合
python -m marsdisk.run --config configs/base.yml --sinks none
```

### 生成物（標準設定）

| 出力 | 内容 |
| --- | --- |
| `out/series/run.parquet` | 時系列（`prod_subblow_area_rate`, `M_out_dot`, `tau`, `t_blow`, etc.） |
| `out/summary.json` | `M_loss`, `M_loss_from_sinks`, `M_loss_from_sublimation`, `s_blow_m`, `beta_at_smin*`, `s_min_effective[m]`, `T_M_source`, `T_M_used[K]` 等を含むサマリ |
| `out/checks/mass_budget.csv` | ステップ毎の質量保存ログ（許容誤差 0.5% 未満） |
| `out/run_config.json` | 使用した式、定数、シード、`init_ei` ブロック（`dynamics.e_mode/i_mode`、$\Delta r$, $e_0$, $i_0$、`e_formula_SI`, `a_m_source` など） |

`series/run.parquet` にはタイムステップ毎の高速ブローアウト診断が含まれます。`dt_over_t_blow = Δt / t_{\rm blow}`（無次元）、`fast_blowout_factor = 1 - \exp(-Δt / t_{\rm blow})`（面密度に対する有効損失分率）、`fast_blowout_flag_gt3` / `fast_blowout_flag_gt10`（`dt/t_{\rm blow}` が 3・10 を超えた際に `true`）が出力され、`io.correct_fast_blowout` を `true` にしたケースのみ `fast_blowout_corrected` が `true` になります（既定は `false` で補正は適用されません）。また、表層レートの列として `dSigma_dt_blowout`,`dSigma_dt_sinks`,`dSigma_dt_total`（単位 kg m⁻² s⁻¹）と、同じステップの平均化された惑星質量スケールのレート `M_out_dot_avg`,`M_sink_dot_avg`,`dM_dt_surface_total_avg` が追加されています。`n_substeps` 列は高速ブローアウトをサブステップで解像した場合の分割数（既定 1）を記録します。

`chi_blow` は YAML のトップレベルで設定でき、スカラー値を与えると従来通り `t_{\rm blow} = chi_{\rm blow} / \Omega` を使用、`"auto"` を指定すると β と ⟨Q_pr⟩ から 0.5–2.0 の範囲で自動推定した係数を採用します。自動推定値は `chi_blow_eff` としてタイムシリーズおよびサマリに記録されます。

初期化温度 `T_M` は `radiation.TM_K` が指定されていれば優先され、未設定の場合は `temps.T_M` が採用されます。どちらが使われたかは `summary.json` の `T_M_source` を参照してください（`radiation.TM_K` / `temps.T_M` が入ります）。採用温度は `T_M_used[K]` に、対応するブローアウト半径や $\beta$ は `s_blow_m`、`beta_at_smin_*` に記録されます。Q_pr/Phi テーブルは `analysis/AI_USAGE.md` に従って `marsdisk/io/tables.py` 経由で読み込み、欠損時は警告付きの解析近似へフォールバックします。

## 3. 設定 YAML の要点

`configs/base.yml` は 0D 実行に必要な最小ブロックを含みます。各セクションの主要項目と挙動は以下の通りです（詳細は `analysis/AI_USAGE.md`）。

| セクション | 主なフィールド | 備考 |
| --- | --- | --- |
| `geometry` | `mode="0D"`, `r` | 代表半径（m）。`e_mode="mars_clearance"` を使う場合は必須。 |
| `material` | `rho` | 粒子バルク密度。 |
| `temps` / `radiation` | `T_M`, `TM_K`, `Q_pr`, `qpr_table` | `radiation.TM_K` が優先。Q_pr テーブル or スカラー上書き可能。 |
| `sizes` | `s_min`, `s_max`, `n_bins` | 対数ビン数は 30–60 推奨（既定 40）。 |
| `initial` | `mass_total`, `s0_mode` | 初期 PSD モードは `"upper"` / `"mono"`。 |
| `dynamics` | `e0`, `i0`, `t_damp_orbits`, `f_wake` | **既定モードは `e_mode="fixed"` / `i_mode="fixed"`**。モードを指定しなければ入力スカラー `e0` / `i0` がそのまま初期値となります。`e_mode="mars_clearance"` を選ぶと Δr（m）を `dr_min_m` / `dr_max_m` からサンプリングし `e = 1 - (R_{\rm MARS}+Δr)/a` を適用、`i_mode="obs_tilt_spread"` では `obs_tilt_deg ± i_spread_deg`（度）をラジアンに変換して一様乱数サンプリングします。`rng_seed` を指定すると再現性を確保できます。 |
| `psd` | `alpha`, `wavy_strength` | 三勾配 PSD と “wavy” 補正の強さ。 |
| `qstar` | `Qs`, `a_s`, `B`, `b_g`, `v_ref_kms` | Leinhardt & Stewart (2012) の補間式を採用。 |
| `surface` | `init_policy`, `use_tcoll` | Wyatt 衝突寿命の導入や Στ=1 のクリップを制御。 |
| `supply` | `mode`, `const` / `powerlaw` / `table` / `piecewise` | 表層供給の時間依存・空間構造。 |
| `sinks` | `mode`, `enable_sublimation`, `enable_gas_drag`, `sub_params.*`, `rho_g` | 昇華・ガス抗力など追加シンク。`mode="none"` で一括無効。 |
| `shielding` | `phi_table` | Φ テーブル経由で自遮蔽係数を補正。 |
| `numerics` | `t_end_years`, `dt_init`, `safety`, `atol`, `rtol` | IMEX-BDF(1) のタイムステップ制御 (`Δt ≤ 0.1 * min t_{\rm coll,k}` が収束条件)。 |
| `io` | `outdir` | 出力ディレクトリ。 |

サンプルとして `analysis/overview.md` の YAML スニペットや `configs/base.yml` / `configs/sweep_example.yml` を参照してください。

### RNG とプロヴェナンス

- `dynamics.rng_seed` を省略した場合は既定シード（`marsdisk/run.py` 内定義）が適用され、`run_config.json` の `init_ei.seed_used` に記録されます。
- `run_config.json` には式、使用定数、Git 情報、`e_formula_SI`（単位説明付き）を埋め込み、分析再現性を担保します。

## 4. 可視化とバッチ実行

`scripts/sweep_heatmaps.py` は感度掃引用に YAML を自動生成し、複数ケースを実行して `results/*.csv` と `sweeps/<map>/<case_id>/out/` へ集計します。  
`scripts/plot_heatmaps.py` は `results/map*.csv` からヒートマップ（例：`total_mass_lost_Mmars`, `beta_at_smin`）を描画し `figures/` へ保存します。  
使い方は各スクリプトの `--help` と `analysis/run-recipes.md` を参照してください。

## 5. テスト

ユニットテストは `pytest` で実行します。

```bash
pytest
```

- Wyatt の衝突寿命スケーリング、ブローアウト即時消滅による “wavy” PSD、IMEX 安定性などのテストが `marsdisk/tests/` に用意されています。
- RNG 駆動モードの再現性と出力レンジを確認する `test_dynamics_sampling.py` も含まれます。

## 6. 参考ドキュメント

- `analysis/overview.md`：アーキテクチャ／物理式／データフローの詳細。  
- `analysis/AI_USAGE.md`：YAML 設定のポイントと I/O 契約。  
- `analysis/run-recipes.md`：ベンチマークや掃引ジョブの運用ノウハウ。  
- `analysis/sinks_callgraph.md`：追加シンクの流れと依存関係。  
- `analysis/equations.md`：採用方程式と文献まとめ。

必要に応じて `analysis/` ディレクトリを `python -m tools.doc_sync_agent --all --write` で同期し、コード変更後の参照情報を更新してください。

## 7. デバッグとトラブルシュート

- **温度掃引が変化しない場合**  
  `radiation.TM_K` が設定されたまま `temps.T_M` を変えても、上書きされた定数温度が使われるため結果が固定されます。`summary.json` の `T_M_source` を確認し、掃引時は `radiation.TM_K` を `null` にするか CLI で未指定にしてください。
- **昇華シンクの可視化**  
  YAML で `io.debug_sinks: true` を指定すると `out/<case>/debug/sinks_trace.jsonl` が生成され、各ステップの `t_sink`, `dominant_sink`, `total_sink_dm_dt_kg_s`, `cum_sublimation_mass_kg` などを追跡できます。ロギングを無効に戻すには `false` を指定します。
- **RNG の再現性**  
  CLI / YAML の同一設定で再実行しても、`dynamics.rng_seed` が一致していれば `summary.json` / `series/run.parquet` の統計量は一致します。シードを省略した場合は幾何条件からの自動決定値（`run_config.json` の `rng_seed_expr` を参照）が使われます。
