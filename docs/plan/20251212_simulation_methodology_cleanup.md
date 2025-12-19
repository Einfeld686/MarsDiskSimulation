# シミュレーション手法整備プラン（後方互換性改善版 v2）

> **作成日**: 2025-12-12  
> **ステータス**: 改訂版 v2 — レビュー指摘を反映

---

## 元プランからの主要変更点

### 問題1: Pydantic v2 移行の破壊的変更

**元の問題**: 21箇所の `@validator` と 7箇所の `@root_validator` を変更する必要がある

**現状**: Pydantic 2.5.1 上で v1 互換デコレータ（`@validator`, `@root_validator`）が正常動作中

> [!NOTE]
> 現在のコードは pydantic 2.x の v1 互換モードを使用しており、`values` 引数を受け取るバリデータ
> （例: `marsdisk/schema.py:612-617` の温度ヒエラルキー検証）も実行時に有効。
> **即時の破壊は発生していない。**

**v1 互換 vs v2 ネイティブの違い**（将来の完全移行時）:

| 機能 | Pydantic v1 互換 | Pydantic v2 ネイティブ |
|------|------------------|------------------------|
| 単一フィールド検証 | `@validator("field")` | `@field_validator("field")` |
| 他フィールド参照 | `values` 引数で取得 | `ValidationInfo.data` で取得 |
| モデル全体検証 | `@root_validator(pre=True)` | `@model_validator(mode="before")` |
| 検証スキップ | `@root_validator(skip_on_failure=True)` | `@model_validator(mode="after")` |

**移行戦略**: **段階的移行（v1 互換を維持しつつ v2 ネイティブへ）**

1. **Phase 2 では v1 互換デコレータを維持**（現状動作を保証）
2. v2 ネイティブへの移行は **別 PR で実施**（Phase 3 以降）
3. 移行時は以下のパターンで書き換え:

```python
# 将来の v2 ネイティブ移行時の書き方
from pydantic import field_validator, ValidationInfo

class PhaseThresholds(BaseModel):
    T_condense_K: float = Field(1700.0, gt=0.0)
    T_vaporize_K: float = Field(2000.0, gt=0.0)

    @field_validator("T_vaporize_K")
    @classmethod
    def _check_temperature_hierarchy(cls, value: float, info: ValidationInfo) -> float:
        condense = info.data.get("T_condense_K", 0.0)
        if value <= condense:
            raise ValueError("phase.thresholds.T_vaporize_K must exceed T_condense_K")
        return float(value)
```

---

### 問題2: run.py 分割による import 破壊

**正確な影響範囲**:

| パターン | 件数 | 対象ファイル |
|----------|------|-------------|
| `from marsdisk.run import ...` | 3件 | `inner_disk_runner.py`, `sweep_massloss_heatmap_gif.py`, `test_run_regressions.py` |
| `from marsdisk import run` | 19件 | 各種テストファイル（`test_sublimation_sio.py` 含む） |
| analysis アンカー参照 | 多数 | `[marsdisk/run.py:L...]` 形式の参照 |

**改善策**: **再エクスポート + DocSync 必須**

```python
# marsdisk/run.py (分割後も残す)
"""Backward compatibility shim — all public API re-exported."""
from marsdisk.cli import parse_args, apply_overrides
from marsdisk.core_run import run_zero_d, load_config, _main

__all__ = ["run_zero_d", "load_config", "parse_args", "apply_overrides", "_main"]
```

> [!WARNING]
> 分割後は **必ず DocSync を実行**し、analysis 内の run.py アンカーを更新すること。
> coverage が 0.75 を下回る場合は、新モジュール (`cli.py`, `core_run.py`) へのアンカー移行が必要。

**完了条件**:
```bash
# 1. DocSync でアンカー更新
python -m tools.doc_sync_agent --all --write

# 2. coverage 維持確認
python -m agent_test.ci_guard_analysis \
  --coverage analysis/coverage.json \
  --fail-under 0.75 \
  --require-clean-anchors

# 3. import 互換性
python -c "from marsdisk.run import run_zero_d, load_config; print('OK')"
python -c "from marsdisk import run; run.run_zero_d; print('OK')"
```

