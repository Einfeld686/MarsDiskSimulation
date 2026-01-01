# デバッグ基盤改善計画

> **作成日**: 2025-12-18  
> **関連**: [20251217_code_improvements_followup.md](.docs/plan/20251217_code_improvements_followup.md)（主に完了済み）

---

## 背景

`20251217_code_improvements_followup.md` の改善項目がほぼ実装完了したため、**異なる観点**からデバッグ効率向上のための追加改善を整理する。

### 現状サマリ

| 項目 | 現状 | 出典 |
|------|------|------|
| `errors.py` | `MarsDiskError` のみ（10行） | - |
| `warnings.warn()` 使用箇所 | 14箇所（構造化なし） | `rg "warnings.warn" marsdisk/` |
| Provenance coverage | 7/44 式（15.9%） | [provenance_report.md L58-67](analysis/provenance_report.md) |
| TODO(REF:...) 残存 | 37件（report値）／ファイルは0件（要再生成） | [analysis/UNKNOWN_REF_REQUESTS.jsonl](analysis/UNKNOWN_REF_REQUESTS.jsonl) |
| `run.py` 行数 | 4,489行（目標 4,000行） | `wc -l marsdisk/run.py` |
| テストルート残存 | 2ファイル | - |

> [!NOTE]
> 上記の数値は 2025-12-18 時点のスナップショットです。最新値は各出典ファイルを参照してください。

---

## 1. エラーハンドリング基盤の拡充

### 1.1 カスタム例外クラスの追加

**現状**: 36ファイルで `raise` が使われているが、`ValueError`/`RuntimeError` を直接使用

**目標**: エラー発生箇所の特定を容易にする階層化された例外

```python
# marsdisk/errors.py に追加

class ConfigurationError(MarsDiskError):
    """設定ファイルの検証エラー"""

class PhysicsError(MarsDiskError):
    """物理計算中のエラー（非物理的な値など）"""

class NumericalError(MarsDiskError):
    """数値計算の収束失敗・オーバーフロー等"""

class TableLoadError(MarsDiskError):
    """テーブル（Q_pr, Φ等）の読み込みエラー"""
```

**適用対象** (段階的に移行):

| モジュール | 現在の例外 | 移行先 |
|------------|-----------|--------|
| `schema.py` | `ValueError` | `ConfigurationError` |
| `physics/*.py` | `ValueError`, `RuntimeError` | `PhysicsError` |
| `run.py` 数値処理 | `RuntimeError` | `NumericalError` |

> [!WARNING]
> **`io/tables.py` のフォールバック動作は維持**
>
> 現在 `io/tables.py` は「テーブル読込失敗時に警告を出しつつ近似で継続」する設計です。
> この動作は互換性と実行継続性のため**変更しません**。
> `TableLoadError` は将来的に「フォールバックも不可能な致命的エラー」に限定して導入を検討します。

**工数**: 1-2時間

---

### 1.2 警告の構造化

**現状**: 14箇所で `warnings.warn()` がバラバラに使用

**対象ファイル**:
- `physics/fragments.py` (4箇所)
- `physics/collide.py` (2箇所)
- `physics/collisions_smol.py` (2箇所)
- `physics/smol.py` (1箇所)
- `io/tables.py` (3箇所)
- `marsdisk/ops/doc_sync_agent.py` (2箇所)

**提案**:

```python
# marsdisk/warnings.py （新規）

import warnings

class MarsDiskWarning(UserWarning):
    """Base warning for marsdisk"""

class PhysicsWarning(MarsDiskWarning):
    """物理計算に関する警告（非物理的パラメータ等）"""

class NumericalWarning(MarsDiskWarning):
    """数値計算に関する警告（精度低下等）"""

class TableWarning(MarsDiskWarning):
    """テーブル読み込みに関する警告"""
```

**工数**: 1時間

---

## 2. Provenance カバレッジ向上

### 2.1 現状

