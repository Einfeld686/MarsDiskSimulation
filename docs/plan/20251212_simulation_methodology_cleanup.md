# シミュレーション手法整備プラン（後方互換性改善版 v2）

> **作成日**: 2025-12-12  
> **ステータス**: Phase 1 完了、Phase 2 完了、Phase 3（その他）進行中（3-A/3-B/3-C/3-D 実装完了、検証待ち）（2026-01-02更新）

## 実装状況サマリー

| Phase | 状況 |
|-------|------|
| Phase 1-1～1-3 | ✅ 完了 |
| Phase 1-4 (smoke test matrix) | ✅ 完了 |
| Phase 2-1, 2-2, 2-4 | ✅ 完了 |
| Phase 2-3 (legacy alias deprecation) | ✅ 完了 |
| Phase 3 (Pydantic v2) | ✅ 完了 |
| Phase 3 (その他) | 🟡 進行中（3-A/3-B/3-C/3-D 実装完了、検証待ち） |

---

## 現時点の整理（2026-01-02）

- **完了**: Phase 1 全般、Phase 2 全タスク、Phase 3(Pydantic v2)
- **進行中**: Phase 3(その他)（3-A/3-B/3-C/3-D 実装完了、検証待ち）
- **新規計画**: streaming chunk offload は実装済み（Macbook 検証済み）
- **進め方**: Macbook で効果検証し、run_sweep への影響を最小化

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

### 問題2: run_zero_d.py 分割による import 破壊

**正確な影響範囲**:

| パターン | 件数 | 対象ファイル |
|----------|------|-------------|
| `from marsdisk.run import ...` | 3件 | `marsdisk/analysis/inner_disk_runner.py`, `scripts/sweeps/sweep_massloss_heatmap_gif.py`, `tests/integration/test_run_regressions.py` |
| `from marsdisk import run` | 19件 | 各種テストファイル（`tests/integration/test_sublimation_sio.py` 含む） |
| analysis アンカー参照 | 多数 | `[marsdisk/run_zero_d.py:L...]` 形式の参照 |

**改善策**: **再エクスポート + DocSync 必須**

```python
# marsdisk/run.py （現行: run_zero_d の薄いラッパ）
"""Thin wrapper that forwards to the main zero-D runner implementation."""
from marsdisk.run_zero_d import *  # re-export main entrypoints
```

> [!WARNING]
> 分割後は **必ず DocSync を実行**し、analysis 内の run_zero_d.py アンカーを更新すること。
> coverage が 0.75 を下回る場合は、`marsdisk/run_zero_d.py` のアンカー移行が必要。

