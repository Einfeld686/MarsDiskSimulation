# 性能改善プラン: collisions_smol / smol の重点最適化

> **作成日**: 2025-12-28  
> **ステータス**: 統合済み  
> **対象**: `marsdisk/physics/collisions_smol.py`, `marsdisk/physics/smol.py` のホットパス  
> **根拠**: 0D cProfile (`configs/mars_0d_baseline.yaml`, `t_end_years=0.01`)  
> **統合先**: [20251228_profile_hotspots_improvement_plan.md](docs/plan/20251228_profile_hotspots_improvement_plan.md)  
> **関連**: [20251227_psd_workspace_reuse_plan.md](docs/plan/20251227_psd_workspace_reuse_plan.md)

---

## 背景と重点区間

0D cProfile で `collisions_smol` / `smol` が支配的だったため、以下の局所最適化を計画する。

- `collisions_smol.step_collisions` 累積 ≈ 15.3s
- `collisions_smol._fragment_tensor` 累積 ≈ 7.5s
- `smol.step_imex_bdf1_C3` 累積 ≈ 3.4s
- `smol._gain_tensor` 累積 ≈ 2.6s
- `qstar.compute_q_d_star_array` 累積 ≈ 2.9s
- `collide.compute_collision_kernel_C1` 累積 ≈ 2.7s

---

## 目的

- `collisions_smol` / `smol` の **再計算コストとアロケーション** を削減する。
- 物理式や数値結果を変えずに **キャッシュ/ワークスペースで短縮**する。

---

## 対象 / 非対象

**対象**
- `_fragment_tensor` の前計算・キャッシュ
- Q_D* 計算の再利用
- `smol._gain_tensor` のサイズ依存前計算
- 供給分配 `supply_mass_rate_to_number_source` の重み再利用

**非対象**
- 物理式の変更
- スキーマ拡張や出力フォーマットの変更
- 1D 拡張や衝突カーネル全体の改造

---

## 追加最適化候補（優先順）

### 1) `_fragment_tensor` の weights_table キャッシュ

**対象**: `marsdisk/physics/collisions_smol.py` `_fragment_tensor`

- `compute_weights_table_numba(edges, alpha)` を毎ステップ計算しているため、
  `(edges_version, alpha_frag)` をキーに **weights_table をキャッシュ**する。
- `edges_version` は PSD 更新時にインクリメント（`psd_state` に保持）。
- **無効化条件**: `edges_version` または `alpha_frag` が変わった場合のみ再生成。

**期待効果**: `fill_fragment_tensor_numba` 前の前処理負荷の削減。

---

### 2) `_FRAG_CACHE` のキー軽量化

**対象**: `marsdisk/physics/collisions_smol.py` `_fragment_tensor`

- 現状のキーは `tuple(sizes_arr.tolist())` 等を毎回生成するため、
  `sizes_version / edges_version` を使った短いキーに置換。
- サイズが同一かつ `rho / v_rel / alpha` が一致すれば再利用。
- `sizes_version` が未提供時は従来の fingerprint フォールバック。
- **無効化条件**: `sizes_version`・`edges_version`・`rho`・`v_rel`・`alpha_frag` のいずれかが変化。

**期待効果**: Python 側のキー生成コスト削減。

---

### 3) サイズ依存のワークスペース化

**対象**: `marsdisk/physics/collisions_smol.py` `_fragment_tensor`

- `size_ref`, `m1`, `m2`, `m_tot`, `valid_pair` はサイズ固定で不変。
- `sizes_version` と `rho` をキーに thread-local で再利用。
- **無効化条件**: `sizes_version` または `rho` が変化（`m1/m2/m_tot` は密度依存）。

**期待効果**: outer 演算・マスク生成の削減。

---

### 4) Q_D* 行列の再利用（スカラー v_rel 重点）

**対象**: `marsdisk/physics/collisions_smol.py` `_fragment_tensor`

- `qstar.compute_q_d_star_array(size_ref, rho, v_rel)` は重い。
- `v_rel` がスカラーかつ `sizes_version` が同一なら
  `(sizes_version, rho, v_rel, qstar_signature)` をキーにキャッシュ。
- **無効化条件**: `qstar_signature`（係数テーブル/μ/単位系）が変化したら必ず破棄。

**期待効果**: Q_D* 計算の削減。

---

### 5) `smol._gain_tensor` のサイズ依存前計算

**対象**: `marsdisk/physics/smol.py` `_gain_tensor`

- `m_sum` と `denom` は `m_k` が固定なら不変。
- `ImexWorkspace` に `m_sum/denom` を持たせるか、
  専用の `GainWorkspace` を追加。
- **無効化条件**: `m_k` が変化（`sizes_version` または `rho` 変更）したら再計算。

**期待効果**: `m_sum`/`denom` 再計算を削減。

---

### 6) 供給分配の重みキャッシュ

**対象**: `marsdisk/physics/collisions_smol.py` `supply_mass_rate_to_number_source`

- `initial_psd` / `powerlaw_bins` の重み計算は
  `s_inj_min/max`, `q`, `widths`, `s_min_eff` が不変なら再利用可能。
- `prod_rate` だけスケーリングする方式に変更。
- **無効化条件**: `s_min_eff` が変化したら必ず再計算（注入ビンが変わるため）。

**期待効果**: 供給分配の計算コスト削減。

---

## 実装方針

- すべて **thread-local か run-local** のキャッシュに限定する。
- `sizes_version` / `edges_version` で無効化できるようにする。
- キャッシュ使用時でも **結果配列は read-only** にして破壊的変更を防ぐ。
- **数学的一致の条件**: `rho`, `s_min_eff`, `qstar` 係数（テーブル/μ）など物理パラメータが変わる場合はキャッシュを必ず破棄する。

---

## 検証

- 既存: `pytest tests/integration/test_mass_conservation.py`
- 既存: `pytest tests/integration/test_surface_outflux_wavy.py`
- 既存: `pytest tests/integration/test_scalings.py`
- 新規: キャッシュ有/無での数値一致テスト（小規模、固定乱数）
- 0D cProfile 再測定（`t_end_years=0.01`）
- **安全実装チェックリスト**
  - 不変条件の明文化（`sizes_version`, `edges_version`, `rho`, `s_min_eff`, `qstar` 係数/μ/単位系, `alpha_frag`, `v_rel`）
  - run-local / thread-local に限定（run 跨ぎ再利用は禁止）
  - キャッシュ配列の read-only 化と必要時のみコピー
  - PSD 更新時の version インクリメント（in-place 変更検知）
  - キャッシュ有/無の数値一致テスト（誤差 < 1e-10）
  - 0D cProfile の再測定で改善確認
  - キャッシュ上限の明記（サイズ/エントリ数）
  - キャッシュヒット率・無効化理由の DEBUG ログ（必要なら）

---

## Done 定義

- `_fragment_tensor` の累積時間が 20% 以上削減（同条件の cProfile）
- `collisions_smol` / `smol` の数値出力が一致（誤差 < 1e-10）
- テストが通る

---

## 実装タスク

- [ ] `edges_version` の導入と更新（PSD 更新時）
- [ ] weights_table のキャッシュ（edges_version + alpha）
- [ ] `_FRAG_CACHE` キー軽量化（sizes_version/edges_version）
- [ ] サイズ依存ワークスペースの thread-local 化
- [ ] Q_D* 行列キャッシュ（scalar v_rel）
- [ ] `_gain_tensor` の前計算ワークスペース
- [ ] 供給分配重みのキャッシュ
- [ ] 追加テストと cProfile 再測定
