# 性能改善プラン: PSD 配列キャッシュと Smol ワークスペース再利用

> **作成日**: 2025-12-27  
> **ステータス**: 計画  
> **対象**: `run_zero_d` ループの配列再確保削減（PSD/Smol 周辺）  
> **関連**: [20251217_performance_optimization_opportunities.md](./20251217_performance_optimization_opportunities.md), [20251219_qpr_vectorization_and_collision_perf.md](./20251219_qpr_vectorization_and_collision_perf.md)

---

## 背景と課題

- `run_zero_d` の **sublimation→Smol** 経路で `zeros_kernel` (n^2) と `zeros_frag` (n^3) を毎ステップ確保しており、GC 圧とアロケーションが無視できない。
- `smol.step_imex_bdf1_C3` にワークスペースを渡していないため、`gain/loss` 配列が毎回新規作成される。
- `m_k = (4/3)πρs^3` など PSD 由来の配列がステップごとに再計算され、サイズが不変なケースでは無駄が発生する。

## 目的

- **数値結果を変えずに**、`run_zero_d` 1 ステップあたりのアロケーション量を削減する。
- 0D スイープの実行時間とメモリジッタを低減する。

## 対象範囲

- 0D の `sublimation_smol_active_step` 分岐（`collision_solver != "smol"` の経路）
- PSD 由来配列（`sizes`, `widths`, `m_k`, `N_k` など）
- `smol.step_imex_bdf1_C3` のワークスペース利用

**非対象**
- 物理式・係数の変更
- 1D 拡張や衝突カーネルの抜本的改造
- Q_pr / Phi テーブルのベクトル化

---

## 実装方針

### Plan A: Smol 用ワークスペースの再利用（最優先）

1) `SmolSinkWorkspace` を `run_zero_d` 内に導入
   - `zeros_kernel`, `zeros_frag`, `zeros_source`, `ds_dt_buf`, `ImexWorkspace` を保持
   - `n_bins` が変わったときのみ作り直す
   - **スコープは run-local または thread-local** とし、スイープ/並列実行での共有を避ける

2) `sublimation_smol_active_step` で再利用
   - `fill(0.0)` による初期化のみ
   - `smol.step_imex_bdf1_C3(..., S=ws.zeros_source, workspace=ws.imex)` を使用

**期待効果**: n^3 配列の毎ステップ確保を削減し、GC とメモリ断片化を抑制。

---

### Plan B: PSD 由来配列の軽量キャッシュ

- `psd_state` に簡易キャッシュを持たせ、以下を再利用:
  - `m_k`（サイズ・密度が変わらない限り再計算しない）
  - `sizes_arr`, `widths_arr` は `np.asarray` を避けられない場合でも再参照を優先

**実装候補**
- `smol.psd_state_to_number_density` に `cache_key=(sizes_version, rho)` を追加
- `sizes_version` は `psd_state["sizes"]` が更新された時にインクリメント（in-place 更新も検出できるようにする）
- `sizes_version` が未提供の場合は `sizes` のハッシュ（例: `np.sum(sizes) + np.sum(sizes**2)`）でフォールバック

---

### Plan C: `ds_dt_k` の配列生成削減

- `sublimation_sink_from_dsdt` を **スカラー ds_dt** 経路対応に拡張
  - `ds_dt` がスカラーなら `t_sub = s / |ds_dt|` を直接計算
  - 既存の配列経路は保持し後方互換
- あるいは Plan A の `ds_dt_buf` を使って `fill` 方式に統一
  - **同値性テスト**: scalar 経路と配列経路の `S_sub_k` と `mass_loss_rate` が一致すること

---

## 影響ファイル（想定）

- `marsdisk/run_zero_d.py`（workspace 管理・呼び出し変更）
- `marsdisk/physics/smol.py`（`psd_state_to_number_density` のキャッシュ）
- `marsdisk/physics/sublimation.py`（scalar ds_dt 経路追加）

---

## 検証

- `pytest tests/integration/test_mass_conservation.py`
- `pytest tests/integration/test_surface_outflux_wavy.py`
- `pytest tests/integration/test_scalings.py`
- （追加）scalar/array 経路の一致テスト（ユニット or 既存テスト拡張）
- 可能なら短いプロファイル: `configs/base.yml`, `t_end_years=0.01` で cProfile 比較

---

## 成果物（Done 定義）

- `run_zero_d` の sublimation→Smol 経路で **ゼロ配列の毎ステップ確保が消える**
- `smol.step_imex_bdf1_C3` が **workspace 再利用**される
- 既存テストが通る（数値差なし）
- （任意）cProfile/簡易計測で `sublimation→Smol` 経路の自分時間または alloc 回数が減少

---

## 実装タスク

- [x] Plan A: `SmolSinkWorkspace` 実装と `run_zero_d` 適用
- [x] Plan B: `psd_state_to_number_density` の `m_k` キャッシュ
- [x] Plan C: `sublimation_sink_from_dsdt` の scalar 経路 or ds_dt バッファ化
- [x] 追加テスト（scalar vs array 同値性）
- [x] プロファイル比較と簡易メモリ測定（必要なら）
