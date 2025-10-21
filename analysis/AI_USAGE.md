# このガイドの目的
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚い内側ガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。
この資料は0D円盤で破砕供給と表層剥離を組み合わせる既存実装の実行方法と出力解釈を、自動化主体でも誤読しない手順として整理する。（analysis/overview.md, [marsdisk/run.py:426-1611]）

# 誰向けか（AI/自動化ツール）と、何ができるかを1段落で。
対象は設定ファイルを切り替えながら結果回収を自動化するAIやCIスクリプトであり、CLI起動・成果物の収集・再実行条件の判定を一連のジョブとして扱える。（[marsdisk/run.py:1387-1449], analysis/run-recipes.md）設定スキーマの検証や有効半径の算定はコード側で完結しているので、本資料に沿えば追加の仮定なしにβ判定や質量収支ログを取得できる。

# 最短の実行手順（Quickstart）
`run_zero_d`は単一コマンドで完結し、出力先は設定の`io.outdir`に従う。（[marsdisk/run.py:1387-1445], [marsdisk/run.py:426-1611]）

```bash
python -m marsdisk.run --config analysis/run-recipes/baseline_blowout_only.yml
```

- `OUTDIR/series/run.parquet`：各ステップの記録を`writer.write_parquet`が生成するタイムシリーズで、`F_abs`,`psi_shield`,`kappa_Planck`,`tau_eff`,`sigma_surf`,`s_peak`,`M_out_cum` などの診断列を保持する。（[marsdisk/run.py:1287-1327], [marsdisk/io/writer.py:80-171]）
- `OUTDIR/summary.json`：累積損失とβ診断に加え、`mass_budget_max_error_percent` や `dt_over_t_blow_median` を含む集約で、`run_zero_d`終端で書き出される。（[marsdisk/run.py:1395-1420], [marsdisk/io/writer.py:185-193]）
- `OUTDIR/checks/mass_budget.csv`：C4質量検査を逐次追記したCSVで、許容差と実測誤差を比較する。（[marsdisk/run.py:1330-1369], [marsdisk/io/writer.py:185-193]）
- `OUTDIR/run_config.json`：`physics_controls` にブローアウト／遮蔽／凍結／PSD床モードの実行値を残し、`sublimation_provenance` で HKL 式・`psat_model`・SiO 既定パラメータ（`alpha_evap`,`mu`,`A`,`B`）・`P_gas`・`valid_K`・テーブルパス・実行半径・公転時間を追跡できる。（[marsdisk/run.py:1523-1611], [marsdisk/io/writer.py:185-200]）

# 設定の要点（YAML→スキーマ→実行）
設定値はYAML→Pydantic→実行時オブジェクトの順に検証される。（[marsdisk/run.py:303-360], [marsdisk/schema.py:437-455]）

- CLIの `--override path=value` は YAML 読み込み後の辞書にマージされ、`load_config` と CLI エントリポイントで共通に処理される。複数指定は `--override a=b --override c=d` またはスペース区切りで指定可能。（[marsdisk/run.py:372-387], [marsdisk/run.py:1622-1654]）
- `physics.blowout.enabled`,`radiation.freeze_kappa`,`surface.freeze_sigma`,`shielding.mode`,`psd.floor.mode` などの物理トグルはスキーマで検証され、`run_zero_d` 内でブローアウト損失や遮蔽、床径進化を切り替える。（[marsdisk/schema.py:212-339], [marsdisk/run.py:623-905]）
- `sinks.mode` は既定で`sublimation`、`none`を選ぶと昇華とガス抗力を同時に停止し、追加シンクの有効化は `SinkOptions` を通じて昇華パラメータ `SublimationParams(**cfg.sinks.sub_params.model_dump())` にコピーされる。HKL 既定値は SiO（`psat_model="clausius"`, μ=0.0440849 kg/mol, α=0.007, A=13.613, B=17850, `valid_K=[1270,1600]`）。`psat_model="tabulated"` を指定すると外部テーブルから `log10P` を読み込む。（[marsdisk/schema.py:251-266], [marsdisk/run.py:571-706], [marsdisk/physics/sublimation.py:167-227], [marsdisk/physics/sinks.py:35-160]）
- `sinks.mode="none"` の場合は `t_sink=None` が `surface.step_surface` に渡り、光学的厚さが与えられてもシンク項は無効のまま推移する。（[marsdisk/run.py:820-1016], [marsdisk/physics/surface.py:96-196]）
- `e_mode` / `i_mode` を設定しない場合は従来どおり入力スカラー `e0` / `i0` を使用するが、`mars_clearance` / `obs_tilt_spread` を指定すると Δr サンプリングや観測傾斜を乱数で生成して初期条件を再設定する。`dr_min_m`/`dr_max_m`（m）や`i_spread_deg`（度）と `rng_seed` を併用して再現性を確保する。（[marsdisk/schema.py:161-199], [marsdisk/run.py:448-515]）
- 温度は `radiation.TM_K` が優先され、未設定時は `temps.T_M` を用い、どちらの経路かを `T_M_source` としてサマリに記録する。（[marsdisk/schema.py:269-314], [marsdisk/run.py:561-563], [marsdisk/run.py:1417-1420]）

