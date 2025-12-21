# Q_pr lookup array / blowout_radius Numba 化（第2段階）実装プラン

**作成日**: 2025-12-19  
**ステータス**: 提案  
**対象**: `qpr_lookup_array`（T がスカラーの高速経路）、`blowout_radius`（数式評価部）

---

## 背景

- 直近の `profile.out` では `qpr_lookup_array` と `blowout_radius` が依然として累積時間の上位にあり、第2段階の JIT 化が有効と判断できる。
- 第1段階で `QPrTable.interp` のスカラー補間は Numba 化済みであり、次のボトルネックは配列補間と blowout 半径計算に絞られる。

---

## 目的

- `qpr_lookup_array` と `blowout_radius` の Python オーバーヘッドを削減し、連続ステップの累積時間を下げる。
- 数値式は変更せず、既存の入力検証・フォールバック機構を維持する。

---

## スコープ

### 対象

- `marsdisk/physics/radiation.py` の `qpr_lookup_array`（T がスカラーの高速経路）
- `marsdisk/physics/radiation.py` の `blowout_radius`（数式評価部のみ）

### 非対象

- テーブル形式・テーブル読み込み仕様の変更
- `qpr_lookup`（スカラー）自体の再設計
- `PhiTable.interp` の Numba 化（将来検討）

---

## 実装方針

### 1) `qpr_lookup_array` の Numba 化

- 新規: `marsdisk/io/_numba_tables.py` に `qpr_interp_array_numba(...)` を追加。
  - 入力: `s_vals`, `T_vals`, `q_vals`, `s_arr`, `T_scalar`
  - 出力: `s_arr` と同形の補間結果
- 実装は要素ごとの二分探索＋線形補間（Numba 互換）。
  - `np.searchsorted` を使えない場合に備え、手書きバイナリサーチも検討。
  - 端点は既存 NumPy と同じくクリップする。
- `qpr_lookup_array` では「T がスカラー」の高速経路のみ Numba を使い、T が配列のケースは現行のフォールバックを維持。
- `MARSDISK_DISABLE_NUMBA=1` と `_NUMBA_FAILED` による自動フォールバックを必須とする。

### 2) `blowout_radius` の Numba 化

- 新規: `marsdisk/physics/_numba_radiation.py`（または既存 `_numba_kernels.py`）に
  `blowout_radius_numba(rho, T_M, qpr)` を追加。
- `blowout_radius` 側では入力検証と `_resolve_qpr` を従来通り行い、
  取得済みの `rho`, `T_M`, `Q_pr` に対して数式評価のみ Numba へ委譲。
- 係数は `constants` と同一値を使用し、式 (R3) を改変しない。

### 3) 失敗時のフォールバック

- `qpr_lookup_array` / `blowout_radius` いずれも `_NUMBA_FAILED` を立て、
  次回以降は NumPy 経路に切り替える。
- 既存の warn/flag パターン（`TableWarning` 等）を踏襲する。

---

## テスト・検証

### 単体/統合テスト

- `tests/integration/test_qpr_lookup.py` に Numba 経路の一致テストを追加。
  - `qpr_lookup_array` の NumPy 経路と Numba 経路を `np.allclose` で比較。
  - Numba が無い環境は skip。
- `tests/unit/test_numba_helpers.py` または新規 `tests/unit/test_radiation_numba.py` に
  `blowout_radius_numba` の一致テストを追加。
  - `MARSDISK_DISABLE_NUMBA=1` / `_NUMBA_FAILED` によるフォールバックも確認。

### ベンチマーク

```bash
python -m cProfile -o profile.out -m marsdisk.run \
  --config configs/base.yml \
  --override numerics.t_end_years=0.01 \
  --override sizes.n_bins=40 \
  --quiet
```

- `qpr_lookup_array` / `blowout_radius` の cum 時間の改善を確認。

---

## リスクと緩和策

- **JIT 初期オーバーヘッド**: 小規模ケースでは遅くなる可能性があるため、
  配列長しきい値で NumPy に戻す運用も検討する。
- **Numba 非対応環境**: 既存の `MARSDISK_DISABLE_NUMBA` と `_NUMBA_FAILED` を維持する。
- **数値差分**: 既存テストの許容誤差を踏襲し、差分が出た場合は補間の境界処理を再確認する。

---

## 完了条件

- Numba 有効環境で `qpr_lookup_array` / `blowout_radius` が Numba 経路に入る。
- Numba 無効・失敗時は自動的に NumPy 経路へ戻る。
- 追加テストがすべて PASS し、`profile.out` で累積時間の削減が確認できる。

---

## 実装タスク（チェックリスト）

- [x] `qpr_interp_array_numba` の追加と `qpr_lookup_array` への導入
- [x] `blowout_radius_numba` の追加と `blowout_radius` への導入
- [x] Numba 経路の一致テスト追加（`qpr_lookup_array` / `blowout_radius`）
- [ ] `profile.out` を再計測して効果を確認
- [ ] 実装完了後に既存プランのチェックボックスを更新

---

## 関連ドキュメント

- `docs/plan/20251219_qpr_interp_numba_plan.md`
- `docs/plan/20251219_qpr_vectorization_and_collision_perf.md`
- `docs/plan/20251218_numba_extension_plan.md`
