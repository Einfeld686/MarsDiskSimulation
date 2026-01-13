# ADR 0001: IMEX-BDF(1) ソルバーを破砕-表層結合の基盤とする

- 日付: 2024-05-26
- ステータス: 承認済み
- 文書種別: 記録（Architecture Decision Record）
- 関連仕様: `analysis/run-recipes.md:12–76`, `analysis/equations.md (E.010)–(E.011)`

## 背景
- 0D円盤の完成条件では 2 年分の Smoluchowski + 表層 ODE を継続させつつ、質量保存誤差を 0.5% 未満に抑えたまま `out/checks/mass_budget.csv` を生成することが必須とされている（`analysis/run-recipes.md:37–76`）。
- 破砕で生成された sub-blow-out 粒子の供給（C1–C3, P1, F1–F2, D1–D2）と表層剥離（R1–R3, S0–S1）が常時カップリングされるため、loss 項目だけでも $\frac{1}{t_{\rm blow}} + \frac{1}{t_{\rm coll}} + \frac{1}{t_{\rm sink}}$ が動的に切り替わる。[marsdisk/physics/surface.py#step_surface_density_S1 [L110–L192]]
- 既存の `analysis/equations.md (E.010)` / `(E.011)` では IMEX-BDF(1) の安定条件（lossを陰的、gain/sinkを陽的）と質量誤差測定を共有し、`marsdisk/physics/smol.py#psd_state_to_number_density [L72–L156]` が単ステップの adaptivity (`safety=0.1`) と質量許容値 (`mass_tol=5e-3`) を保証している。

## 決定
IMEX-BDF(1) を `marsdisk/physics/smol.py#psd_state_to_number_density [L72–L156]` で正式採用し、loss（$C_{ij}$ に由来する $\Lambda_i$）は陰的解法、gain と外部 sink `S_k` は陽的に扱う。時間刻みは

1. 行毎の損失率 $\Lambda_i$ から $t_{\rm coll,i}$ を計算し、`safety` 倍の最小値で $\Delta t_{\max}$ を制限する。
2. 陽更新により負値が出た場合や (E.011) の質量検査で `mass_tol` を超えた場合は刻みを 1/2 ずつ短縮する。

Surface/PSD モジュールは `run_zero_d` から得る `prod_subblow_mass_rate` と `S_k` を IMEX solver に渡し、更新後の `N_k` を `analysis/equations.md (E.007)` の表層 ODE に接続して `M_out_dot` を再評価する。[marsdisk/run_zero_d.py#run_zero_d [L1392–L5987]]

## 代替案
1. **完全陽的オイラー** — 計算量は最小だが、Wyatt スケールで $\Delta t \le 0.1\min t_{\rm coll}$ としても数十ビンの PSD では即座に発散した。wavy PSD をテストする `tests/integration/test_surface_outflux_wavy.py#test_blowout_driven_wavy_pattern_emerges [L10–L37]` でも負の粒子数が発生するため却下。
2. **全陰的 BDF1** — 損失・生成・シンクを同時に陰的化する案。非線形ソルバやヤコビアンの組み立てが必要で、1 ステップごとに dense solve を行うコストが 0D 要求に対して過剰。
3. **安定化 Runge–Kutta (ARK2/3)** — 2 段以上のステージを備えた IMEX Runge–Kutta。gain/sink の評価回数が増える割に、各ステージで (E.011) の質量ログを確保するフックが複雑になる。

## 影響
- RTM (`analysis/traceability/rtm.csv`) で REQ-MASS-BUDGET の設計要素として `marsdisk/physics/smol.py#psd_state_to_number_density [L72–L156]` を指名し、仕様→式→テスト→成果物の対応を固定化する。
- `numerics.dt_safety_factor` と `numerics.mass_budget_tol` は IMEX パラメータを YAML から切り替えるフラグであり、将来的に値を変更する際は本 ADR を改版して挙動差分を記録する。
- `tests/integration/test_mass_conservation.py#test_imex_bdf1_limits_timestep_and_preserves_mass [L10–L42]` が dt 制限と質量ログ (E.011) を検証し、`tests/integration/test_scalings.py#test_strubbe_chiang_collisional_timescale_matches_orbit_scaling [L16–L23]` や `tests/integration/test_surface_outflux_wavy.py#test_blowout_driven_wavy_pattern_emerges [L10–L37]` と合わせて数値安定性・物理再現性の基準を形成する。
- 出力 `out/checks/mass_budget.csv` の `error_percent` と `summary.json["mass_budget_max_error_percent"]` は RTM で定義した誤差しきい値 (0.5%) に直結し、CI が退行を検知する一次指標となる。

## フォローアップ
- IMEX-BDF(2) や adaptive-order スキームを検証する際は、本 ADR を supersede する 000x 番台を追加し、`tests/integration/test_mass_conservation.py` へ新シナリオを足して差分を計測する。
- 粒径ビン数を 60 以上に増やした場合の性能計測を `analysis/run-recipes.md` に追記し、`safety` 設定の最適値をレビューする。