# 最小粒径と軽さ指標（データ契約）
PSDの下限は `psd.floor.mode` に応じて設定値・ブローアウト境界・`ds/dt` 派生値の最大で評価され、辞書 `"s_min_components"` に `config` / `blowout` / `effective` / `floor_mode` / `floor_dynamic` を保持する。（[marsdisk/schema.py:212-220], [marsdisk/run.py:633-705]）ブローアウト境界（[marsdisk/physics/radiation.py:244-258]）が主因となり、`"evolve_smin"` モードでは HKL 由来の `|ds/dt|Δt` が `s_min_floor_dynamic` として単調に蓄積される。（[marsdisk/run.py:748-806], [marsdisk/physics/psd.py:267-356]）

放射圧と重力の比率を表す軽さ指標（β）は `s_min_config` と `s_min_effective` で別々に評価され、それぞれ `beta_at_smin_config` と `beta_at_smin_effective` として記録される。（[marsdisk/run.py:669-686], [marsdisk/physics/radiation.py:220-241]）`beta_threshold` は定数 0.5 で、βが閾値以上なら `case_status="blowout"`（ブローアウト抑止時は `"no_blowout"`）、未満なら `"ok"` となる。（[marsdisk/physics/radiation.py:32-32], [marsdisk/run.py:675-684], [scripts/sweep_heatmaps.py:1248-1264]）

# 出力ファイルの中身（機械可読の約束）
`summary.json`の主要キーは次のとおり。

| キー | 意味 | 単位 | 記録箇所 |
| --- | --- | --- | --- |
| `M_loss` | 吹き飛び損失とシンク損失の合計 | M_Mars | [marsdisk/run.py:1400-1405] |
| `M_out_cum` / `M_sink_cum` | 各経路の累積損失 | M_Mars | [marsdisk/run.py:1400-1405] |
| `case_status` | 軽さ指標によるケース分類 (`blowout` / `ok` / `no_blowout`) | 文字列 | [marsdisk/run.py:1405-1408] |
| `beta_threshold` | 軽さ指標の閾値 | 無次元 | [marsdisk/physics/radiation.py:32-32], [marsdisk/run.py:1406-1410] |
| `beta_at_smin_config` / `beta_at_smin_effective` | 設定・有効下限でのβ | 無次元 | [marsdisk/run.py:1408-1410] |
| `s_min_config` / `s_min_effective` | YAML指定とクリップ後の最小粒径 | m | [marsdisk/run.py:635-705], [marsdisk/run.py:1427-1430] |
| `s_min_effective_gt_config` | 有効下限が設定値より大きいか | 真偽値 | [marsdisk/run.py:1427-1431] |
| `s_min_components` | `config`/`blowout`/`effective`/`floor_dynamic` 等を保持 | m | [marsdisk/run.py:642-649], [marsdisk/run.py:1430-1431] |
| `T_M_used` / `T_M_source` | 使用温度と出典ラベル | K / 文字列 | [marsdisk/run.py:1418-1420] |
| `rho_used` / `Q_pr_used` | 材料密度と Planck 平均効率 | kg/m³ / 無次元 | [marsdisk/run.py:1414-1416] |
| `mass_budget_max_error_percent` | ステップ最大質量誤差 | % | [marsdisk/run.py:1395-1425] |
| `dt_over_t_blow_median` | ブローアウト時間に対するΔt中央値 | 無次元 | [marsdisk/run.py:1395-1425] |
| `mass_budget_violation` | 許容超過時の詳細（オプション） | 辞書 | [marsdisk/run.py:1446-1451] |

- `series/run.parquet`で最低限確認する列は次のとおり。

  - `time` / `dt`：通算時刻とステップ幅。[marsdisk/run.py:1210-1243]
  - `prod_subblow_area_rate`：光学クリップ後に混合された供給率[kg m⁻² s⁻¹]。[marsdisk/run.py:1235-1236]
  - `M_out_dot` / `M_sink_dot`：吹き飛び・追加シンクの瞬時流出率[M_Mars s⁻¹]。[marsdisk/run.py:1236-1238]
  - `mass_lost_by_blowout` / `mass_lost_by_sinks`：累積損失[M_Mars]。[marsdisk/run.py:1246-1250]