---

### 問題3: surface_ode 非推奨化の警告制御

**元の問題**: セッション全体で `MARSDISK_SUPPRESS_DEPRECATION` を設定すると、将来の他の DeprecationWarning もマスクされる

**改善策**: **対象テストのみで抑制 + 警告内容のアサーション**

```python
# tests/test_collision_solver_modes.py
import pytest
import warnings

def test_surface_ode_deprecated():
    """surface_ode が非推奨警告を出すことを確認"""
    with pytest.warns(DeprecationWarning, match="surface_ode solver is deprecated"):
        # surface_ode を使用するコード
        cfg.surface.collision_solver = "surface_ode"
        run.run_zero_d(cfg)

@pytest.fixture
def suppress_surface_ode_deprecation():
    """surface_ode の非推奨警告のみを抑制"""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="surface_ode solver is deprecated",
            category=DeprecationWarning,
        )
        yield
```

```python
# marsdisk/physics/surface.py
_SURFACE_ODE_DEPRECATION_MSG = (
    "surface_ode solver is deprecated and will be removed after 2026-06. "
    "Use collision_solver='smol' (default) instead."
)

def step_surface_density_S1(...):
    warnings.warn(_SURFACE_ODE_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    # ... 既存の実装
```

---

### 問題4: テストディレクトリ再編成の破壊

**改善策**: **Phase 3 に延期**（元プランから変更なし）

---

## 改訂版実装順序

### Phase 1: 安全な変更のみ（既存コード変更なし）

| 順序 | タスク | リスク | 状態 |
|------|--------|--------|------|
| 1-1 | ADR-0002 作成 | なし | [ ] 未着手 |
| 1-2 | README.md クイックスタート追記 | なし | [ ] 未着手 |
| 1-3 | `physics/__init__.py` に `__all__` 追加 | なし | [x] 完了 |
| 1-4 | smoke test matrix 新規作成 | なし | [ ] 未着手 |

### Phase 2: 互換性を維持したリファクタリング

| 順序 | タスク | 完了条件 | 状態 |
|------|--------|---------|------|
| 2-1 | run.py 分割 + 再エクスポート + DocSync | coverage ≥ 0.75, import 互換維持 | [ ] 未着手 |
| 2-2 | surface_ode deprecation（対象限定） | 警告テスト追加 | [x] 完了 |
| 2-3 | legacy alias deprecation | 警告出力確認 + pytest パス | [ ] 未着手 |
| 2-4 | physics_controls ブロック導入 | 既存 config.yml 読込可能 | [ ] 未着手 |

### Phase 3: 大規模変更（別 PR）

> [!WARNING]
> 以下は Phase 2 完了後、別途計画として分離

| タスク | 備考 | 状態 |
|--------|------|------|
| Pydantic v2 ネイティブ移行 | v1 互換デコレータ → v2 ネイティブ署名 | [x] 完了 |
| テストディレクトリ再編成 | pytest.ini 更新と同時実施 | [ ] 未着手 |
| Numba JIT 集約 | パフォーマンステスト追加後 | [ ] 未着手 |
| physics_flow.md 自動生成 | DocSync 拡張と同時 | [ ] 未着手 |

---

## 必須検証ゲート

各フェーズの実装後、以下を**すべてパスすること**を PR マージ条件とする:

```bash
# 1. 既存テストの完全パス
pytest tests/ -v

# 2. import 互換性の確認
python -c "from marsdisk.run import run_zero_d, load_config; print('imports OK')"
python -c "from marsdisk import run; run.run_zero_d; print('module import OK')"

# 3. DocSync + coverage ガード
python -m tools.doc_sync_agent --all --write
python -m agent_test.ci_guard_analysis \
  --coverage analysis/coverage.json \
  --fail-under 0.75 \
  --require-clean-anchors

# 4. 既存 config の互換性
python -m marsdisk.run --config configs/base.yml --dry-run
```

---

## 各タスク詳細（改訂版 v2）

### 2-2/2-3: Pydantic v2 完全移行

**変更が必要なバリデータの完全リスト**:

