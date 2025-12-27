# シミュレーション実行時間短縮計画

**作成日**: 2025-12-12  
**ステータス**: 提案中  
**対象**: 0D円盤シミュレーション全般

---

## 概要

本計画は、`marsdisk` シミュレーションの実行時間を短縮するための施策をまとめる。GitHub Education 特典（Codespaces, Azure for Students）の活用も視野に入れる。

---

## 現状分析

### 実装状況

| 項目 | 現状 | 備考 |
|------|------|------|
| **Numba** | v0.62.1（実測値） | 10スレッド利用可能。`requirements.txt` ではバージョン未固定のため環境依存あり |
| **Numba適用範囲** | `_fragment_tensor` + 重みテーブル生成 | `_numba_kernels.py` で `fill_fragment_tensor_numba`, `compute_weights_table_numba` が JIT 済み |
| **スイープ並列化** | `concurrent.futures` | `--jobs N` オプション対応 |
| **衝突カーネル** | 純NumPy | `compute_collision_kernel_C1` |
| **IMEX積分** | 純NumPy | `np.einsum` がホットスポット |

> [!NOTE]
> Numba のバージョンを固定する場合は `requirements.txt` に `numba>=0.60` を追記し、CI でのインストール手順を `.github/workflows/` に明記すること。

### ボトルネック箇所

1. **`smol.py:255`** — `np.einsum("ij,kij->k", C, Y)` が毎ステップ O(n³) で呼ばれる
2. **`collide.py`** — 衝突カーネル構築が O(n²)
3. **`_fragment_tensor`** — Numba化済みだがキャッシュ効率に改善余地
4. **スイープ並列化** — `ThreadPoolExecutor` + `subprocess.run` で既に別プロセス化済み

---

## 提案施策

### 施策1: サイズビン数の削減（即効性: 高）

**工数**: 設定変更のみ  
**効果**: 3〜8倍高速化

計算量は `n_bins` に対し O(n²)〜O(n³) で増加する。探索的なパラメータスイープでは粗いビン数で十分。

| n_bins | 相対時間 | 用途 |
|--------|---------|------|
| 40 | 1.0x | 最終結果・論文用 |
| 30 | ~0.4x | 中間検証 |
| 20 | ~0.15x | パラメータ探索・スクリーニング |

> [!IMPORTANT]
> スクリーニング用設定では **`n_bins` のみを変更**し、サイズ範囲 `s_min`, `s_max` はデフォルト（`[1e-6, 3] m`）を維持すること。範囲を変更すると `M_loss` や wavy PSD の再現性が変わる。

```yaml
# configs/fast_screening.yml
# ベース設定を継承し、n_bins のみ変更
sizes:
  n_bins: 20
  # s_min, s_max はデフォルト [1e-6, 3] m を維持
```

---

### 施策2: 並列スイープの強化（即効性: 高）

**工数**: 環境設定のみ  
**効果**: コア数に比例（4〜16倍）

