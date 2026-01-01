# 温度×μスイープの可視化プラン（0D・gas-poor前提）

目的と背景
----------
- `T=2000/4000/6000 K` × `μ=1/0.1` の 6 ケースについて、破砕供給と表層アウトフローの時間発展と累積損失を比較可視化する。
- 既に `out/<run_id>` の 2 ケースが存在。残り 4 ケースを待ちつつ、先行 2 本で図の仕様を固める。
- gas-poor 既定（`ALLOW_TL2003=false`）を前提とし、分析結果は run_card に依拠して参照のみ行う（詳細仕様は analysis/ をシングルソースとする）。

このプランを読む人の前提
----------------------
- リポジトリや出力構造を知らない前提で、フォルダやカラム名を明示する。
- 0D の標準実行は `python -m marsdisk.run --config <yaml>` で `out/<timestamp>_<tag>__<sha>__seed<n>/` を生成する。今回の tag は `temp_supply_T{T}_eps{eps}` 形式。
- `eps` は混合効率 `mixing.epsilon_mix` の略。`mu` は昇華モデルの平均分子量 [kg/mol] を指す。

出力ファイルの最小構成と主カラム（知らない人向け）
----------------------------------------------
- `out/<run_id>/summary.json`: 集計スカラー。
  - 主要キー: `M_loss`, `M_out_cum`, `M_sink_cum` (いずれも火星質量単位), `case_status`, `s_min_effective`, `beta_at_smin_effective`, `mass_budget_max_error_percent`, `dt_over_t_blow_median`, `T_M_used`, `mu_used`。
- `out/<run_id>/series/run.parquet`: 時系列（pandas/pyarrow で読める）。
  - 必須列: `time` [s], `dt` [s], `prod_subblow_area_rate` [kg m^-2 s^-1], `M_out_dot` [M_Mars s^-1], `M_sink_dot` [M_Mars s^-1], `mass_lost_by_blowout` [M_Mars], `mass_lost_by_sinks` [M_Mars], `s_min` [m], `beta_at_smin_effective`, `Sigma_tau1` [kg m^-2], `dt_over_t_blow`, `fast_blowout_flag_gt3/gt10`。
- `out/<run_id>/series/diagnostics.parquet`（存在する場合）: 遮蔽などの補助列。
  - 例: `tau_eff`, `psi_shield`, `kappa_Planck`, `fast_blowout_factor`, `n_substeps`。
- `out/<run_id>/checks/mass_budget.csv`: C4 質量検査ログ。`error_percent` が 0.5% 未満であることを確認する。
- `out/<run_id>/run_config.json` / `out/<run_id>/run_card.md`: 実行時の設定・温度ソース・Q_pr テーブル・物理トグル（特に `allow_TL2003`）を確認する。

対象・非対象
------------
- 対象: `configs/sweep_temp_supply/` 由来の 0D 実行結果（`out/<run_id>/summary.json`, `out/<run_id>/series/run.parquet`, `out/<run_id>/checks/mass_budget.csv`, `out/<run_id>/run_config.json`, `out/<run_id>/run_card.md`）。
- 非対象: 1D 半径拡張や TL2003 有効化シナリオ、SiO₂ 冷却サブプロジェクト（別プラン扱い）。

入力フォルダと必要データ
------------------------
- 想定出力: `out/<timestamp>_temp_supply_T{2000|4000|6000}_eps{0p1|1}__<sha>__seed<rng>/`
- 使用ファイル: `out/<run_id>/summary.json`（集計）、`out/<run_id>/series/run.parquet`（主要時系列）、`out/<run_id>/checks/mass_budget.csv`（C4 監査）、`out/<run_id>/run_config.json`/`out/<run_id>/run_card.md`（前提確認）、`out/<run_id>/series/diagnostics.parquet` があれば遮蔽確認。
- 6 ケース揃い次第、欠損なく読み込めるかを最初に確認し、`out/<run_id>/checks/mass_budget.csv` の |error_percent|<0.5% を満たさないものは別フラグを立てる。

可視化アウトプット案
--------------------
1. 単体ケース（各 outdir ごと）
   - `M_out_dot` と `prod_subblow_area_rate` の時系列重ね描きで供給→アウトフロー応答を確認（時間は年単位の線形軸、必要なら対数も併用）。
   - `s_min`（有効下限）と `beta_at_smin_effective` の時系列でブローアウト境界の推移を表示。
   - `Sigma_tau1` / `tau_eff` と `psi_shield`（存在する場合）の推移で遮蔽クリップの有無を可視化。
   - 安定性メトリクス: `dt_over_t_blow` と `fast_blowout_flag_gt3/gt10` の時系列をフラグ表示し、粗いステップの影響を注記。
