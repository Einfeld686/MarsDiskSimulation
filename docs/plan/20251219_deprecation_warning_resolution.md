# Deprecation 警告解消プラン

> **作成日**: 2025-12-19  
> **ステータス**: ドラフト

---

## 背景

pytest 実行時に以下の deprecation 警告が発生している：

1. **Pydantic V1 スタイル警告** — `@validator` / `@root_validator` が Pydantic V3 で削除予定
2. **`compute_s_min_F2` 非推奨警告** — レガシーヘルパーの使用

これらを計画的に解消し、将来の Pydantic 3.0 リリースへの備えと警告クリーンなテスト実行を実現する。

---

## 対象警告

### 1. Pydantic V1 スタイル警告

**発生箇所**: `marsdisk/schema.py`（21+ `@validator`, 7+ `@root_validator`）

**警告メッセージ**:
```
PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated.
Deprecated in Pydantic V2.0 to be removed in V3.0.
```

**対象行** (主要なもの):
| 行 | デコレータ | クラス |
|----|-----------|--------|
| L32 | `@root_validator(pre=True)` | `Geometry` |
| L66 | `@root_validator(skip_on_failure=True)` | `DiskGeometry` |
| L109 | `@root_validator(pre=True)` | `InnerDiskMass` |
| L148 | `@root_validator(pre=True)` | `SupplyMixing` |
| L156 | `@validator` | `SupplyMixing` |
| L245 | `@validator` | `SupplyFeedback` |
| L522 | `@validator` | `Material` |
| L545 | `@validator` | `Temps` |
| L645 | `@validator` | `Initial.MeltPSD` |
| L744 | `@root_validator` | `Dynamics` |
| L750 | `@validator` | `Dynamics` |

### 2. `compute_s_min_F2` 非推奨警告

**発生箇所**: `marsdisk/physics/fragments.py` (L217–248)

**警告メッセージ**:
```
DeprecationWarning: compute_s_min_F2 is deprecated; use max(s_min_cfg, blowout_radius) instead.
```

**呼び出し元**:
- `tests/integration/test_qstar_fragments.py` (L7, L26)
- `tests/unit/test_sublimation.py` (L5, L20–23)

---

## 提案変更

### Phase 1: テスト警告の整理（低リスク）

#### [MODIFY] [test_sublimation.py](file:///Users/daichi/marsshearingsheet/tests/unit/test_sublimation.py)

- `pytest.warns(DeprecationWarning)` を明示的にテスト
- 警告抑制ではなく警告発生の検証に変更

#### [MODIFY] [test_qstar_fragments.py](file:///Users/daichi/marsshearingsheet/tests/integration/test_qstar_fragments.py)

- `compute_s_min_F2` 呼び出しを `max(s_min, blowout_radius)` パターンへ更新
- または `pytest.warns` でラップして警告を検証

---

### Phase 2: Pydantic V2 ネイティブ移行

> [!WARNING]
> Phase 2 は既存プラン [`20251212_simulation_methodology_cleanup.md`](file:///Users/daichi/marsshearingsheet/docs/plan/20251212_simulation_methodology_cleanup.md) と統合して実施。重複作業を避けるため、本プランでは Phase 1 のみを対象とする。

**移行パターン**:

```diff
- from pydantic import validator, root_validator
+ from pydantic import field_validator, model_validator, ValidationInfo

- @validator("field_name")
- def _check(cls, value, values):
+ @field_validator("field_name")
+ @classmethod
+ def _check(cls, value: T, info: ValidationInfo) -> T:
```

---

### Phase 3: `compute_s_min_F2` 削除（将来）

本関数はレガシー互換のため残存。テストの警告整理後、以下のタイムラインで削除：

1. **2025-Q1**: テスト内の直接呼び出しを排除
2. **2025-Q2**: `__all__` から除外、docstring に "will be removed in 2026-06" 追記
3. **2026-06**: 関数削除

---

## 検証プラン

### 自動テスト

```bash
# 警告なしでテスト実行（-W error::DeprecationWarning は厳しすぎるため除外）
pytest tests/unit/test_sublimation.py -v

# Pydantic 警告カウント確認
pytest tests/ 2>&1 | grep -c "PydanticDeprecatedSince20"
```

### 手動確認

- `python -c "from marsdisk.schema import Config; print('OK')"` でインポート検証
- `make analysis-doc-tests` パス確認

---

## 完了条件

- [ ] Phase 1 完了: テストファイル内の `compute_s_min_F2` 呼び出しが `pytest.warns` または新パターンに更新
- [ ] `pytest tests/unit/test_sublimation.py` が警告検証付きでパス
- [ ] 本プランレビュー完了

---

## 関連ドキュメント

- [20251212_simulation_methodology_cleanup.md](file:///Users/daichi/marsshearingsheet/docs/plan/20251212_simulation_methodology_cleanup.md) — Pydantic V2 移行の詳細計画
- [fragments.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/fragments.py) — `compute_s_min_F2` 定義
- [schema.py](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py) — Pydantic バリデータ群
