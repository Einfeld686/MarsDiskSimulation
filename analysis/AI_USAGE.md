# このガイドの目的
> **注記（gas‑poor）**: 本解析は **ガスに乏しい衝突起源デブリ円盤**を前提とします。従って、**光学的に厚い内側ガス円盤**を仮定する Takeuchi & Lin (2003) の表層塵アウトフロー式は**適用外**とし、既定では評価から外しています（必要時のみ明示的に有効化）。この判断は、衝突直後の円盤が溶融主体かつ蒸気≲数%で、初期周回で揮発が散逸しやすいこと、および小衛星を残すには低質量・低ガスの円盤条件が要ることに基づきます。参考: Hyodo et al. 2017; 2018／Canup & Salmon 2018。
この資料は0D円盤で破砕供給と表層剥離を組み合わせる既存実装の実行方法と出力解釈を、自動化主体でも誤読しない手順として整理する。（analysis/overview.md, [marsdisk/run.py:1032–2795]）

# 誰向けか（AI/自動化ツール）と、何ができるかを1段落で。
対象は設定ファイルを切り替えながら結果回収を自動化するAIやCIスクリプトであり、CLI起動・成果物の収集・再実行条件の判定を一連のジョブとして扱える。（[marsdisk/run.py:1622–1654], analysis/run-recipes.md）設定スキーマの検証や有効半径の算定はコード側で完結しているので、本資料に沿えば追加の仮定なしにβ判定や質量収支ログを取得できる。

# 最短の実行手順（Quickstart）
`run_zero_d`は単一コマンドで完結し、出力先は設定の`io.outdir`に従う。（[marsdisk/run.py:1622–1654], [marsdisk/run.py:1032–2795]）

```bash
python -m marsdisk.run --config analysis/run-recipes/baseline_blowout_only.yml
```

- `OUTDIR/series/run.parquet`：各ステップの記録を`writer.write_parquet`が生成するタイムシリーズで、`F_abs`,`psi_shield`,`kappa_Planck`,`tau_eff`,`sigma_surf`,`s_peak`,`M_out_cum` などの診断列を保持する。（[marsdisk/run.py:1281–1415], [marsdisk/io/writer.py:24–162]）
- `OUTDIR/summary.json`：累積損失とβ診断に加え、`mass_budget_max_error_percent` や `dt_over_t_blow_median` を含む集約で、`run_zero_d`終端で書き出される。（[marsdisk/run.py:2660–2771], [marsdisk/io/writer.py:185–193]）
- `OUTDIR/checks/mass_budget.csv`：C4質量検査を逐次追記したCSVで、許容差と実測誤差を比較する。（[marsdisk/run.py:2334–2351], [marsdisk/io/writer.py:191–193]）
- `OUTDIR/run_config.json`：`physics_controls` にブローアウト／遮蔽／凍結／PSD床モードの実行値を残し、`sublimation_provenance` で HKL 式・`psat_model`・SiO 既定パラメータ（`alpha_evap`,`mu`,`A`,`B`）・`P_gas`・`valid_K`・テーブルパス・実行半径・公転時間を追跡できる。（[marsdisk/run.py:2795–2889], [marsdisk/io/writer.py:185–188]）

# analysis のシングルソースと参照カタログ
- 数式・変数定義の唯一のソースは `analysis/equations.md`。`slides_outline.md` / `run_catalog.md` / `figures_catalog.md` / `glossary.md` / `literature_map.md` は参照ビューであり、式本体や独自定義を持たず eq_refs や FIG_/RUN_/REF_ ID を列挙するだけとする。
- FIG_ / RUN_ / REF_ ID はリポジトリ全体で一意。追加時は `rg "FIG_" analysis`、`rg "RUN_" analysis`、`rg "REF_" analysis` で重複がないことを確認してから追記する。
- 参照ドキュメント一覧（AI が読んでよいもの）: `analysis/slides_outline.md`（スライド骨子）、`analysis/run_catalog.md`（代表 run メタ）、`analysis/figures_catalog.md`（図のインデックス）、`analysis/glossary.md`（用語タグ）、`analysis/literature_map.md`（文献と役割マップ）。
- `analysis/*.md` を追加・更新したら `make analysis-sync` → `make analysis-doc-tests` → `python -m tools.evaluation_system --outdir <run_dir>` を実行し、`function_reference_rate≥0.75`・`anchor_consistency_rate≥0.98` を維持していることを確認する（`<run_dir>` は直近の out/ パスを指定）。DocSyncAgent でアンカーを同期してから評価すること。
- スライド生成向け analysis ファイルの役割: `analysis/slides_outline.md` は 10 枚固定のコア＋オプションを並べた骨子、`analysis/run_catalog.md` はドキュメントで使ってよい RUN_* を列挙するレジストリ、`analysis/figures_catalog.md` は FIG_* の唯一のインデックス、`analysis/glossary.md` は用語・記法のマップ、`analysis/literature_map.md` は REF_* と主要論文の対応表。数式は常に `analysis/equations.md` を単一ソースとし、各ファイルはアンカー参照のみで再タイプセットしない。
- FIG_ / RUN_ / REF_ の ID は必ず一意にし、新規追加前に重複を検索すること。これらのファイルを変更した場合も DocSyncAgent → analysis-doc-tests → evaluation_system の順に束で回し、`function_reference_rate≥0.75` と `anchor_consistency_rate≥0.98` を崩さない。
- スライド生成エージェントの読み方: 並びと意図は `slides_outline.md`、使う run/fig は `run_catalog.md` / `figures_catalog.md` から選び、用語と引用は `glossary.md` と `literature_map.md` で確定した上で `analysis/equations.md` のアンカーを参照する。

