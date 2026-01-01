外部供給（内側→表層 ODE）導入プラン
==============================

> **ステータス**: 実装完了（2026-01-01更新）

## 実装完了状況

以下の機能が実装済み：

- ✅ `tools/derive_supply_rate.py`: μ → R_base 変換ユーティリティ（262行）
  - CLI インターフェース（`--mu`, `--sigma-tau1`, `--t-blow`, `--epsilon-mix`, `--format`）
  - r×μ グリッド出力機能
- ✅ `marsdisk/physics/supply.py`: 外部供給パラメータ処理（547行）
  - `SupplyTableConfig` クラス: テーブル形式の供給率サポート
  - `SupplyTemperatureTable` クラス: 温度依存テーブル
  - `get_prod_area_rate` 関数
- ✅ `analysis/equations.md`: (E.027a) として μ の式を記載
- ✅ `analysis/run-recipes.md`: 使用例を記載
- ✅ `tests/integration/test_external_supply_pipeline.py`: テスト実装

---

目的と背景
----------
- 現行の S1 表層 ODE は供給項 (dotSigma_prod) を時間一定の入力として受け取り、ブローアウト・衝突・追加シンクとは独立に扱う設計。
- 内側ディスクから表層への供給強度を「表層がブローアウトだけを受けるときの平衡面密度」と「光学的厚さ 1 の面密度 Σ_tau=1 の比」で表す無次元 μ
  μ = (dotSigma_prod * t_blow) / Σ_tau=1  （ここで t_blow = 1/Omega(r), gas-poor S1 ODE 前提）
  として制御し、時間発展中のブローアウトや衝突フラックスに供給量が引きずられない形で「定常供給」を実装する。
- gas-poor を既定としつつ、外部供給 μ スイープをオプションとして追加し、analysis の run-recipes・ドキュメントと整合するコード・テストを整備する。

対象スコープ
-----------
- 0D 実行パスの表層供給設定（`supply` セクション）と S1 表層 ODE への受け渡し経路。
- μ, Σ_tau=1, t_blow, ε_mix から定数供給率 R_base を決めるユーティリティ（YAML 断片生成または CLI オーバーライド用）。
- `shielding` モードが `fixed` か `psitau` かで Σ_tau=1 基準値が変わる場合の扱い方針（μ の定義とリンクさせて明記）。
- r 依存の R_base 出力（r×μ グリッド）は「0D ケースを複数半径で回すための補助」として含める。1D 粘性拡散・本格的な半径 ODE 連成は範囲外。

非対象
-----
- gas-rich / TL2003 型の表層フロー導入（`ALLOW_TL2003` はデフォルト無効のまま）。
- 1D 半径拡張や粘性拡散（C5）の実装。

進め方（ドラフト）
-----------------
1. 仕様整理  
   - μ の定義を analysis/equations.md に追記。t_blow = 1/Omega(r)（gas-poor S1 ODE 前提）を明記。  
   - ブローアウトのみの定常解 Σ_eq = μ Σ_tau=1 を書き下し、追加シンクがある場合の Σ_eq = μ Σ_tau=1 / (1 + t_blow/t_coll + t_blow/t_sink) をコメントとして残す。  
   - `shielding.mode` と `sigma_tau1_fixed` による Σ_tau=1 の違いを整理。標準: `shielding.mode="fixed"`＋`sigma_tau1_fixed` を μ 基準に。拡張: `psitau` の場合は t=0, r=r0 で評価した Σ_tau=1 を μ 定義用に凍結し、時間変化は有効 μ の変化として扱う。
2. 実装検討  
   - μ, Σ_tau=1, t_blow, ε_mix から R_base を計算する `tools/derive_supply_rate.py` を設計。既存 `get_prod_area_rate` が ε_mix を掛けるので、raw rate として R_base = (μ Σ_tau=1)/(ε_mix t_blow) と定義し二重掛けを防ぐ。  
   - CLI 案: `python -m tools.derive_supply_rate --mu 0.3 --sigma-tau1 1.0 --t-blow 1000 --epsilon-mix 1.0` → 標準出力 `prod_area_rate_kg_m2_s=<value>`。`--format yaml` で `supply: { mode: "const", const: { prod_area_rate_kg_m2_s: ... } }`。  
   - 半径依存: `--r` を受けて Ω(r) 計算を `grid.Omega_kepler` に委譲。必要に応じ `--rho` `--T_M` `--qpr` を受けるがデフォルトは YAML 値。`--format csv --r-grid "2.0,2.5,3.0" --mu-grid "0.1,0.3,1.0"` で r×μ グリッドを作り `supply.mode=table` 用 CSV を生成。`piecewise` モードも検討。
