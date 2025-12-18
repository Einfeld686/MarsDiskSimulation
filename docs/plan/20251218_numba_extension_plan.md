# Numba 適用範囲拡張計画

**作成日**: 2025-12-18  
**ステータス**: 提案中  
**対象**: `marsdisk/physics/` 内の残存 NumPy ホットスポット

---

## 概要

本計画は、シミュレーション高速化のために Numba JIT 適用範囲を拡張するための施策を整理する。現状分析の結果、主要なホットスポットは既に Numba 化済みであり、追加の高速化対象は限定的である。

> フォーカス: **Numba が無効化された環境（`MARSDISK_DISABLE_NUMBA=1` や JIT 失敗時フォールバック）での性能劣化を最小化する**。通常運用（Numba 有効）は現状のままで十分速い。

---

## 現状分析

### ✅ Numba 適用済み（JIT 化完了）

| 関数 | ファイル | 計算量 | 並列化 |
|------|---------|-------|-------|
| `compute_weights_table_numba` | `_numba_kernels.py:70` | O(n²) | ❌ |
| `fill_fragment_tensor_numba` | `_numba_kernels.py:114` | O(n²) | ✅ `prange` |
| `gain_from_kernel_tensor_numba` | `_numba_kernels.py:170` | O(n³) | ✅ `prange` |
| `collision_kernel_numba` | `_numba_kernels.py:185` | O(n²) | ✅ `prange` |
| `collision_kernel_bookkeeping_numba` | `_numba_kernels.py:218` | O(n²) | ✅ `prange` |

> [!NOTE]
> 上記の関数は自動的に Numba 版が優先される設計（`_USE_NUMBA` フラグ）になっている。

### ⚠️ Numba 未適用の候補

| 関数 | ファイル | 計算量 | 優先度 |
|------|---------|-------|-------|
| `compute_prod_subblow_area_rate_C2` | `collide.py:123-152` | O(n²) | 低（現行パス未使用） |
| IMEX loss 計算 `loss = np.sum(C, axis=1)` | `smol.py:275` | O(n²) | 低 |
| `compute_mass_budget_error_C4` | `smol.py:310-350` | O(n) | 低 |
| `_gain_tensor` / `_fragment_tensor` フォールバック | `smol.py:159-175` / `collisions_smol.py:324-365` | O(n³) | 中（Numba無効時のみ） |

---

## 追加 Numba 化の検討

### 候補1: `compute_prod_subblow_area_rate_C2`

```python
# collide.py:147-149
n = C.shape[0]
idx = np.triu_indices(n)
rate = float(np.sum(C[idx] * m_subblow[idx]))
```

**分析**:
- 計算量は O(n²) だが `np.triu_indices` + ベクトル演算で既に効率的
- **現行パスでは呼び出しされていない**（`smol.py` で import のみ）
- 仮にループ内に入れても毎ステップ1回のみ
- **効果見込み: 低**（NumPy のベクトル化が十分高速）

### 候補2: IMEX loss 計算

```python
# smol.py:275
loss = np.sum(C, axis=1)
```

**分析**:
- O(n²) だが単純な行和
- NumPy の BLAS レベル演算で既に高速
- **効果見込み: 低**

### 候補3: `compute_mass_budget_error_C4`

**分析**:
- O(n) の単純な内積
- オーバーヘッドに対して計算量が小さい
- **効果見込み: 無視できる**

### 候補4: `_gain_tensor` / `_fragment_tensor` フォールバック

**分析**:
- Numba 有効時は `_numba_kernels` のカーネルが支配するが、無効化されると三重ループ/`np.einsum` が走り O(n³) 支配になる
- Numba を無効化する CI/デバッグ環境での時間短縮にはここを JIT 化するのが最も効く
- **効果見込み: 中（Numba無効時）**

### 候補5: O(n)〜O(n²) 前処理のバンドルJIT

**候補例**: `supply_mass_rate_to_number_source`（powerlaw 分岐）、`_blowout_sink_vector`、`compute_kernel_e_i_H`、`kernel_minimum_tcoll`  
**分析**: 全体コストへの寄与は小さいが、非Numba環境でのオーバーヘッド均しには一定の効果。  
**効果見込み: 低**

---

## 結論（方針アップデート）

> [!IMPORTANT]
> **可能な限り全ての候補に Numba を導入し、Numba 無効環境でも JIT 経路で性能を維持する。**
>
> 理由:
> 1. フォールバック経路（`_gain_tensor` / `_fragment_tensor`）が O(n³) で支配的になるため、ここを JIT しておくと MARSDISK_DISABLE_NUMBA=1 でも実行時間を短縮できる。
> 2. 低コストな内積・行和も JIT しておけば、NumPy 依存を減らし一貫性を高められる。
> 3. `_NUMBA_FAILED` での自動フォールバックを維持しつつ、失敗時にも別 JIT 経路を用意することで運用上のリスクを抑える。

---

## 推奨施策（Numba 以外）

以下の施策がより効果的である:

標準ビン数は 40（推奨レンジ 30–60）のまま維持し、性能要件が厳しい CI/デバッグのみ短時間レシピで調整する。