## analysis カタログ群の役割（AI向け）
- `analysis/slides_outline.md`: 著者向けスライド骨子。AIはここからSxx ID順にサマリを生成し、人間読みの流れを崩さずに要約する。
- `analysis/run_catalog.md`: 重要 run の索引。`configs/*` と `out/*/run_card.md` の対応を橋渡しし、再実行や比較対象の選択に使う。
- `analysis/figures_catalog.md`: 再利用したい図のカタログ。fig_idとrun_id, eq_refsを紐付け、スライド生成時の図選択ガイドとする。
- `analysis/glossary.md`: 用語・記法のテーブル。対象読者や数学レベルのタグ付きで、AIが表記ゆれを避けるための辞書として扱う。
- `analysis/literature_map.md`: Hyodo+, Ronnet+, Kuramoto 2024 など主要論文とステータス（replicated/planned/reference_only）をまとめた表。AIは引用や位置づけ確認にのみ使用し、式を再掲しない。

## ラベルとアンカーの補足規約
- 数式のアンカー(E.xxx)は `analysis/equations.md` のみで定義し、他のドキュメントは参照に徹する。新しい E.xxx を他所に作らない。
- スライドID(Sxx_*), run ID(RUN.*), 図ID(FIG.*)はリポジトリ全体で一意に保つ。存在しない ID を AI が使いたい場合は、`UNKNOWN_REF_REQUESTS` に従い相談または TODO(REF:slug) として記録し、捏造しない。