2. 横断 6 ケース比較
   - 集約表: `T`, `mu`, `M_loss`, `M_out_cum`, `M_sink_cum`, `case_status`, `s_min_effective`, `beta_at_smin_effective`, `mass_budget_max_error_percent`, `dt_over_t_blow_median` を 1 行にまとめた CSV。
   - 棒グラフ: `M_loss` を x 軸=T, 色=μ で表示（累積損失の温度依存と μ 依存を確認）。
   - 折れ線: `M_out_dot` の代表ケース重ね描き（温度固定で μ を比較、μ 固定で温度を比較の 2 種）。
   - 折れ線: `s_min` 終端値と時間推移を温度別に並べ、`beta_at_smin_effective` と対で吹き飛び強度を示す。
   - ヒートマップ（任意）: (T, μ) を軸に `M_loss` または `M_out_cum` を塗り分け、欠損はハッチで明示。

実施手順
--------
1. 出力収集: 6 ケースの outdir をリスト化（先行 2 ケースは固定）。存在しない組み合わせは `missing` ラベルでプレースホルダ行を作る。
2. 集計スクリプト案（pandas/pyarrow 前提）:
   - summary.json から主要スカラーを読み込み、集約表を生成して `out/<timestamp>_temp_supply_viz__/summary_table.csv` に書き出す。
   - series/run.parquet から必要列を抜き出し、プロットに使う DataFrame をキャッシュ（例: feather）。
3. 可視化:
   - matplotlib ベースで上記プロットを作成し、`out/<timestamp>_temp_supply_viz__<sha>/figs/` に PNG 保存。ファイル名は `runid_metric.png` 形式（例: `T2000_mu0p1_Mout.png`）。
   - `out/<run_id>/checks/mass_budget.csv` の最大誤差が閾値超のケースには図や凡例に `(mass budget warn)` を付記。
4. 記録:
   - `out/<run_id>/run_card.md` から T, μ, Q_pr テーブル、`physics_controls`（特に `allow_TL2003`）を転記せずに引用し、可視化ノートを別途 `out/<timestamp>_temp_supply_viz__<sha>/figs/notes.md` に残す。
   - 必要に応じて analysis/run_catalog.md への run 追加は別コミットで行い、ここでは方針のみ。

読み込みスニペット例（外部ツール向け）
------------------------------------
```python
import json, pandas as pd, pyarrow.parquet as pq, glob
outdirs = sorted(glob.glob("out/*_temp_supply_*"))
rows = []
for od in outdirs:
    try:
        s = json.load(open(f"{od}/summary.json"))
    except FileNotFoundError:
        continue
    rows.append({
        "outdir": od,
        "T": s.get("T_M_used"),
        "mu": s.get("mu_used") or s.get("mu"),
        "M_loss": s.get("M_loss"),
        "case_status": s.get("case_status"),
        "s_min_effective": s.get("s_min_effective"),
        "beta_at_smin_effective": s.get("beta_at_smin_effective"),
        "mass_budget_err_%": s.get("mass_budget_max_error_percent"),
    })
df = pd.DataFrame(rows)
print(df)
# 時系列のサンプル列取得
if outdirs:
    tbl = pq.read_table(f"{outdirs[0]}/series/run.parquet", columns=[
        "time","M_out_dot","prod_subblow_area_rate","s_min","beta_at_smin_effective"
    ])
    ts = tbl.to_pandas()
    print(ts.head())
```

リスクと緩和
------------
- 欠損ケース: 4 ケース未着手の場合は集約表で `missing` を明示し、図は取得済み 2 本の重ね描きに限定。
- データ欠落（diagnostics.parquet 不在など）: 遮蔽系プロットは省略可能とし、存在列のみで描画する条件分岐をスクリプトに入れる。
- 安定性問題: `fast_blowout_flag_gt3/gt10` が多い run は別色ハイライトし、再実行の必要性を判断できるようにする。
- 転記過多: 詳細な式や物理説明は analysis 側を参照するだけに留め、本ファイルでは手順とアウトプット定義に限定する。

完了条件
--------
- 6 ケースの集約表（欠損は `missing`）と主要プロット群を `out/<timestamp>_temp_supply_viz__<sha>/` に配置。
- 各プロットに軸ラベル・単位・ケース識別（T, μ, run_hash）を付記し、mass budget 関連の警告があれば明示。
- 可視化用スクリプト/ノートの所在を本プランで参照でき、実行コマンド例を残す（詳細コードは今後作成）。
