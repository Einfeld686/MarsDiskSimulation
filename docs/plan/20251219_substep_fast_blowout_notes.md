# サブステップ導入メモ（fast blowout 用）

> 目的: ChatGPT などにサブステップ案を検討させる際、必要な前提と接続点を一覧化する。  
> 日付: 2025-12-19

---

## 本プロジェクト・ドキュメントについて

### プロジェクト概要

本リポジトリ（MarsDiskSimulation / `marsshearingsheet`）は、**火星ロッシュ限界内の高密度ダストディスク**を対象に、放射圧によるブローアウトと衝突破砕カスケードを2年間シミュレーションして質量損失・流出率を定量化するものです。詳細は以下を参照してください：

- **全体仕様**: [analysis/overview.md](analysis/overview.md)
- **物理モデル式**: [analysis/equations.md](analysis/equations.md)
- **実行レシピ**: [analysis/run-recipes.md](analysis/run-recipes.md)
- **AI向け利用ガイド**: [analysis/AI_USAGE.md](analysis/AI_USAGE.md)

### 用語定義

本ドキュメントで使用される主な用語を以下に定義します：

| 用語 | 意味 | 参考 |
|------|------|------|
| **ブローアウト (blowout)** | 放射圧が重力を上回り、粒子が系外へ吹き飛ばされる現象。β≥0.5 で発生 | (E.004), (E.005) |
| **β（軽さ指標）** | 放射圧と重力の比。$\beta = F_{\rm rad}/F_{\rm grav}$。0.5 を超えると粒子がブローアウト | (E.004) |
| **t_blow（ブローアウト時間）** | ブローアウトが完了するまでの時間スケール。$t_{\rm blow} = \chi_{\rm blow}/\Omega$ | — |
| **dt/t_blow 比** | タイムステップ幅とブローアウト時間の比。大きいと数値誤差が増加 | — |
| **サブステップ (substep)** | dt/t_blow が大きいとき、ブローアウト項のみを細分化して精度を保つ手法 | — |
| `substep_fast_blowout` | サブステップ機能の有効化フラグ（`io` セクション） | [run_zero_d.py](marsdisk/run_zero_d.py) |
| `substep_max_ratio` | サブステップ発動の閾値。dt/t_blow がこれを超えると細分化。デフォルト 1.0（実質無効）、運用値 0.3–0.5 | [run_zero_d.py](marsdisk/run_zero_d.py) |
| `fast_blowout_factor` | 高速ブローアウト補正係数。粗いステップでの誤差を補正 | — |
| `fast_blowout_factor_avg` | サブステップ時の `dt_sub` 重み平均補正係数 | — |
| **M_out_dot** | 瞬時の質量流出率（$\dot{M}_{\rm out}$）。ジグザグはサブステップで緩和可能 | — |
| **Ω（ケプラー角速度）** | 軌道半径 r での軌道周期に対応する角速度 | (E.001) |
| **headroom** | $\Sigma_{\tau=1} - \Sigma_{\rm surf}$。供給ゲートの開閉を決定 | (E.031) |
| `collision_solver` | 衝突解法モード。`surface_ode`（表層ODE）または `smol`（Smoluchowski） | [schema.py](marsdisk/schema.py) |
| `substep_active` | 当該ステップでサブステップが有効化されたかのフラグ（出力列） | — |

### ドキュメントの位置付け

`docs/plan/` 内のドキュメントは開発プラン・イシュー整理・振り返りを管理します。本メモは **fast blowout（高速ブローアウト）問題に対するサブステップ導入**の検討資料であり、外部AI（ChatGPT等）へ相談する際の前提情報を整理したものです。

関連ドキュメント：
- [20251219_tau_clip_gate_review.md](docs/plan/20251219_tau_clip_gate_review.md) — τクリップと供給ゲートの現状整理
- [20251216_temp_supply_sigma_tau1_headroom.md](docs/plan/20251216_temp_supply_sigma_tau1_headroom.md) — 供給クリップ事象の報告
- [20251220_supply_headroom_policy_spill.md](docs/plan/20251220_supply_headroom_policy_spill.md) — headroom 超過時の spill モード提案