- `series/diagnostics.parquet` では幾何吸収量や遮蔽を追跡できる。`F_abs`,`psi_shield`,`kappa_Planck`,`tau_eff`,`sigma_surf`,`s_peak`,`M_out_cum` を確認し、遮蔽モードやPSD床の挙動をレビューする。（[marsdisk/run.py:1287-1327], [marsdisk/io/writer.py:80-171]）

<!-- AUTOGEN:AI_USAGE PRACTICES START -->

# アンカー規約
- `marsdisk/...` の参照はすべて `[path/to/file.py:start–end]` 形式に統一する。関数名ハッシュや `#symbol` 付きアンカーは禁止。
- アンカーの解決は `analysis/inventory.json` と `analysis/symbols.raw.txt` を基にする。新しい関数・クラスを追加した際は必ず `analysis/tools/anchor_sync.py --write --root analysis` を実行し、行範囲を再解決する。
- 既存アンカーが外れた場合は、`analysis/tools/anchor_sync.py --write` を走らせた後で差分を確認し、必要なら `analysis/tools/check_docs.py --strict` の WARN/ERROR を根拠に修正する。
- モジュール全体を参照する必要があっても `#__module__` アンカー以外の直書きを許可しない。根拠となるセクションを作り、該当関数を列挙すること。

# 日次チェック手順
1. `python analysis/tools/anchor_sync.py --write`  
   既存アンカーの行範囲を再解決し、新規シンボルを同期する。
2. `python analysis/tools/make_coverage.py`  
   `analysis/coverage/coverage.{json,md}` を更新し、参照率と未解決リストを最新化する。
3. `python analysis/tools/check_docs.py --strict`  
   70%未満の参照率・行範囲ずれ・単位不足を検出し、WARN も ERROR へ昇格させる。

すべて成功したら `git status` で差分を確認し、CI やチーム共有用のメモを残す。

# しきい値と例外対応
- **アンカー整合率**（= 1.0 を要求）を下回った場合、該当アンカーを修正できない理由を Issue へ記載し、`analysis/coverage/anchor_unresolved.tsv` に除外理由を追記する。緊急度が高い場合は `docs@marsdisk.example`（仮）へ連絡する。
- **関数参照率**が 70% 未満の場合、`analysis/coverage/coverage.json` の `holes` から優先度順に 3 件以上を抜粋し、次のスプリントでドキュメント化する。例外を認めるときは、対象シンボルを `analysis/coverage/exclude_functions.txt`（行コメント付き）に追加し、理由と期限を書く。
- **単位記載率**が 90% 未満でも緊急度は低いが、更新へ向けた TODO を Issue に残し、新しい式ブロックには必ず単位表を含める。分析用途で一時的に無視する場合は `analysis/tools/check_docs.py --no-regen` を使い、ログに「一時除外: 単位未定義」と明記する。

例外票を作成したら、週次の運用ミーティングで棚卸しし、古い除外を削除する。除外リストのエントリには担当者と更新期限（YYYY-MM-DD）を必ず付けること。

<!-- AUTOGEN:AI_USAGE PRACTICES END -->
- `dt_over_t_blow`：`Δt / t_{\rm blow}`（無次元）。タイムステップがブローアウト時間を十分解像しているかの指標で、常に記録される。（[marsdisk/run.py:1072-1106], [marsdisk/io/writer.py:118-136]）
- `fast_blowout_factor` と `fast_blowout_flag_gt3/gt10`：高速ブローアウト補正の適用状況。`io.correct_fast_blowout=true` かつ `dt/t_{\rm blow} > 3` のステップで補正係数が乗算され、`case_status` が `"blowout"` でない行は互換性のため `0.0` を保持する。（[marsdisk/run.py:1072-1107], [marsdisk/io/writer.py:141-145]）
- `M_out_dot_avg` / `M_sink_dot_avg` / `dM_dt_surface_total_avg`：ステップ平均化した吹き飛び・シンク・総和の質量損失レート（M_Mars s⁻¹）。時間積分で累積値を復元する際に利用する。（[marsdisk/run.py:1072-1093], [marsdisk/io/writer.py:124-133]）
- `n_substeps`：`io.substep_fast_blowout=true` かつ `dt/t_{\rm blow}` が `io.substep_max_ratio` を超えた際に使用されたサブステップ数（既定 1）。（[marsdisk/run.py:1044-1109], [marsdisk/io/writer.py:135-136]）

`checks/mass_budget.csv`は`time`,`mass_initial`,`mass_remaining`,`mass_lost`,`mass_diff`,`error_percent`,`tolerance_percent`を持ち、`error_percent`が0.5%以内かで合否を判断する。（[marsdisk/run.py:1330-1351]）