| 種類 | 箇所数 | 移行方法 |
|------|--------|----------|
| `@validator` (単純) | 14 | `@field_validator` + `@classmethod` |
| `@validator` (values 参照) | 7 | `@field_validator` + `ValidationInfo.data` |
| `@root_validator(pre=True)` | 4 | `@model_validator(mode="before")` |
| `@root_validator(skip_on_failure=True)` | 3 | `@model_validator(mode="after")` |

**変換例（values 参照あり）**:

```python
# Before (v1)
@validator("T_vaporize_K")
def _check_temperature_hierarchy(cls, value: float, values: Dict[str, Any]) -> float:
    condense = values.get("T_condense_K", 0.0)
    if value <= condense:
        raise ValueError("...")
    return float(value)

# After (v2)
from pydantic import field_validator, ValidationInfo

@field_validator("T_vaporize_K")
@classmethod
def _check_temperature_hierarchy(cls, value: float, info: ValidationInfo) -> float:
    condense = info.data.get("T_condense_K", 0.0)
    if value <= condense:
        raise ValueError("...")
    return float(value)
```

**変換例（root_validator）**:

```python
# Before (v1)
@root_validator(pre=True)
def _forbid_deprecated_radius(cls, values: Dict[str, Any]) -> Dict[str, Any]:
    if "r" in values and values.get("r") is not None:
        raise ValueError("geometry.r is no longer supported")
    return values

# After (v2)
from pydantic import model_validator

@model_validator(mode="before")
@classmethod
def _forbid_deprecated_radius(cls, data: Any) -> Any:
    if isinstance(data, dict):
        if "r" in data and data.get("r") is not None:
            raise ValueError("geometry.r is no longer supported")
    return data
```

### 2-4: run.py 分割 + DocSync

**分割後のファイル構成**:

```
marsdisk/
  run.py          ← 互換 shim（再エクスポートのみ）
  cli.py          ← argparse, ProgressReporter
  core_run.py     ← run_zero_d, load_config, 物理ループ
```

**DocSync 更新が必要な analysis ファイル**:
- `analysis/AI_USAGE.md`: `[marsdisk/run.py:...]` 形式のアンカー多数
- `analysis/overview.md`: run.py への参照
- `analysis/equations.md`: run.py への参照
- `analysis/run-recipes.md`: run.py への参照

**完了条件**:
```bash
python -m tools.doc_sync_agent --all --write
make analysis-doc-tests
# anchor_consistency_rate >= 0.98 を確認
```

### 2-5: surface_ode 非推奨化（対象限定）

```python
# marsdisk/physics/surface.py
import warnings

SURFACE_ODE_DEPRECATION_MSG = (
    "surface_ode solver is deprecated and will be removed after 2026-06. "
    "Use collision_solver='smol' (default) instead."
)

def step_surface_density_S1(...):
    """Legacy surface ODE solver (deprecated)."""
    warnings.warn(SURFACE_ODE_DEPRECATION_MSG, DeprecationWarning, stacklevel=2)
    # ... 既存の実装
```

**テスト（対象限定の警告抑制）**:

```python
# tests/test_collision_solver_modes.py
import pytest
import warnings
from marsdisk.physics.surface import SURFACE_ODE_DEPRECATION_MSG

@pytest.fixture
def ignore_surface_ode_deprecation():
    """surface_ode 非推奨警告のみを限定的に抑制"""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=SURFACE_ODE_DEPRECATION_MSG)
        yield

def test_surface_ode_mode(ignore_surface_ode_deprecation, tmp_path):
    # surface_ode を使うテスト
    ...

def test_surface_ode_emits_deprecation_warning():
    """非推奨警告が正しく出力されることを検証"""
    with pytest.warns(DeprecationWarning, match="surface_ode solver is deprecated"):
        ...
```

---

## 全体完了条件（改訂版 v2）