> [!NOTE]
> 現行の `sweep_heatmaps.py` は `ThreadPoolExecutor` を使用しているが、各ケースは `subprocess.run([python, -m, marsdisk.run, ...])` で別プロセスを起動するため（[sweep_heatmaps.py:1222-1228](file:///Users/daichi/marsshearingsheet/scripts/sweeps/sweep_heatmaps.py#L1222-1228)）、**実計算は既に GIL の影響外で並列化されている**。`ProcessPoolExecutor` への変更は pickling オーバーヘッドを増やすだけで効果がない。
>
> 並列度向上には `--jobs N` の増加と、より多くのコアを持つ実行環境（Codespaces 等）の活用が有効。

#### 2b. GitHub Codespaces 活用

GitHub Education 加入者は大型インスタンス（16-32コア）を無料で利用可能。

```json
// .devcontainer/devcontainer.json
{
  "hostRequirements": {
    "cpus": 16,
    "memory": "32gb"
  }
}
```

実行例:
```bash
python scripts/sweeps/sweep_heatmaps.py --map 1 --jobs 16 --outdir sweeps/map1_fast
```

#### 2c. GitHub Actions マトリクスジョブ

CI で分散実行する場合:
```yaml
# .github/workflows/sweep.yml
jobs:
  sweep:
    strategy:
      matrix:
        part: [1, 2, 3, 4]
    runs-on: ubuntu-latest
    steps:
      - run: python scripts/sweeps/sweep_heatmaps.py --map 3 --num-parts 4 --part-index ${{ matrix.part }}
```

---

### 施策3: Numba 適用範囲の拡大（効果: 中〜大）

**工数**: 1日程度  
**効果**: 1ステップあたり 2〜5倍高速化

#### 3a. einsum の JIT 化

```python
# marsdisk/physics/_numba_kernels.py に追加

@njit(cache=True, parallel=True)
def compute_gain_numba(C: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """Numba版 gain = 0.5 * einsum('ij,kij->k', C, Y)"""
    n = C.shape[0]
    gain = np.zeros(n, dtype=np.float64)
    for k in prange(n):
        total = 0.0
        for i in range(n):
            for j in range(n):
                total += C[i, j] * Y[k, i, j]
        gain[k] = 0.5 * total
    return gain
```

#### 3b. 衝突カーネル構築の JIT 化

> [!IMPORTANT]
> 既存の `compute_collision_kernel_C1`（[collide.py:18-65](file:///Users/daichi/marsshearingsheet/marsdisk/physics/collide.py#L18-65)）は `v_rel` としてスカラーまたは `(n, n)` 行列を受け付ける。Numba 版も同等の柔軟性を維持し、数値一致ベンチマーク（小規模 `n_bins`）で検証すること。

```python
# marsdisk/physics/_numba_kernels.py に追加

@njit(cache=True, parallel=True)
def compute_collision_kernel_numba(
    N: np.ndarray,
    s: np.ndarray,
    H: np.ndarray,
    v_rel_scalar: float,
    v_rel_matrix: np.ndarray,  # shape (n, n) or empty (0, 0) if scalar mode
    use_scalar: bool,
) -> np.ndarray:
    """Numba版 compute_collision_kernel_C1（スカラー/行列両対応）
    
    既存 collide.py:compute_collision_kernel_C1 と数値一致を保証する。
    v_rel がスカラーの場合は use_scalar=True, v_rel_matrix は空行列でよい。
    v_rel が (n,n) 行列の場合は use_scalar=False, v_rel_scalar は無視される。
    """
    n = N.size
    kernel = np.zeros((n, n), dtype=np.float64)
    sqrt_2pi = np.sqrt(2.0 * np.pi)
    
    for i in prange(n):
        for j in range(n):
            s_sum = s[i] + s[j]
            H_ij = np.sqrt(H[i]**2 + H[j]**2)
            delta = 1.0 if i == j else 0.0
            
            if use_scalar:
                v = v_rel_scalar
            else:
                v = v_rel_matrix[i, j]
            
            kernel[i, j] = (
                N[i] * N[j] / (1.0 + delta)
                * np.pi * s_sum**2 * v
                / (sqrt_2pi * H_ij)
            )
    return kernel


def compute_collision_kernel_C1_numba_wrapper(
    N: np.ndarray, s: np.ndarray, H: np.ndarray, v_rel: float | np.ndarray
) -> np.ndarray:
    """Python ラッパー：既存 API との互換性を維持"""
    N_arr = np.asarray(N, dtype=np.float64)
    s_arr = np.asarray(s, dtype=np.float64)
    H_arr = np.asarray(H, dtype=np.float64)
    n = N_arr.size
    
    if np.isscalar(v_rel):
        return compute_collision_kernel_numba(
            N_arr, s_arr, H_arr, float(v_rel), np.empty((0, 0)), True
        )
    else:
        v_mat = np.asarray(v_rel, dtype=np.float64)
        if v_mat.shape != (n, n):
            raise ValueError("v_rel has wrong shape")
        return compute_collision_kernel_numba(
            N_arr, s_arr, H_arr, 0.0, v_mat, False
        )
```

**検証手順**:
1. 小規模 `n_bins=10` で既存 `compute_collision_kernel_C1` と数値一致を確認
2. `v_rel` をスカラー / 行列の両パターンでテスト
3. `tests/test_numba_kernels.py` にベンチマークを追加

---

### 施策4: タイムステップ戦略の最適化（実験的）

> [!CAUTION]
> この施策は受入条件「Δt ≤ 0.1·min t_coll,k で収束」および既定レシピ（`configs/base.yml`, `analysis/run-recipes` で `dt_over_t_blow_max: 0.05–0.1` 推奨）と矛盾する可能性がある。**本番設定には適用せず、別ブランチで実験的に検証する**こと。

**工数**: 設定変更 + 検証  
**効果**: ~2倍高速化（質量誤差増大リスクあり）

#### 実験手順

1. 別ブランチ `experiment/dt-relaxation` を作成
2. 以下の設定で実行し、質量誤差ログを収集:

```yaml
# configs/experiment_dt_relaxed.yml
numerics:
  dt_init: auto
  dt_over_t_blow_max: 0.3   # 現状 0.1 → 緩和（段階的に試行）
  safety: 0.15              # 現状 0.1 → 緩和（段階的に試行）
```

3. 検証項目:
   - `checks/mass_budget.csv` の `error_percent` が 0.5% 以内か
   - `tests/integration/test_mass_conservation.py` が PASS するか
   - IMEX 収束テストが合格するか

4. 結果を `docs/experiments/dt_relaxation_results.md` に記録

> [!WARNING]
> 質量誤差が 0.5% を超える場合、この施策は採用しない。

---

## 優先順位と実施計画

| 優先度 | 施策 | 工数 | 効果 | 備考 |
|-------|------|------|-----|------|
| **1** | n_bins 削減（スクリーニング用設定作成） | 30分 | 3-8倍 | n_bins のみ変更、s_min/s_max は維持 |
| **2** | Codespaces 大型インスタンス設定 + `--jobs` 増 | 1時間 | 4-16倍 | GitHub Education 活用、コア数に比例 |
| **3** | Numba 拡張（einsum + カーネル） | 1日 | 2-5倍/ステップ | v_rel 行列対応必須、数値一致テスト追加 |
| ~~4~~ | ~~dt パラメータ調整~~ | — | — | **実験ブランチで検証後に再評価** |

---

## 検証計画

### ベンチマーク設定

```bash
# 基準ケース（現状）
time python -m marsdisk.run --config configs/base.yml

# 各施策適用後に同一設定で計測し比較
```

### 成功基準

- [ ] スクリーニングスイープ（Map-1 全点）が1時間以内で完了
- [ ] 質量保存誤差が 0.5% 以下を維持
- [ ] wavy PSD 構造の定性的再現（n_bins=30以上で確認）
- [ ] Numba カーネルが既存実装と数値一致（相対誤差 < 1e-12）

---

## GitHub Education リソース活用まとめ

| リソース | 用途 | 設定方法 |
|---------|------|---------|
| **Codespaces** | 16-32コア並列実行 | `.devcontainer/devcontainer.json` |
| **Azure for Students** | GPU計算 or HPC | Azure Portal からサブスクリプション作成 |
| **Actions** | CI分散ジョブ | `.github/workflows/*.yml` |

---

## 関連ドキュメント

- [analysis/run-recipes.md](file:///Users/daichi/marsshearingsheet/analysis/run-recipes.md) — 実行レシピ（dt 推奨値の根拠）
- [scripts/sweeps/sweep_heatmaps.py](file:///Users/daichi/marsshearingsheet/scripts/sweeps/sweep_heatmaps.py) — スイープスクリプト
- [marsdisk/physics/_numba_kernels.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/_numba_kernels.py) — Numba カーネル
- [marsdisk/physics/collide.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/collide.py) — 既存衝突カーネル実装（v_rel 行列対応）