## DocSync と coverage メモ
- `analysis/*.md` を編集したら DocSyncAgent（`python -m tools.doc_sync_agent --all --write` か `make analysis-sync`）でアンカー同期→`make analysis-doc-tests` で `function_reference_rate≥0.75` と `anchor_consistency_rate≥0.98` を確認する。新カタログ（run_catalog / figures_catalog / glossary / literature_map）も coverage 対象に含まれる。
- 現在のカバレッジ状況（[coverage.json](file:///Users/daichi/marsshearingsheet/analysis/coverage/coverage.json) / [coverage_report.md](file:///Users/daichi/marsshearingsheet/analysis/coverage/coverage_report.md)）を参照し、未文書化関数（holes）の削減に努める。
- `analysis/assumptions_overview.md`: 仮定タグと式・設定・コードパスの対応を自動生成したメモ。`python -m analysis.tools.render_assumptions` で更新し、DocSync/coverage ガードの対象に含める。

## out/ ディレクトリの扱い
- `out/` は Git 無視でドキュメントソースではない。`analysis/run_catalog.md` は `out/*/run_card.md` を出典とするパターンを示し、参照先が消えた場合は該当 run_id を `deprecated` にし、同じ ID を黙って再利用しない。

# 設定の要点（YAML→スキーマ→実行）
設定値はYAML→Pydantic→実行時オブジェクトの順に検証される。（[marsdisk/run.py:357-357], [marsdisk/schema.py:456-456]）

- CLIの `--override path=value` は YAML 読み込み後の辞書にマージされ、`load_config` と CLI エントリポイントで共通に処理される。複数指定は `--override a=b --override c=d` またはスペース区切りで指定可能。（[marsdisk/run.py:388-388], [marsdisk/run.py:1649-1654]）
- `physics.blowout.enabled`,`radiation.freeze_kappa`,`surface.freeze_sigma`,`shielding.mode`,`psd.floor.mode` などの物理トグルはスキーマで検証され、`run_zero_d` 内でブローアウト損失や遮蔽、床径進化を切り替える。（[marsdisk/schema.py:343-343], [marsdisk/run.py:1032-1100]）
- `sinks.mode` は既定で`sublimation`、`none`を選ぶと昇華とガス抗力を同時に停止し、追加シンクの有効化は `SinkOptions` を通じて昇華パラメータ `SublimationParams(**cfg.sinks.sub_params.model_dump())` にコピーされる。HKL 既定値は SiO（`psat_model="clausius"`, μ=0.0440849 kg/mol, α=0.007, A=13.613, B=17850, `valid_K=[1270,1600]`）。`psat_model="tabulated"` を指定すると外部テーブルから `log10P` を読み込む。（[marsdisk/schema.py:263-265], [marsdisk/run.py:701-706], [marsdisk/physics/sublimation.py:220-227], [marsdisk/physics/sinks.py:83-160]）
- `sinks.mode="none"` の場合は `t_sink=None` が `surface.step_surface` に渡り、光学的厚さが与えられてもシンク項は無効のまま推移する。（[marsdisk/run.py:1011-1016], [marsdisk/physics/surface.py:190-196]）
- `e_mode` / `i_mode` を設定しない場合は従来どおり入力スカラー `e0` / `i0` を使用するが、`mars_clearance` / `obs_tilt_spread` を指定すると Δr サンプリングや観測傾斜を乱数で生成して初期条件を再設定する。`dr_min_m`/`dr_max_m`（m）や`i_spread_deg`（度）と `rng_seed` を併用して再現性を確保する。（[marsdisk/schema.py:189-199], [marsdisk/run.py:519-519]）
- 火星温度は `radiation.TM_K` または `mars_temperature_driver.constant` のいずれかが必須で、採用経路は `T_M_source` に `radiation.TM_K` / `mars_temperature_driver.constant` / `mars_temperature_driver.table` として記録される（`temps.T_M` は廃止）。[marsdisk/config_utils.py:44–48][marsdisk/physics/tempdriver.py:275–341][marsdisk/run.py:1032–1180]

# 最小粒径と軽さ指標（データ契約）
PSDの下限は `psd.floor.mode` に応じて設定値・ブローアウト境界・`ds/dt` 派生値の最大で評価され、辞書 `"s_min_components"` に `config` / `blowout` / `effective` / `floor_mode` / `floor_dynamic` を保持する。（[marsdisk/schema.py:218-220], [marsdisk/run.py:701-705]）ブローアウト境界（[marsdisk/physics/radiation.py:250-258]）が主因となり、`"evolve_smin"` モードでは HKL 由来の `|ds/dt|Δt` が `s_min_floor_dynamic` として単調に蓄積される。（[marsdisk/run.py:773-778], [marsdisk/physics/psd.py:267-356]）

放射圧と重力の比率を表す軽さ指標（β）は `s_min_config` と `s_min_effective` で別々に評価され、それぞれ `beta_at_smin_config` と `beta_at_smin_effective` として記録される。（[marsdisk/run.py:676-676], [marsdisk/physics/radiation.py:236-241]）`beta_threshold` は定数 0.5 で、βが閾値以上なら `case_status="blowout"`（ブローアウト抑止時は `"no_blowout"`）、未満なら `"ok"` となる。（[marsdisk/physics/radiation.py:32-32], [marsdisk/run.py:677-684], [scripts/sweep_heatmaps.py:1261-1264]）

# 出力ファイルの中身（機械可読の約束）
`summary.json`の主要キーは次のとおり。

| キー | 意味 | 単位 | 記録箇所 |
| --- | --- | --- | --- |
| `M_loss` | 吹き飛び損失とシンク損失の合計 | M_Mars | [marsdisk/run.py:2708-2723] |
| `M_out_cum` / `M_sink_cum` | 各経路の累積損失 | M_Mars | [marsdisk/run.py:2708-2723] |
| `case_status` | 軽さ指標によるケース分類 (`blowout` / `ok` / `no_blowout`) | 文字列 | [marsdisk/run.py:2556-2636] |
| `beta_threshold` | 軽さ指標の閾値 | 無次元 | [marsdisk/physics/radiation.py:32-32], [marsdisk/run.py:2556-2636] |
| `beta_at_smin_config` / `beta_at_smin_effective` | 設定・有効下限でのβ | 無次元 | [marsdisk/run.py:2556-2636] |
| `s_min_config` / `s_min_effective` | YAML指定とクリップ後の最小粒径 | m | [marsdisk/run.py:1080-1150], [marsdisk/run.py:2680-2685] |
| `s_min_effective_gt_config` | 有効下限が設定値より大きいか | 真偽値 | [marsdisk/run.py:2682-2685] |
| `s_min_components` | `config`/`blowout`/`effective`/`floor_dynamic` 等を保持 | m | [marsdisk/run.py:1089-1096], [marsdisk/run.py:1336-1434], [marsdisk/run.py:2680-2685] |
| `T_M_used` / `T_M_source` | 使用温度と出典ラベル | K / 文字列 | [marsdisk/run.py:2556-2636] |
| `rho_used` / `Q_pr_used` | 材料密度と Planck 平均効率 | kg/m³ / 無次元 | [marsdisk/run.py:2556-2636] |
| `mass_budget_max_error_percent` | ステップ最大質量誤差 | % | [marsdisk/run.py:2334-2351], [marsdisk/run.py:2670-2678] |
| `dt_over_t_blow_median` | ブローアウト時間に対するΔt中央値 | 無次元 | [marsdisk/run.py:2334-2351], [marsdisk/run.py:2670-2678] |
| `mass_budget_violation` | 許容超過時の詳細（オプション） | 辞書 | [marsdisk/run.py:2334-2351], [marsdisk/run.py:2768-2770] |

- `series/run.parquet`で最低限確認する列は次のとおり。

  - `time` / `dt`：通算時刻とステップ幅。[marsdisk/run.py:2120-2185]
  - `prod_subblow_area_rate`：光学クリップ後に混合された供給率[kg m⁻² s⁻¹]。[marsdisk/run.py:2120-2185]
  - `M_out_dot` / `M_sink_dot`：吹き飛び・追加シンクの瞬時流出率[M_Mars s⁻¹]。[marsdisk/run.py:2120-2185]
  - `mass_lost_by_blowout` / `mass_lost_by_sinks`：累積損失[M_Mars]。[marsdisk/run.py:2120-2185]

- `series/diagnostics.parquet` では幾何吸収量や遮蔽を追跡できる。`F_abs`,`psi_shield`,`kappa_Planck`,`tau_eff`,`sigma_surf`,`s_peak`,`M_out_cum` を確認し、遮蔽モードやPSD床の挙動をレビューする。（[marsdisk/run.py:1287-1327], [marsdisk/io/writer.py:80-171]）

<!-- AUTOGEN:AI_USAGE PRACTICES START -->

# アンカー規約
- `marsdisk/...` の参照はすべて `[path/to/file.py:start–end]` 形式に統一する。関数名ハッシュや `#symbol` 付きアンカーは禁止。
- アンカーの解決は `analysis/inventory.json` と `analysis/symbols.raw.txt` を基にする。新しい関数・クラスを追加した際は必ず `python -m tools.doc_sync_agent --all --write` を実行し、行範囲を再解決する。
- 既存アンカーが外れた場合は、同期コマンドを走らせた後で差分を確認し、必要なら `analysis/tools/check_docs.py --strict` の WARN/ERROR を根拠に修正する。
- モジュール全体を参照する必要があっても `#__module__` アンカー以外の直書きを許可しない。根拠となるセクションを作り、該当関数を列挙すること。

# 日次チェック手順
1. `python -m tools.doc_sync_agent --all --write`
   既存アンカーの行範囲を再解決し、新規シンボルを同期する。`tests/` や `configs/` への参照もここで更新される。
2. `python analysis/tools/make_coverage.py`
   `analysis/coverage/coverage.{json,md}` を更新し、参照率と未解決リストを最新化する。
3. `python analysis/tools/check_docs.py --strict`
   70%未満の参照率・行範囲ずれ・単位不足を検出し、WARN も ERROR へ昇格させる。

すべて成功したら `git status` で差分を確認し、CI やチーム共有用のメモを残す。

# 未解決参照の管理プロセス (UNKNOWN_REF_REQUESTS)
コードやドキュメント内で出典が不明確な仮定や、外部文献による裏付けが必要な箇所が見つかった場合は、安易に `TODO` コメントで済ませず、以下の手順で構造化データとして登録する。

1.  **登録**: `analysis/UNKNOWN_REF_REQUESTS.jsonl` に新しい JSON 行を追加する。
    *   `slug`: 一意な識別子（例: `tl2003_surface_flow_scope_v1`）
    *   `type`: `assumption` (仮定), `citation_needed` (要出典), `parameter_justification` (パラメータ根拠) など
    *   `where`: 該当ファイルと行範囲
    *   `assumptions`: 具体的な仮定の内容
    *   `priority`: `high`, `medium`, `low`
2.  **参照**: コードやドキュメントの該当箇所には、登録した slug を用いて `TODO(REF:slug)` と記述する。これにより、将来の自動化ツールがこの参照を追跡可能になる。
3.  **解決**: 調査により出典が判明した場合は、`analysis/references.registry.json` に文献情報を登録し、`UNKNOWN_REF_REQUESTS.jsonl` からエントリを削除（または解決済みフラグを付与）した上で、コード内の `TODO(REF:slug)` を `[@Key]` 形式の正式な引用に置き換える。

このプロセスにより、「なんとなく書かれた仮定」を排除し、全ての設計判断が文献または明示的な合意に基づいている状態（Provenance）を維持する。

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
スイープ集計では互換カラムとして`beta_at_smin`が残り、新フィールドが利用可能なら`beta_at_smin_config`と`beta_at_smin_effective`を優先し、旧カラムは後方互換のために並列表記される。（[scripts/sweep_heatmaps.py:1252–1256]定義（概ね994–1012行））自動処理では新フィールドを参照し、欠損時のみ旧カラムで補う方針を推奨する。

# 代表レシピ
**ブローアウトのみ（baseline_blowout_only.yml）** `sinks.mode: "none"`と`enable_sublimation: false`がセットされ、`t_sink=None`が表層解法に渡るため`mass_lost_by_sinks`は全行で0になる。（analysis/run-recipes/baseline_blowout_only.yml, [marsdisk/run.py:1447-1463][marsdisk/run.py:1654-1683][marsdisk/run.py:2120-2185]）実行後に`python -c "import pandas as pd; df=pd.read_parquet('analysis/outputs/baseline_blowout_only/series/run.parquet'); print(df['mass_lost_by_sinks'].sum())"`などでゼロを確認する。

**スイープの最小例** `scripts/sweep_heatmaps.py`はマップ定義と出力CSVを自動構築し、集計CSVに軽さ指標の新旧両カラムと`case_status`を列挙する。（[scripts/sweep_heatmaps.py:1261-1522]）`python scripts/sweep_heatmaps.py --map 1 --outdir sweeps/map1_demo --jobs 4`を用いると、結果CSVに`beta_at_smin_config`,`beta_at_smin_effective`,`beta_at_smin`が同時に含まれ、互換項目との整合を確認できる。

# よくある落とし穴
- 代表半径は `disk.geometry.r_in_RM/r_out_RM` から解決され、欠損すると 0D 実行は例外を投げるため、YAML で必ず `disk.geometry` を与える（`geometry.r` は廃止）。[marsdisk/config_utils.py:37–43][marsdisk/run.py:1032–1180]
- 温度上書きの出典を混同しないよう、`radiation.TM_K`を使った場合はsummaryの`T_M_source`が`"radiation.TM_K"`になる点を確認する。（[marsdisk/run.py:568-568], [marsdisk/run.py:1417-1420]）
- `pyarrow`未導入だとParquet書き出しが失敗するので、CI環境では事前に依存関係を導入する。（[marsdisk/io/writer.py:24-103]）

# 検証チェックリスト（短縮版）
- `sinks.mode`が`none`のケースでは`mass_lost_by_sinks`の総和が0になることを確認する。（[marsdisk/run.py:1072-1250]）
- `case_status`が`beta_at_smin_config`と`beta_threshold`の比較結果に一致するかをsummaryで確認する。（[marsdisk/run.py:1406-1409], [marsdisk/physics/radiation.py:32-32]）
- `checks/mass_budget.csv`で`error_percent`が0.5%以下かを検査し、超過時は`--enforce-mass-budget`再実行を検討する。（[marsdisk/run.py:1330-1357]）

# 付録：用語の一行定義
- 軽さ指標（放射圧比 β, radiation pressure ratio）：放射圧と重力の比を表し、0.5を超えると粒子が吹き飛ぶ。（[marsdisk/physics/radiation.py:236-241]）
- ブローアウト半径（blow-out radius）：軽さ指標が0.5になる粒径で、`s_min`クリップの基準になる。（[marsdisk/physics/radiation.py:250-258]）
- Strubbe–Chiang 衝突時間（Wyatt legacy collisional time）：`t_{\rm coll}=1/(\Omega\tau_{\perp})` として評価する表層の衝突寿命。（[marsdisk/physics/surface.py:81-87]）
- 光学的厚さ（optical depth）：遮蔽判断に使う厚さ指標で、`sigma_tau1`によるクリップの上限を定める。（[marsdisk/physics/surface.py:190-196]）