`run_config.json`にはβ式、ブローアウト式、デフォルト定数、実際に用いた`T_M_used`,`rho_used`,`Q_pr_used`、Git情報、`physics_controls`、`sublimation_provenance` が記録されるため、再解析時はここを参照して式の係数とトグルを一致させる。（[marsdisk/run.py:1477-1547]）

`io.correct_fast_blowout` は既定で `false` であり、粗いステップ幅で `dt/t_{\rm blow}` が 3 を大きく超える感度試験でのみ `true` に切り替えることを推奨する。補正を有効化すると `fast_blowout_factor` が表層アウトフローへ乗算され、`fast_blowout_corrected` が `true` になる。通常解析では補正を無効のまま保持し、`scripts/analyze_radius_trend.py` の WARNING（および `flag_dt_over_t_blow_gt3` / `flag_dt_over_t_blow_gt10` 列）で対処が必要か判断する。

# 互換性：旧フィールド `beta_at_smin` の扱い
スイープ集計では互換カラムとして`beta_at_smin`が残り、新フィールドが利用可能なら`beta_at_smin_config`と`beta_at_smin_effective`を優先し、旧カラムは後方互換のために並列表記される。（[scripts/sweep_heatmaps.py:1252–1258]定義（概ね994–1012行））自動処理では新フィールドを参照し、欠損時のみ旧カラムで補う方針を推奨する。

# 代表レシピ
**ブローアウトのみ（baseline_blowout_only.yml）** `sinks.mode: "none"`と`enable_sublimation: false`がセットされ、`t_sink=None`が表層解法に渡るため`mass_lost_by_sinks`は全行で0になる。（analysis/run-recipes/baseline_blowout_only.yml, [marsdisk/run.py:697-1016]）実行後に`python -c "import pandas as pd; df=pd.read_parquet('analysis/outputs/baseline_blowout_only/series/run.parquet'); print(df['mass_lost_by_sinks'].sum())"`などでゼロを確認する。

**スイープの最小例** `scripts/sweep_heatmaps.py`はマップ定義と出力CSVを自動構築し、集計CSVに軽さ指標の新旧両カラムと`case_status`を列挙する。（[scripts/sweep_heatmaps.py:1261-1524]）`python scripts/sweep_heatmaps.py --map 1 --outdir sweeps/map1_demo --jobs 4`を用いると、結果CSVに`beta_at_smin_config`,`beta_at_smin_effective`,`beta_at_smin`が同時に含まれ、互換項目との整合を確認できる。

# よくある落とし穴
- 半径`r`を設定しないと0D実行で例外が発生するため、YAMLで`geometry.r`または`disk.geometry`を必ず与える。（[marsdisk/run.py:517-705], analysis/run-recipes.md）
- 温度上書きの出典を混同しないよう、`radiation.TM_K`を使った場合はsummaryの`T_M_source`が`"radiation.TM_K"`になる点を確認する。（[marsdisk/run.py:561-563], [marsdisk/run.py:1417-1420]）
- `s_min_effective`が`s_max`に近づくと0.9倍でクランプされるため、極端な昇華設定ではPSDの解像度が失われる。（[marsdisk/run.py:635-666]）
- `pyarrow`未導入だとParquet書き出しが失敗するので、CI環境では事前に依存関係を導入する。（[marsdisk/io/writer.py:24-103]）

# 検証チェックリスト（短縮版）
- `sinks.mode`が`none`のケースでは`mass_lost_by_sinks`の総和が0になることを確認する。（[marsdisk/run.py:1072-1250]）
- `case_status`が`beta_at_smin_config`と`beta_threshold`の比較結果に一致するかをsummaryで確認する。（[marsdisk/run.py:1406-1409], [marsdisk/physics/radiation.py:32-32]）
- `checks/mass_budget.csv`で`error_percent`が0.5%以下かを検査し、超過時は`--enforce-mass-budget`再実行を検討する。（[marsdisk/run.py:1330-1357]）

# 付録：用語の一行定義
- 軽さ指標（放射圧比 β, radiation pressure ratio）：放射圧と重力の比を表し、0.5を超えると粒子が吹き飛ぶ。（[marsdisk/physics/radiation.py:220-241]）
- ブローアウト半径（blow-out radius）：軽さ指標が0.5になる粒径で、`s_min`クリップの基準になる。（[marsdisk/physics/radiation.py:244-258]）
- Wyatt衝突時間（Wyatt collisional time）：Wyattスケール`1/(2Ωτ)`で評価する表層の衝突寿命。（[marsdisk/physics/surface.py:62-90]）
- 光学的厚さ（optical depth）：遮蔽判断に使う厚さ指標で、`sigma_tau1`によるクリップの上限を定める。（[marsdisk/physics/surface.py:96-196]）