**完了条件**:
```bash
# 1. DocSync でアンカー更新
python -m tools.doc_sync_agent --all --write

# 2. coverage 維持確認
python -m agent_test.ci_guard_analysis \
  --coverage analysis/coverage/coverage.json \
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
# tests/integration/test_collision_solver_modes.py
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
| 1-1 | ADR-0002 作成 | なし | [x] 完了 |
| 1-2 | README.md クイックスタート追記 | なし | [x] 完了 |
| 1-3 | `physics/__init__.py` に `__all__` 追加 | なし | [x] 完了 |
| 1-4 | smoke test matrix 新規作成（[docs/plan/20260102_smoke_test_matrix.md](docs/plan/20260102_smoke_test_matrix.md)） | なし | [x] 完了 |

### Phase 2: 互換性を維持したリファクタリング

| 順序 | タスク | 完了条件 | 状態 |
|------|--------|---------|------|
| 2-1 | run_zero_d.py 分割 + 再エクスポート + DocSync | coverage ≥ 0.75, import 互換維持 | [x] 完了 |
| 2-2 | surface_ode deprecation（対象限定） | 警告テスト追加 | [x] 完了 |
| 2-3 | legacy alias deprecation | 警告出力確認 + pytest パス | [x] 完了 |
| 2-4 | physics_controls ブロック導入 | 既存 `configs/*.yml` 読込可能 | [x] 完了 |

### Phase 3: 大規模変更（別 PR）

> [!WARNING]
> 以下は Phase 2 完了後、別途計画として分離

| タスク | 備考 | 状態 |
|--------|------|------|
| Pydantic v2 ネイティブ移行 | v1 互換デコレータ → v2 ネイティブ署名 | [x] 完了 |
| テストディレクトリ再編成 | `pytest.ini` 更新と同時実施 | [x] 完了 |
| Numba JIT 集約 | パフォーマンステスト追加後 | [x] 完了 |
| physics_flow.md 自動生成 | DocSync 拡張と同時 | [x] 完了 |
| streaming chunk offload（外部HDD退避） | 実行中に古いチャンクを退避し、merge を維持 | [x] 実装完了（検証待ち） |

---

### Phase 3 (その他) 詳細タスク

**優先順位（順序）**:
1. 3-A テストディレクトリ再編成（作業基盤の整理）
2. 3-C physics_flow.md 自動生成（ドキュメントの自動化基盤）
3. 3-B Numba JIT 集約（実行系の安定化）
4. 3-D streaming chunk offload（運用負荷の削減）

**Phase 3 着手前の注意（チェックリスト）**:
- [x] 1タスク=1PR を維持する（混在変更を避ける）
  - 証跡: PR 説明で変更範囲を 1 タスクに限定した旨を明記
- [x] 既定挙動は不変、追加は opt-in のみ
  - 証跡: `schema.py` の既定値と README/plan の記載が一致
- [x] 3-A はパス/配置のみでテスト内容は不変更
  - 証跡: `pytest tests/ -q` が通り、テスト内容の変更がない
- [x] 3-B は numba on/off の差分最小化と例外処理集約
  - 証跡: on/off で unit テストが通り、警告差分が説明可能
- [x] 3-C は生成物の決定性担保と DocSync 統合
  - 証跡: `make analysis-sync` の差分が再現可能
- [x] analysis/ 更新時は DocSync + doc tests を必ず実行
  - 証跡: `make analysis-sync` → `make analysis-doc-tests` のログ

**保守性強化の方針（共通）**:
- 設定/スイッチは 1 箇所に集約し、重複実装を避ける（YAML → schema → runtime の一方向化）。
- 追加スクリプトは `tools/` に統一し、実行手順は plan 参照に限定（README の重複記述を避ける）。
- テストは「成功条件」と「失敗時の想定」まで明示し、後方互換の保証範囲を固定化する。

**批判的視点での補強ポイント**:
- タスクごとに **非目標** を明記し、スコープ拡張を防ぐ。
- デフォルト挙動の **非変更** を担保する（新機能は flag/opt-in で開始）。
- 1 タスク = 1 PR を基本とし、相互依存の混在を避ける。
- 変更点が「テスト/ログ/ドキュメント」のどれで検証されるかを明示する。

#### 3-A: テストディレクトリ再編成
- [x] 既存テストの分類方針を確定（unit / integration / slow などの境界）
- [x] `pytest.ini` でマーカーとデフォルト除外ルールを整理
- [x] `tests/` 配下の移動と import パスの修正
- [x] CI/ローカルの実行コマンド更新（README or plan 参照のみで可）
- [x] 既存 fixture を `tests/fixtures` に集約し、相互依存を削減
- **実行コマンド例**: `pytest tests/ -q` / `pytest -m unit` / `pytest -m integration`
- **レビュー観点（チェックリスト）**:
  - 実行コマンドの変更がドキュメントに反映されている（重複記述なし）
  - テストの意味が変わっていない（skip/xfail の追加なし）
  - import パスの更新漏れがない（ローカル/CI 両方で成功）
- **非目標**: テストの意味・内容の変更、テスト仕様の拡張
- **完了条件**: `pytest tests/ -q` が通り、既存の `tests/integration/*` を含めて網羅できる

#### 3-B: Numba JIT 集約
- [x] Numba 依存箇所の棚卸し（環境変数/フラグ/初期化箇所）
- [x] 有効/無効スイッチを 1 箇所に集約（`marsdisk.io.tables` 等の既存トグルと整合）
- [x] fallback の警告と挙動を統一（Numba 失敗時のログ粒度を整理）
- [x] `NUMBA_DISABLE` 相当の環境変数をドキュメント化（既存と衝突しない名称）
- [x] Numba 例外の捕捉範囲を明確化し、計算結果の差分を最小化
- **レビュー観点（チェックリスト）**:
  - デフォルト挙動が変わっていない（numba 無効時の結果が従来通り）
  - 例外ハンドリングが 1 箇所で完結している（分岐の重複なし）
  - 警告が増えていない（数・内容の差分が説明可能）
- **非目標**: 物理式やアルゴリズムの変更、性能最適化の大規模改修
- **完了条件**: numba 有効/無効の両方で unit テストが通り、警告が過剰に増えない

#### 3-C: physics_flow.md 自動生成
- [x] 生成対象の情報源を整理（run.py セクション表、schema 参照、dataflow）
- [x] 自動生成スクリプトを `tools/` に追加し、DocSync バッチに統合
- [x] 生成物は手編集禁止（README/overview に注記）
- [x] 生成物の diff が大きくならないように順序/整形ルールを固定
- **レビュー観点（チェックリスト）**:
  - 生成物が決定的である（同一入力で差分が出ない）
  - DocSync バッチに組み込まれている（手動手順の追加なし）
  - 生成物のアンカー整合性が崩れていない
- **非目標**: 新しい設計内容の追加（既存情報の再表現に限定）
- **完了条件**: `make analysis-sync` で `physics_flow.md` が再生成される

#### 3-D: streaming chunk offload（外部HDD退避）
- [x] 詳細仕様は「3-1: streaming chunk offload」節に準拠
- [x] `schema.py` と `streaming.py` の実装追加
- [x] `tests/` に offload/merge 再開テストを追加
- [x] 例外時のログとリカバリ手順を固定（失敗時はローカル保持）
- **レビュー観点（チェックリスト）**:
  - デフォルトは offload 無効（既存挙動の維持）
  - merge 結果の row_count が一致する（offload 有無で同じ）
  - offload 失敗時にローカルへ安全にフォールバックする
  - 再起動時の再探索が想定通り動作する（重複の扱い含む）
- **非目標**: `run_sweep.cmd` のロジック変更、出力スキーマの変更
- **完了条件**: Macbook で小規模 run → offload → merge が成立する

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
  --coverage analysis/coverage/coverage.json \
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

### 2-4: run_zero_d.py 分割 + DocSync

**分割後のファイル構成**:

```
marsdisk/
  run.py          ← 互換 shim（run_zero_d を再エクスポート）
  run_zero_d.py   ← run_zero_d, load_config, CLI main
  run_one_d.py    ← 1D runner
```

**DocSync 更新が必要な analysis ファイル**:
- `analysis/AI_USAGE.md`: `[marsdisk/run_zero_d.py:...]` 形式のアンカー多数
- `analysis/overview.md`: run_zero_d.py への参照
- `analysis/equations.md`: run_zero_d.py への参照
- `analysis/run-recipes.md`: run_zero_d.py への参照

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
# tests/integration/test_collision_solver_modes.py
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

### 3-1: streaming chunk offload（外部HDD退避）

**背景/目的**: streaming flush のチャンクが `out/series` に蓄積して SSD を圧迫するため、古いチャンクを外部HDDへ退避して内部ストレージ使用量を抑える。

**既存ストレージ運用（run_sweep + overrides の前提）**:
- `OUT_ROOT` は内部SSD（既定 `out` もしくは `LOCALAPPDATA\marsdisk_out`）を優先し、空き容量が `MIN_INTERNAL_FREE_GB` 未満の場合は外部SSD（既定 `EXTERNAL_OUT_ROOT`）へフォールバックする。
- `BATCH_ROOT=OUT_ROOT` を用いてローカルでステージングし、`BATCH_ROOT` と `io.archive.dir` を同一にしない（run_sweep のチェックで強制）。
- `io.archive` は外部HDD（例: `EXTERNAL_ARCHIVE_ROOT`）へ保存する前提で有効化され、`merge_target=external` と `keep_local=metadata` を要求する。
- アーカイブ実行は run_temp_supply_sweep の `archive` フック（`python -m marsdisk.archive`）で行われ、**チャンクファイルはコピー対象から除外**される。
- `io.archive.dir` が見つからない場合は `OUT_ROOT\archive` にフォールバックする（同一ディスクに退避されるため、実行中のSSD削減効果は弱い）。
- `merge_target=external` の場合、`streaming` の最終マージは `archive_root/run_id` 側へ書き出される（ローカルチャンクは残存する）。

**前提/注意**:
- 現状の `merge_chunks` はローカルのチャンクを前提とするため、単純移動は `series/run.parquet` の生成を破壊する。
- `io.archive` は実行後の退避であり、実行中のディスク使用量は減らない。

**仕様案（案）**:
- `io.streaming.offload.enabled`（default: false）
- `io.streaming.offload.dir`（外部ボリュームの絶対パス。未指定時は `io.archive.dir/<run_id>/series_chunks` を優先）
- `io.streaming.offload.keep_last_n`（default: 2）
- `io.streaming.offload.mode`（`copy` / `move`）
- `io.streaming.offload.verify`（`size` / `hash`）
- `io.streaming.offload.skip_if_same_device`（default: true、`OUT_ROOT` と同一デバイスの場合は実行しない）

**動作イメージ**:
1. `flush` 後に、`keep_last_n` より古いチャンクを offload 先へ移動。
2. 移動成功時に `run_chunks` / `psd_chunks` / `diag_chunks` のパスを更新。
3. `merge_chunks` は更新済みパス（ローカル+外部混在）を読み込む。
4. 移動失敗時はローカル保持し、警告のみ出す。

**テスト観点**:
- 擬似チャンク作成 → offload → merge で row_count が一致すること。
- `merge_outdir` が外部の場合でも merge が通ること。
- `io.archive.dir` が未接続のときは offload を自動スキップし、`OUT_ROOT\archive` へ落とさないこと。

**補助施策**:
- `step_flush_interval` を増やしてチャンク生成/移動頻度を抑制する。

**overrides.txt コメント枠（案）**:
```
# --- Optional: streaming chunk offload (EXPERIMENTAL) ---
# Keep these commented unless offload is required.
# dir omitted => use io.archive.dir/<run_id>/series_chunks (runtime default)
# io.streaming.offload.enabled=false
# io.streaming.offload.dir=E:\marsdisk_archive\series_chunks
# io.streaming.offload.keep_last_n=2
# io.streaming.offload.mode=move
# io.streaming.offload.verify=size
# io.streaming.offload.skip_if_same_device=true
```

**復旧/再探索ルール（再起動時の検知）**:
- run_dir/series に残っているローカルチャンクは常に優先的に収集する。
- offload_dir が指定されている場合は、`series/*_chunk_*.parquet` を再探索して既存チャンク一覧に追加する。
- `run_config.json` に offload 設定と offload_dir を記録し、再起動時の再探索に用いる。
- 再探索で重複するチャンクが見つかった場合は、最終更新時刻が新しい方を採用し、古い方は警告ログのみ。
- offload_dir が存在しない/未接続の場合は再探索をスキップし、ローカルのみで merge を試行する。

**重複判定ルール（mtime/size/hash の優先度）**:
- 重複判定はチャンク名（`*_chunk_<start>_<end>.parquet`）で同一性を確定する。
- `verify=hash` の場合は hash を最優先で比較し、不一致時は **新しい mtime** を採用（警告を出す）。
- `verify=size` の場合は **size → mtime** の順で優先する（size が大きい方を優先、同一なら新しい mtime）。
- size と mtime が同一で差が付かない場合は **ローカル優先**（同一ファイルとみなし警告のみ）。

**verify=hash の適用方針**:
- **デフォルトは `verify=size`** とし、通常の運用では十分と判断する（I/O負荷と実行時間を優先）。
- `verify=hash` を使うのは次の場合に限定する:
  - 外部HDDが不安定/USB接続で書き込みエラーが疑われる場合
  - 途中で強制終了・再開を繰り返して整合性が不安な場合
  - 研究成果として最終保存版を確定する「最終 run」に限る

**仕様確定チェックリスト（offload）**:
- [x] offload 設定キーとデフォルトを確定
- [x] OUT_ROOT / io.archive との整合を明文化
- [x] 復旧・再探索ルールを確定
- [x] 重複判定と verify=hash 適用方針を確定
- [x] 再探索対象の優先順位（run/diagnostics/psd）を確定
- [x] Macbook で小規模 run の効果検証（offload→merge）

**再探索対象の優先順位（psd/diagnostics）**:
- 最優先: `run_chunk_*`（常に収集、系列本体の前提）。
- 次点: `diagnostics_chunk_*`（diagnostics 有効時のみ再探索）。
- 最後: `psd_hist_chunk_*`（psd_history 有効時のみ再探索、容量が最も大きくなりがち）。

---

## 全体完了条件（改訂版 v2）

- [x] Phase 1 全タスク完了（1-3 は完了済み）
- [x] Phase 2 全タスク完了（Pydantic v2 必須化）
- [x] `pytest tests/` 全パス
- [x] 既存 `from marsdisk.run import ...` および `from marsdisk import run` パターンが全て動作
- [x] `make analysis-doc-tests` パス
- [x] `anchor_consistency_rate >= 0.98`
- [x] ADR-0002 レビュー済み
- [x] `pydantic>=2.0` を要件に追加済み

---

## 関連ファイル

- [run_zero_d.py](marsdisk/run_zero_d.py)
- [schema.py](marsdisk/schema.py)
- [surface.py](marsdisk/physics/surface.py)
- [physics/__init__.py](marsdisk/physics/__init__.py) — `__all__` 定義済み
- [conftest.py](tests/conftest.py)
- [test_collision_solver_modes.py](tests/integration/test_collision_solver_modes.py)
- [test_phase9_usecases.py](tests/integration/test_phase9_usecases.py)

---

## 付録: 影響を受けるファイル一覧

### `from marsdisk.run import` パターン（3件）

| ファイル | インポート |
|----------|-----------|
| `marsdisk/analysis/inner_disk_runner.py` | `load_config, run_zero_d` |
| `scripts/sweeps/sweep_massloss_heatmap_gif.py` | `load_config, run_zero_d` |
| `tests/integration/test_run_regressions.py` | `load_config, run_zero_d` |

### `from marsdisk import run` パターン（19件）

`tests/integration/test_phase_branching_run.py`, `tests/integration/test_reproducibility.py`, `tests/integration/test_sublimation_phase_gate.py`, `tests/integration/test_sinks_tracing.py`, `tests/integration/test_baseline_smol_pipeline.py`, `tests/integration/test_blowout_gate.py`, `tests/integration/test_mass_budget_combined.py`, `tests/integration/test_fast_blowout.py`, `tests/integration/test_temperature_selection.py`, `tests/integration/test_sublimation_sio.py` (L218), `tests/integration/test_supply_positive.py`, `tests/integration/test_temperature_driver.py`, `tests/integration/test_phase_map_fallback.py`, `tests/integration/test_streaming_merge.py`, `tests/integration/test_phase3_surface_blowout.py`, `tests/integration/test_zero_division_guards.py`, `tests/integration/test_step_diagnostics.py`, `tests/integration/test_min_size_evolution_hook.py`, `tests/unit/test_timegrid_and_budget.py`

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