---

## 背景と問題点

### 問題点
大きなタイムステップ `dt` を使用すると、ブローアウト時間 `t_blow` に対して `dt/t_blow` が大きくなり、以下の問題が発生する：

1. **数値誤差の増加**: ブローアウトが 1 ステップで完了するため、物理的な時間発展を正確に追跡できない
2. **M_out_dot のギザギザ**: 質量流出率が不連続に見え、解析が困難
3. **質量収支のずれ**: 急激な変化により質量保存の誤差が蓄積しやすい

### 解決策：サブステップ導入
`dt/t_blow > substep_max_ratio` のステップのみを細分化し、ブローアウト項を小さな `dt_sub` で反復計算する。これにより：

- 全体の計算コストを抑えつつ、問題のあるステップのみ精度を向上
- M_out_dot の滑らかさを改善
- 質量誤差を許容範囲（< 0.5%）に維持

---

## 現行実装の入口
- トグル: `io.substep_fast_blowout`（bool）、`io.substep_max_ratio`（float）。`run_zero_d` 内で `dt/t_blow > substep_max_ratio` のときのみサブステップ分割を行う。[marsdisk/run_zero_d.py で dt_over_t_blow 判定]
- ブローアウト時間: `t_blow = chi_blow_eff / Omega`。`chi_blow_eff` は β=0.5 を基準に `radiation` モジュールで決定。[marsdisk/physics/radiation.py]
- 追加安全弁: `numerics.dt_over_t_blow_max`（例 0.1）。ここを下げると dt 自体を縮める挙動と併用できる。
- 出力: `out/<run_id>/series/run.parquet` に `fast_blowout_factor`, `fast_blowout_ratio`, `fast_blowout_flag_gt3/gt10`, `n_substeps` が記録される。[marsdisk/io/writer.py メタデータ]

## 既知の制約・注意
- サブステップはブローアウト項のみに適用（Smol 内部の衝突計算を細分化するわけではない）。
- `io.substep_fast_blowout` をオンにしても headroom=0 なら供給は流れず、ジグザグ改善は限定的。
- hard gate のままなので、サブステップは「滑らかにする」ための手段であって「供給を通す」手段ではない。
- 現状、`substep_max_ratio` のデフォルトは 1.0（実質無効）。運用上は 0.3–0.5 などへの引き下げを検討中。

## 検討時に必要な環境情報
- 代表設定: `configs/sweep_temp_supply/temp_supply_T6000_eps1.yml` など（dt=20 s, shielding.mode=psitau, supply.const × epsilon_mix）。
- 代表出力: `out/<run_id>/series/run.parquet` で `dt_over_t_blow`, `n_substeps`, `M_out_dot` を確認すると効果が見える。
- 典型スケール: `t_orb ≈ 1.5e4 s`（r≃1.85 RM）、`t_blow ≈ 1/Omega ≃ 2.4e3 s`。`dt=20 s` なら `dt/t_blow ≃ 8e-3` なので、サブステップが効くのはさらに短い t_blow（高速ブローアウト補正が必要な領域）や粗い dt のケース。

## 期待するアウトカム
- ジグザグ（M_out_dot, sigma_surf）の緩和：大きな dt でもブローアウトの速さを部分的に解像。
- 質量収支: サブステップ導入で質量誤差が増えないこと（`out/<run_id>/checks/mass_budget.csv` |error|<0.5% 維持）。
- 速度: 全ステップ細分化ではなく「dt/t_blow が閾値超えのステップだけ」細分化し、総計算時間の増加を抑える。

## 実装反映メモ（サブステップ導入後）

### 変更一覧

