# シミュレーション手法整備プラン（実装版）

> **作成日**: 2025-12-12  
> **ステータス**: 意思決定完了 → 実装待ち

---

## 決定事項サマリ

| # | 項目 | 決定 |
|---|------|------|
| 1 | 二重経路（Smol vs 表層ODE） | **表層ODE を非推奨化**（deprecation warning） |
| 2 | run.py 分割 | **2ファイル分割**（cli.py + run.py） |
| 3 | legacy alias | **警告付き非推奨**（6〜12ヶ月後廃止） |
| 4 | physics_controls | **ブロックに集約** |
| 5 | クイックスタート | **README.md に追記** |
| 6 | physics_flow.md | **自動生成スクリプト作成** |
| 7 | config_guide | **現状維持**（冒頭追加・別ファイル作成は不要、設定変更に伴う更新は実施） |
| 8 | ADR | **作成する** |
| 9 | `__all__` | **公開APIを明示** |
| 10 | Numba JIT | **集約する** |
| 11 | テストファイル | **カテゴリ別に整理** |
| 12 | Smol vs 表層ODE 比較テスト | 不要 |
| 13 | smoke test matrix | **拡充する** |
| 14 | 優先順位 | **小規模タスク優先** |
| 15 | Pydantic | **v2 移行**（`@field_validator` / `@model_validator`） |
| 16 | DocSync | **run.py 分割後に実行**（coverage 低下防止） |

---

## 実装順序（小規模 → 中規模）

### Phase 1: 小規模タスク（各1時間以内）

| 順序 | タスク | 対象ファイル |
|------|--------|--------------|
| 1-1 | Pydantic v2 移行 | `marsdisk/schema.py` |
| 1-2 | 表層ODE 非推奨化 warning 追加 | `marsdisk/physics/surface.py`, `marsdisk/run.py` |
| 1-3 | legacy alias に deprecation warning | `marsdisk/schema.py` |
| 1-4 | ADR-0002 作成（本整備の決定記録） | `analysis/adr/0002-methodology-cleanup.md` |
| 1-5 | README.md にクイックスタート追記 | `README.md` |
| 1-6 | `physics/__init__.py` に `__all__` 追加 | `marsdisk/physics/__init__.py` |
| 1-7 | smoke test matrix 拡充 | `tests/test_smoke_matrix.py`（新規） |

### Phase 2: 中規模タスク（各2-4時間）

| 順序 | タスク | 対象ファイル | 完了条件 |
|------|--------|--------------|----------|
| 2-1 | run.py 2ファイル分割 | `marsdisk/run.py` → `cli.py` + `run.py` | DocSync 実行、coverage 維持 |
| 2-2 | physics_controls ブロック導入 | `marsdisk/schema.py`, `configs/base.yml` | — |
| 2-3 | physics_flow.md 自動生成スクリプト | `tools/gen_physics_flow.py`（新規） | — |
| 2-4 | Numba JIT 関数集約 | `marsdisk/physics/_numba_kernels.py` | — |
| 2-5 | テストのカテゴリ別整理 | `tests/` → `tests/{physics,io,integration}/` | — |

---

## 各タスク詳細

### 1-1: Pydantic v2 移行

```python
# Before (v1)
from pydantic import validator
class Material(BaseModel):
    @validator("rho")
    def check_rho(cls, v):
        ...

# After (v2)
from pydantic import field_validator
class Material(BaseModel):
    @field_validator("rho")
    @classmethod
    def check_rho(cls, v):
        ...
```

- 21箇所の `@validator` → `@field_validator` 変換
- `always=True` → `mode='before'` または削除
- `pre=True` → `mode='before'`

### 1-2: 表層ODE 非推奨化

```python
# marsdisk/physics/surface.py
import warnings

def step_surface_density_S1(...):
    warnings.warn(
        "surface_ode solver is deprecated and will be removed in a future version. "
        "Use collision_solver='smol' (default) instead.",
        DeprecationWarning,
        stacklevel=2
    )
    ...
```

### 1-3: legacy alias 非推奨化

```python
# marsdisk/schema.py (v2 style)
@field_validator('phi_table', mode='before')
@classmethod
def _warn_phi_table(cls, v):
    if v is not None:
        warnings.warn(
            "'phi_table' is deprecated. Use 'shielding.table_path' instead.",
            DeprecationWarning
        )
    return v
```

### 2-1: run.py 分割 + DocSync

**分割後の構成**:
- `cli.py`: argparse, ヘルパー関数, ProgressReporter
- `run.py`: run_zero_d, 物理ループ

**完了条件**:
```bash
python -m tools.doc_sync_agent --all --write
make analysis-doc-tests
# coverage が 0.75 以上を維持すること
```

### 2-2: physics_controls ブロック

```yaml
# configs/base.yml
physics_controls:
  blowout_enabled: true
  shielding_mode: psitau
  sublimation_enabled: true
  freeze_kappa: false
  freeze_sigma: false
  collision_solver: smol  # "smol" | "surface_ode" (deprecated)
```

---

## 全体完了条件

- [ ] 全タスク実装完了
- [ ] `make analysis-doc-tests` パス
- [ ] 既存テスト（`pytest tests/`）パス
- [ ] ADR-0002 がレビュー済み
- [ ] Pydantic v2 での動作確認

---

## 関連ファイル

- [run.py](file:///Users/daichi/marsshearingsheet/marsdisk/run.py)
- [schema.py](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py)
- [surface.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/surface.py)
- [physics_flow.md](file:///Users/daichi/marsshearingsheet/analysis/physics_flow.md)