- [ ] Phase 1 全タスク完了（1-3 は完了済み）
- [ ] Phase 2 全タスク完了（Pydantic v2 必須化）
- [ ] `pytest tests/` 全パス
- [x] 既存 `from marsdisk.run import ...` および `from marsdisk import run` パターンが全て動作
- [x] `make analysis-doc-tests` パス
- [x] `anchor_consistency_rate >= 0.98`
- [x] ADR-0002 レビュー済み
- [x] `pydantic>=2.0` を要件に追加済み

---

## 関連ファイル

- [run.py](file:///Users/daichi/marsshearingsheet/marsdisk/run.py)
- [schema.py](file:///Users/daichi/marsshearingsheet/marsdisk/schema.py)
- [surface.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/surface.py)
- [physics/__init__.py](file:///Users/daichi/marsshearingsheet/marsdisk/physics/__init__.py) — `__all__` 定義済み
- [conftest.py](file:///Users/daichi/marsshearingsheet/tests/conftest.py)
- [test_collision_solver_modes.py](file:///Users/daichi/marsshearingsheet/tests/test_collision_solver_modes.py)
- [test_phase9_usecases.py](file:///Users/daichi/marsshearingsheet/tests/test_phase9_usecases.py)

---

## 付録: 影響を受けるファイル一覧

### `from marsdisk.run import` パターン（3件）

| ファイル | インポート |
|----------|-----------|
| `marsdisk/analysis/inner_disk_runner.py` | `load_config, run_zero_d` |
| `scripts/sweep_massloss_heatmap_gif.py` | `load_config, run_zero_d` |
| `tests/test_run_regressions.py` | `load_config, run_zero_d` |

### `from marsdisk import run` パターン（19件）

`test_phase_branching_run.py`, `test_reproducibility.py`, `test_sublimation_phase_gate.py`, `test_sinks_tracing.py`, `test_baseline_smol_pipeline.py`, `test_blowout_gate.py`, `test_mass_budget_combined.py`, `test_fast_blowout.py`, `test_temperature_selection.py`, `test_sublimation_sio.py` (L218), `test_supply_positive.py`, `test_temperature_driver.py`, `test_phase_map_fallback.py`, `test_streaming_merge.py`, `test_phase3_surface_blowout.py`, `test_zero_division_guards.py`, `test_step_diagnostics.py`, `test_min_size_evolution_hook.py`, `marsdisk/tests/test_timegrid_and_budget.py`

### バリデータ変換対象（schema.py）

| 行 | 種類 | 特記 |
|----|------|------|
| 29 | `@root_validator(pre=True)` | Geometry |
| 63 | `@root_validator(skip_on_failure=True)` | DiskGeometry |
| 106 | `@root_validator(pre=True)` | InnerDiskMass |
| 137 | `@root_validator(pre=True)` | SupplyMixing |
| 210 | `@validator("rho")` | Material |
| 233 | `@validator("T_M")` | Temps |
| 342 | `@root_validator(skip_on_failure=True)` | Dynamics |
| 553 | `@root_validator(pre=True)` | Process |
| 612 | `@validator("T_vaporize_K")` | **values 参照あり** |
| 663 | `@validator("entrypoint")` | PhaseConfig |
| 677 | `@validator("value_K")` | MarsTemperatureDriverConstant |
| 750 | `@validator("constant", always=True)` | MarsTemperatureDriverConfig |
| 760 | `@validator("table", always=True)` | MarsTemperatureDriverConfig |
| 809 | `@validator("Q_pr")` | Radiation |
| 819 | `@validator("source")` | Radiation |
| 944 | `@validator("dt_init")` | Time |
| 954 | `@validator("t_end_orbits")` | Time |
| 962 | `@validator("t_end_years")` | Time |
| 970 | `@validator("safety")` | Time |
| 976 | `@validator("atol", "rtol")` | Time |
| 982 | `@validator("dt_over_t_blow_max")` | Time |
| 990 | `@validator("orbit_rollup")` | Time |
| 994 | `@validator("eval_per_step")` | Time |
| 1061 | `@validator("memory_limit_gb")` | IO |
| 1067 | `@validator("step_flush_interval")` | IO |
| 1171 | `@root_validator(pre=True)` | Config |
| 1203 | `@validator("physics_mode")` | Config |
| 1214 | `@validator("chi_blow")` | Config |