| 変更箇所 | 内容 | ファイル |
|----------|------|----------|
| **サブステップ判定** | `collision_solver=surface_ode` かつ `dt/t_blow > substep_max_ratio` のみ有効化 | [run_zero_d.py](marsdisk/run_zero_d.py) |
| **n_substeps 計算** | `ceil(dt / (substep_max_ratio * t_blow))` で分割数を決定 | [run_zero_d.py](marsdisk/run_zero_d.py) |
| **サブステップ反復** | 遮蔽→供給→deep buffer→`surface.step_surface` を `dt_sub` で反復 | [run_zero_d.py](marsdisk/run_zero_d.py) |
| **Smol 経路** | 常に `n_substeps=1`（サブステップ無効）。`fast_blowout_factor` は元の `dt/t_blow` 基準を維持 | [run_zero_d.py](marsdisk/run_zero_d.py) |
| **新規出力列** | `substep_active` 列を追加 | [writer.py](marsdisk/io/writer.py) |
| **平均化変更** | `fast_blowout_factor_avg` を `dt_sub` 重み平均に変更 | [run_zero_d.py](marsdisk/run_zero_d.py), [writer.py](marsdisk/io/writer.py) |
| **スキーマ更新** | `io.substep_max_ratio` のデフォルト 1.0（実質無効）、運用値 0.3–0.5 を明示 | [schema.py](marsdisk/schema.py) |
| **回帰テスト** | surface_ode でサブステップ有効、smol では無効、質量誤差≦0.5% を検証 | [test_fast_blowout.py](tests/integration/test_fast_blowout.py) |

### 出力カラム詳細

| カラム名 | 型 | 単位 | 説明 |
|----------|-----|------|------|
| `fast_blowout_ratio` | float | 無次元 | `dt / t_blow` の値 |
| `fast_blowout_factor` | float | 無次元 | 単一ステップでの補正係数 |
| `fast_blowout_factor_avg` | float | 無次元 | サブステップ時の `dt_sub` 重み平均補正係数 |
| `fast_blowout_flag_gt3` | bool | — | `dt/t_blow > 3` かどうか |
| `fast_blowout_flag_gt10` | bool | — | `dt/t_blow > 10` かどうか |
| `n_substeps` | int | — | 実行されたサブステップ数（通常 1） |
| `substep_active` | bool | — | 当該ステップでサブステップが有効化されたか |

### 互換性
- 既存の `fast_blowout_factor`, `fast_blowout_ratio`, 瞬時 `M_out_dot` との互換性を保持
- `substep_fast_blowout=false`（デフォルト）の場合、従来と完全に同一の挙動

## ChatGPT 等に依頼するときの指示サンプル
- 入力: 上記設定ファイルと出力例、`run_zero_d.py` のサブステップ判定箇所。
- 相談したい点:
  - 適切な `substep_max_ratio` の推奨レンジ（精度 vs コスト）。
  - サブステップ時の出力の平均化／積分の取り方（現状は per-substep の累積をステップ値として記録）。
  - Smol 衝突項への拡張の要否（今回は scope 外の可能性を明記）。
- ゴール: 20 s 全体 dt を保ちつつ、M_out_dot のギザツキを減らし、質量誤差と計算時間を許容範囲に収める設定指針を得る。

## 参考

### 関連ドキュメント
- 物理式の詳細: [analysis/equations.md](analysis/equations.md)
- シミュレーション実行方法: [analysis/run-recipes.md](analysis/run-recipes.md)
- AI向け利用ガイド: [analysis/AI_USAGE.md](analysis/AI_USAGE.md)

### コード参照
| 機能 | ファイル | 備考 |
|------|----------|------|
| サブステップ判定・実行 | [run_zero_d.py](marsdisk/run_zero_d.py) | `dt_over_t_blow` 判定、`n_substeps` 計算 |
| ブローアウト時間計算 | [radiation.py](marsdisk/physics/radiation.py) | `chi_blow_eff`, β=0.5 基準 |
| 出力メタデータ定義 | [writer.py](marsdisk/io/writer.py) | `fast_blowout_*` 列の記録 |
| 数値設定スキーマ | [schema.py](marsdisk/schema.py) | `numerics.dt_over_t_blow_max` 等 |