| 優先度 | 施策 | 効果 | 工数 |
|-------|-----|------|------|
| **1** | 並列スイープ `--jobs N` | コア数倍 | 環境設定のみ |
| **2** | Codespaces 16-32 コア活用 | 4〜16倍 | `.devcontainer` 設定 |
| **3** | CI/デバッグ用に `n_bins` を 30–40 に維持した短時間レシピを用意 | 1.5〜3倍 | 設定追加のみ |

詳細は [20251212_simulation_performance_optimization.md](20251212_simulation_performance_optimization.md) を参照。

---

## （参考）将来の検討事項

Numba 拡張を行う場合の留意点:

1. **数値一致テストの追加**
   - 既存テスト: `tests/integration/test_fragment_tensor_numba.py`
   - パターン: Numba 版と NumPy 版の結果を `np.allclose()` で比較

2. **フォールバック機構の維持**
   - `_NUMBA_FAILED` フラグによる自動フォールバック
   - 環境変数 `MARSDISK_DISABLE_NUMBA=1` で明示的無効化

3. **ベンチマーク手順**
   ```bash
   # 現状計測
   time python -m marsdisk.run --config configs/base.yml
   
   # Numba 無効で比較
   MARSDISK_DISABLE_NUMBA=1 time python -m marsdisk.run --config configs/base.yml
   ```

---

## 検証計画

本計画は実装を伴わないため、検証は不要。

---

## 関連ドキュメント

- [20251212_simulation_performance_optimization.md](20251212_simulation_performance_optimization.md) — 包括的な高速化計画
- marsdisk/physics/_numba_kernels.py — 既存 Numba カーネル
- tests/integration/test_fragment_tensor_numba.py — 既存テスト

---

## 追加タスク候補（優先度の目安）

1. **非NumbaフォールバックのJIT化（中）**  
   - `_gain_tensor` フォールバックを専用 `njit` に切り出し、`_NUMBA_FAILED` にも適用できるようにする。  
   - `_fragment_tensor` の純Python三重ループを `njit` した代替を用意し、`MARSDISK_DISABLE_NUMBA=1` 時の計算時間を短縮。

2. **軽量前処理のバンドルJIT（低）**  
   - `supply_mass_rate_to_number_source`（powerlaw 分岐のみ）、`_blowout_sink_vector`、`compute_kernel_e_i_H`、`kernel_minimum_tcoll` をまとめて JIT し、非Numba環境のオーバーヘッドを均す。

3. **未使用関数の扱い整理（低）**  
   - `compute_prod_subblow_area_rate_C2` は現行パス未使用である旨を docstring に明記し、必要ならテスト付きでパスに組み込む。Numba 化は用途が固まってから。

4. **運用ガイド更新（中）**  
   - CI/デバッグで `MARSDISK_DISABLE_NUMBA=1` を使う場合のショートレシピを `analysis/run-recipes.md` に追加し、`n_bins`=30–40 の範囲で実行時間を抑える手順を残す。

---

## 実装タスク（Numba 導入の具体ステップ）

1. **新規カーネル追加（_numba_kernels.py）**  
   - `compute_prod_subblow_area_rate_C2_numba`（上三角内積、手動ループ）  
   - `loss_sum_numba`（行和）  
   - `mass_budget_error_numba`（質量誤差計算）  
   - `gain_tensor_fallback_numba`（三重和）  
   - `fragment_tensor_fallback_numba`（weights 計算込み三重ループ）  
   - 軽量前処理セット: `supply_mass_rate_powerlaw_numba` / `blowout_sink_vector_numba` / `compute_kernel_e_i_H_numba` / `kernel_minimum_tcoll_numba`

2. **呼び出し側の切り替え**  
   - collide.py / smol.py / collisions_smol.py で `_USE_NUMBA and not _NUMBA_FAILED` を流用し、Numba 版→失敗時 NumPy 版へフォールバック。  
   - 形状チェックや `MarsDiskError` は呼び出し前に実施し、カーネル内の分岐を最小化。

3. **テスト整備**  
   - NumPy vs Numba 一致テストを追加（prod_subblow, loss_sum, mass_budget_error, gain/fragment fallback）。  
   - `MARSDISK_DISABLE_NUMBA=1` でフォールバックもカバー。  
   - 既存 `tests/integration/test_fragment_tensor_numba.py` にフォールバック経路の一致と性能サニティを追記。

4. **ベンチマークとガイド更新**  
   - `configs/base.yml` で `time python -m marsdisk.run`、および `MARSDISK_DISABLE_NUMBA=1` で計測し、効果を記録。  
   - `analysis/run-recipes.md` に NumPy/Numba 両モードの所要時間メモを追加し、CI 用ショートレシピ（n_bins 30–40）を掲載。  
   - 実測例（Numba有効・軽量設定）: `numerics.t_end_years=1e-4`, `io.stream.parquet=false` で実行時間 `real ≈ 4.2s`（環境: pyenv 3.10.4）。

---

## 進捗チェック

- [x] 新規 Numba カーネルの実装（上三角内積、行和、質量誤差、gain/fragment フォールバック、軽量前処理）
- [x] 呼び出し側の切り替え（collide.py / smol.py / collisions_smol.py での JIT 適用とフォールバック維持）
- [x] テスト追加（NumPy/Numba 一致・フォールバック経路の検証）
- [x] ベンチマーク計測（短時間設定での所要時間取得）
