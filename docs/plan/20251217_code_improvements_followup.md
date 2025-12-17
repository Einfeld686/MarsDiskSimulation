# コード整備の追加改善項目

> **作成日**: 2025-12-17  
> **関連**: [20251216_code_reorganization_for_collision_physics.md](./20251216_code_reorganization_for_collision_physics.md)（Phase 1–3 完了済み）

---

## 背景

Phase 1–3 のコード整備が完了し、以下が達成済み:
- `CollisionStepContext` 導入
- `ProgressReporter`, `StreamingState`, `ZeroDHistory` 抽出
- テストディレクトリ再構成（`unit/`, `integration/`, `research/`, `legacy/`）
- Phase5 削除、Phase7 → `extended_diagnostics` リネーム
- Coverage guard: `function_reference_rate: 0.98`, `anchor_consistency_rate: 1.0`

本ドキュメントでは、デバッグ効率と拡張性向上のための**追加改善項目**を整理する。

---

## 1. 高優先度

### 1.1 coverage holes 解消

**現状**: `analysis/coverage/coverage.json` に 2 件の未参照関数が存在

```json
"holes": [
  "marsdisk/physics/collisions_smol.py#step_collisions",
  "marsdisk/physics/radiation.py#grain_temperature_graybody"
]
```

**対応**: `analysis/equations.md` または `analysis/overview.md` に参照アンカーを追加

**工数**: 15 分

---

### 1.2 `writer.py` の Phase7 コメント更新

**現状**: `marsdisk/io/writer.py` に「Phase7」コメントが 6 箇所残存（L202–204, L226–228）

**対応**: 「Phase7 diagnostics」→「extended diagnostics」に統一

**工数**: 10 分

---

## 2. 中優先度

### 2.1 `run.py` の関数数削減

**現状**: `run.py` に 43 関数、4,825 行（目標 4,000 行以下）

**移動候補**:

| 関数群 | 移動先 | 行数 |
|--------|--------|------|
| `_resolve_time_grid`, `_resolve_seed`, `_derive_seed_components` | `marsdisk/runtime/config_helpers.py` | ~150 |
| `_parse_override_value`, `_apply_overrides_dict`, `_merge_physics_section` | `marsdisk/config_utils.py`（既存） | ~100 |
| `_human_bytes`, `_memory_estimate` | `marsdisk/utils/format.py` | ~50 |
| `_ensure_finite_kappa`, `_safe_float`, `_float_or_nan` | `marsdisk/utils/numerics.py` | ~50 |

**工数**: 2 時間

---

### 2.2 ログレベルの統一と拡充

**現状**: `collisions_smol.py` に `logger.debug()` が 1 箇所のみ

**推奨追加**:
```python
# step_collisions_smol_0d 内
logger.debug("collision kernel: t_coll=%.3e, e=%.4f, i=%.4f", t_coll_kernel, e_kernel, i_kernel)
logger.debug("fragment tensor: shape=%s, Y_max=%.3e", Y_tensor.shape, np.max(Y_tensor))
```

**工数**: 30 分

---

## 3. 低優先度

### 3.1 新規 `tmp_debug_*` ディレクトリの管理

**現状**: 7 つの `tmp_debug_*` 類似ディレクトリが存在（Git 管理外）

| ディレクトリ | 内容 |
|-------------|------|
| `tmp_debug_mass_budget`, `tmp_debug_mass_budget2` | 質量収支テスト |
| `tmp_debug_sampling` | サンプリングテスト |
| `tmp_debug_test_gate`, `_gate2`, `_gate3` | ゲート係数テスト |
| `tmp_debug_test_psat` | 蒸気圧テスト |
| `tmp_eval_fixture` | 評価フィクスチャ |

**対応**: テスト完了後に手動削除を習慣化。必要に応じて `make clean-tmp` タスク追加

---

### 3.2 Numba フォールバックのテスト強化

**現状**: `_fragment_tensor` に Numba 無効時のフォールバック処理があるが、専用テストなし

**対応**: `tests/unit/test_fragment_tensor_fallback.py` を追加し、`MARSDISK_DISABLE_NUMBA=1` 環境でのテストを実施

---

### 3.3 `DEBUG_STAGE` 環境変数の整理

**現状**: `run.py:L89` に `DEBUG_STAGE = bool(int(os.environ.get("MARSDISK_DEBUG_STAGE", "0")))`

**対応**: 利用箇所を精査し、不要なら削除。必要なら使い方をドキュメント化

---

## 完了条件

- [ ] coverage holes が 0 件
- [ ] `writer.py` の Phase7 コメントが更新されている
- [ ] `run.py` が 4,000 行以下
- [ ] 衝突物理モジュールに適切なログ出力が追加されている

---

## 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2025-12-17 | 初版作成 |