**計測ソース**:
- `analysis/provenance_report.md` L58-67: Coverage Summary テーブル
- `analysis/UNKNOWN_REF_REQUESTS.jsonl`: 未解決参照の構造化リスト
- `analysis/coverage/coverage.json`: 関数参照率・アンカー整合率

**スナップショット値** (2025-12-18 時点):
- **確認済み式**: 7/44 (15.9%)
- **TODO(REF:...) 残存**: 37件（provenance_report.md の値／analysis/UNKNOWN_REF_REQUESTS.jsonl は空）
- 主要クラスタ: `blowout_core`, `shielding_gate_order`, `psd_wavy_floor`, `tcoll_regime_switch`, `sublimation_gasdrag`, `radius_fix_0d`

### 2.2 優先対応（ドキュメント系）

| クラスタ | 関連式 | 対応優先度 |
|----------|--------|-----------|
| `blowout_core_eid_v1` | E.007/E.013/E.014 | 高 |
| `tcoll_regime_switch_v1` | E.006/E.007 | 高 |
| `sublimation_gasdrag_scope_v1` | E.018/E.019/E.036-E.038 | 中 |
| `shielding_gate_order_v1` | E.015-E.017/E.031 | 中 |

**工数**: 継続的（各クラスタ 30分〜1時間）

---

## 3. アーキテクチャ整理

### 3.1 `run.py` の責務分離

**現状**: 5,033行（目標 4,000行以下）

**既存の分離済みモジュール**:
- `orchestrator.py` (473行): 時間グリッド解決、状態管理
- `physics_step.py` (526行): ステップ単位の物理計算

**追加移動候補**:

| 関数群 | 移動先 | 削減見込み |
|--------|--------|-----------|
| `_resolve_time_grid`, `_resolve_seed` | `orchestrator.py` | ~100行 |
| `_parse_override_value`, `_apply_overrides_dict` | `config_utils.py` | ~80行 |
| `_human_bytes`, `_memory_estimate` | `orchestrator.py` (既存あり) | 重複削除 |
| 診断出力系 (`_write_diagnostics_*`) | `io/diagnostics.py`（新規） | ~200行 |

> [!IMPORTANT]
> **移動後の必須ワークフロー** (AGENTS.md / AI_USAGE.md 準拠)
>
> ```bash
> # 1. DocSync でアンカー同期
> python -m tools.doc_sync_agent --all --write
>
> # 2. ドキュメントテスト
> make analysis-doc-tests
>
> # 3. 評価システム実行（必須）
> python -m tools.evaluation_system --outdir <run_dir>
> ```
>
> `<run_dir>` は直近のシミュレーション出力パス（`out/<run_id>` または `analysis/outputs/<run_id>`）を指定。

**工数**: 3-4時間

---

### 3.2 テストファイル配置整理

**現状**: ルートに2ファイル残存

| ファイル | 移動先 |
|----------|--------|
| `tests/unit/test_energy_bookkeeping.py` | `tests/unit/` |
| `tests/unit/test_energy_bookkeeping_boundaries.py` | `tests/unit/` |

**工数**: 15分

---

## 完了条件

### 高優先度（必須）

- [x] `errors.py` に 4+ のカスタム例外クラスが追加されている
- [x] 主要モジュール（`schema.py`, `physics/*.py`）がカスタム例外を使用

### 中優先度（推奨）

- [x] `warnings.py` が新設され、構造化警告が使用されている
- [x] `run.py` が 4,500行以下
- [x] テストファイルが適切なディレクトリに配置されている

### 低優先度（任意）

- [ ] Provenance coverage が 30% 以上
- [x] 診断出力が `io/diagnostics.py` に分離されている

---

## 変更履歴

| 日付 | 変更内容 |
|------|----------|
| 2025-12-18 | ユーザー指摘反映: evaluation_system 必須ワークフロー追加、Provenance計測ソース明記、TableLoadErrorフォールバック方針修正 |
| 2025-12-18 | 初版作成 |