3. テスト計画  
   - R_base 計算の単体: ε_mix=1, μ=0.5, Σ_tau=1=1e2, t_blow=1e3 → R_base=5e-5 を期待値にし、CLI 出力・YAML 出力のキーと値を検証。  
   - S1 ODE 短時間ステップ: collision/sink をオフ、ブローアウトのみで R_base を入力し、Σ_surf が μ Σ_tau=1 に収束するか確認。`shielding.mode="fixed"` と `psitau` を両方テストし、psitau では μ 定義時の Σ_tau=1 と Σ_tau=1(t) の差を記録。
4. ドキュメント  
   - analysis/run-recipes.md に μ 指定→`supply.const.prod_area_rate_kg_m2_s` 決定手順を追記。μ=0.1,1.0 を例示し、光学的厚さが 1 を大きく超えない範囲で μ を選ぶ注意書きを入れる。  
   - config_guide.md に μ 由来設定例を追加（`epsilon_mix: 0.3` と `prod_area_rate_kg_m2_s` を derive_supply_rate の出力で置換）。
5. 実行と検証  
   - 代表ケース（μ=0.1, 1.0）で `python -m marsdisk.run --config configs/base.yml --override ...` を実行し、`out/series/run.parquet` の `prod_subblow_area_rate` と `M_out_dot` を確認。ブローアウトのみのケースでは後半 `M_out_dot ≃ dotSigma_prod × 2π r Δr`（0D 相当）かつ Σ_surf が μ Σ_tau=1 に近づくことをチェック。  
   - DocSyncAgent → analysis-doc-tests → evaluation_system の通常フローを実施し、ドキュメントとコードの整合を確認。

ユーティリティ案（μ→R_base）の整理版
---------------------------------
- 目的: μ, Σ_tau=1, t_blow, ε_mix から定数供給率 R_base を計算し、YAML 断片や CLI オーバーライド文字列を生成する。  
- インターフェース案:  
  - `python -m tools.derive_supply_rate --mu 0.3 --sigma-tau1 1.0 --t-blow 1000 --epsilon-mix 1.0` → 標準出力 `prod_area_rate_kg_m2_s=<value>`  
  - `--format yaml` で `supply: { mode: "const", const: { prod_area_rate_kg_m2_s: ... } }` を出力  
  - `--r` `--rho` `--T_M` `--qpr` で半径・物性指定、Ω(r) は `grid.Omega_kepler`。  
  - `--format csv --r-grid "2.0,2.5,3.0" --mu-grid "0.1,0.3,1.0"` で r×μ グリッドを吐き、`supply.mode=table` 用 CSV を生成。  
- 省力化: `--config` で YAML から `supply.mixing.epsilon_mix` や `shielding.fixed_tau1_sigma` を既定値として取得し、さらに `MARS_DISK_SIGMA_TAU1` / `MARS_DISK_EPSILON_MIX` 環境変数をデフォルト源として使う。通常は `--mu` と `--r` だけで済ませる運用を想定。  
- 計算式: R_base = (μ Σ_tau=1) / (ε_mix t_blow)。R_base は `supply.const.prod_area_rate_kg_m2_s` に対応し、`get_prod_area_rate` が ε_mix を掛けるためここで除外する。  
- 例外処理: ε_mix ≤ 0, t_blow ≤ 0, Σ_tau=1 ≤ 0 はエラーで終了（非有限値も拒否）。  
- 出力利用:  
  1) 単発: `--override supply.const.prod_area_rate_kg_m2_s=<R_base>` を実行コマンドに渡す。  
  2) テーブル生成: CSV 出力を `supply.mode="table"` の入力にし、r と μ を掃いた複数ケースを一括実行。  
- テスト案: ε_mix=1, μ=0.5, Σ_tau=1=1e2, t_blow=1e3 → R_base=5e-5 を期待値とし、テキスト・YAML 出力の値とキー名を確認。

リスクと対策（再整理）
---------------------
- Σ_tau=1 定義の不一致による μ 基準ずれ → `shielding.mode="fixed"` ケースを必ずテストし、`psitau` 時は μ 定義時の Σ_tau=1 と実効 Σ_tau=1(t) の差をログに記録。  
- ε_mix の二重掛け → derive_supply_rate で ε_mix を分離し、単体テストで担保。  
- gas-rich 感度との混同 → 本プランは `ALLOW_TL2003=false` を前提とし、`configs/scenarios/gas_rich.yml` は参照のみ（実行対象外）。
